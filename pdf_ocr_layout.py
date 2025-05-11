import os
import sys
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import re
from datetime import datetime
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import time
import logging
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_document_client():
    """Initialize and return the Azure Document Intelligence client."""
    endpoint = os.getenv('AZURE_DOCUMENT_ENDPOINT')
    key = os.getenv('AZURE_DOCUMENT_KEY')
    
    if not endpoint or not key:
        logger.error("Azure Document Intelligence credentials not found in environment variables")
        raise ValueError("Azure Document Intelligence credentials not found in environment variables")
    
    try:
        client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        logger.info("Successfully initialized Azure Document Intelligence client")
        return client
    except Exception as e:
        logger.error(f"Error initializing Azure Document Intelligence client: {str(e)}")
        raise

def extract_date_from_text(text):
    """Extract date from text in various formats."""
    # Common date patterns
    patterns = [
        r'\d{2}[/-]\d{2}[/-]\d{4}',  # DD/MM/YYYY or DD-MM-YYYY
        r'\d{4}[/-]\d{2}[/-]\d{2}',  # YYYY/MM/DD or YYYY-MM-DD
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',  # Month DD, YYYY
        r'\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}'  # DD Month YYYY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group()
            try:
                # Try to parse the date
                if '/' in date_str or '-' in date_str:
                    if len(date_str.split('/')[0]) == 4:  # YYYY/MM/DD
                        date = datetime.strptime(date_str, '%Y/%m/%d')
                    else:  # DD/MM/YYYY
                        date = datetime.strptime(date_str, '%d/%m/%Y')
                else:
                    # Handle month names
                    date = datetime.strptime(date_str, '%B %d, %Y')
                return date.strftime('%Y-%m-%d')
            except ValueError:
                continue
    
    # Return current date if no date found
    return datetime.now().strftime('%Y-%m-%d')

def load_medical_template():
    """Load the medical template from JSON file."""
    try:
        with open('medical_template.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: medical_template.json not found. Using empty template.")
        return {}

def parse_medical_results(result):
    """Parse the Document Intelligence results into structured data."""
    template = load_medical_template()
    data = template.copy()
    
    # Extract all text from the document
    all_text = []
    for page in result.pages:
        for line in page.lines:
            all_text.append(line.content)
    full_text = ' '.join(all_text)
    
    # Extract date from text
    date = extract_date_from_text(full_text)
    if 'metadata' not in data:
        data['metadata'] = {}
    data['metadata']['date'] = date
    
    # Process each page
    for page in result.pages:
        # Group lines by their vertical position
        lines_by_y = {}
        for line in page.lines:
            # Round y-coordinate to handle slight misalignments
            y_pos = round(line.bounding_polygon[0].y)
            if y_pos not in lines_by_y:
                lines_by_y[y_pos] = []
            lines_by_y[y_pos].append(line)
        
        # Sort lines by y-position
        sorted_y_positions = sorted(lines_by_y.keys())
        
        # Process each row
        for y_pos in sorted_y_positions:
            # Sort lines in this row by x-position
            row_lines = sorted(lines_by_y[y_pos], key=lambda line: line.bounding_polygon[0].x)
            row_text = " ".join(line.content for line in row_lines)
            
            # Check each category in the template
            for category, params in data.items():
                if category == 'metadata':
                    continue
                    
                if isinstance(params, dict):
                    for param_name, _ in params.items():
                        # Create variations of the parameter name
                        variations = [
                            param_name,
                            param_name.lower(),
                            param_name.replace(' Count', ''),
                            param_name.replace(' Count', '').strip()
                        ]
                        
                        # Check if any variation matches
                        for variation in variations:
                            if variation.lower() in row_text.lower():
                                # Extract the value using regex
                                pattern = f"{re.escape(variation)}[\\s:]*([-+]?\\d*\\.?\\d+(?:\\s*[-–]\\s*\\d*\\.?\\d+)?(?:\\s*x\\s*10\\^\\d+)?(?:\\s*[a-zA-Z%]+)?)"
                                match = re.search(pattern, row_text, re.IGNORECASE)
                                if match:
                                    value = match.group(1).strip()
                                    # Clean up the value
                                    value = value.replace('–', '-').replace('×', 'x')
                                    data[category][param_name] = value
                                    break
    
    return data

def process_file(file_path, output_dir="output"):
    """Process a file (PDF or image) using Document Intelligence."""
    try:
        logger.info(f"Processing file: {file_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize Document Intelligence client
        document_client = get_document_client()
        
        # Read the file
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Start the analysis
        logger.info("Starting document analysis")
        poller = document_client.begin_analyze_document(
            "prebuilt-document", file_content
        )
        
        # Wait for the analysis to complete
        logger.info("Waiting for analysis to complete")
        result = poller.result()
        
        # Parse the results
        logger.info("Parsing results")
        structured_data = parse_medical_results(result)
        
        # Save the structured data
        output_file = os.path.join(output_dir, "structured_data.json")
        logger.info(f"Saving structured data to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(structured_data, f, indent=2)
        
        # Save the raw text
        text_file = os.path.join(output_dir, "extracted_text.txt")
        logger.info(f"Saving raw text to: {text_file}")
        with open(text_file, 'w', encoding='utf-8') as f:
            for page in result.pages:
                for line in page.lines:
                    f.write(line.content + '\n')
        
        logger.info("File processing completed successfully")
        return output_file
        
    except Exception as e:
        logger.error(f"Error in process_file: {str(e)}")
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_ocr_layout.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        output_file = process_file(file_path)
        print(f"Results saved to: {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1) 