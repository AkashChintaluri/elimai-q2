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
import tkinter as tk
from tkinter import filedialog, messagebox

# Load environment variables
load_dotenv()

def get_document_client():
    """Create and return Azure Document Intelligence client."""
    endpoint = os.getenv('AZURE_DOCUMENT_ENDPOINT')
    key = os.getenv('AZURE_DOCUMENT_KEY')
    
    if not endpoint or not key:
        raise ValueError("Please set AZURE_DOCUMENT_ENDPOINT and AZURE_DOCUMENT_KEY in .env file")
    
    # Validate endpoint format
    if not endpoint.startswith('https://'):
        endpoint = f'https://{endpoint}'
    if not endpoint.endswith('/'):
        endpoint = f'{endpoint}/'
    
    try:
        client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        # Test the connection
        client.begin_analyze_document(
            "prebuilt-document",
            b"test"
        ).cancel()
        return client
    except Exception as e:
        error_msg = f"Error initializing Document Intelligence client: {str(e)}"
        if "endpoint" in str(e).lower():
            error_msg += "\nPlease check your AZURE_DOCUMENT_ENDPOINT format. It should be like: https://your-resource-name.cognitiveservices.azure.com/"
        elif "key" in str(e).lower():
            error_msg += "\nPlease check your AZURE_DOCUMENT_KEY"
        raise ValueError(error_msg)

def extract_date_from_text(text):
    """Extract date from text using various common date formats."""
    # Common date patterns
    date_patterns = [
        # DD/MM/YYYY or DD-MM-YYYY
        r'\b(0?[1-9]|[12][0-9]|3[01])[/-](0?[1-9]|1[0-2])[/-](19|20)\d{2}\b',
        # YYYY/MM/DD or YYYY-MM-DD
        r'\b(19|20)\d{2}[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12][0-9]|3[01])\b',
        # Month DD, YYYY (e.g., January 1, 2024)
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12][0-9]|3[01]),\s+(19|20)\d{2}\b',
        # DD Month YYYY (e.g., 1 January 2024)
        r'\b(0?[1-9]|[12][0-9]|3[01])\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(19|20)\d{2}\b'
    ]
    
    # Try each pattern
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(0)
            try:
                # Try to parse the date
                if '/' in date_str or '-' in date_str:
                    # Handle DD/MM/YYYY or YYYY/MM/DD
                    if len(date_str.split('/')[0]) == 4 or len(date_str.split('-')[0]) == 4:
                        date_obj = datetime.strptime(date_str, '%Y/%m/%d' if '/' in date_str else '%Y-%m-%d')
                    else:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y' if '/' in date_str else '%d-%m-%Y')
                else:
                    # Handle text month formats
                    if date_str.split()[0] in ['January', 'February', 'March', 'April', 'May', 'June', 
                                             'July', 'August', 'September', 'October', 'November', 'December']:
                        date_obj = datetime.strptime(date_str, '%B %d, %Y')
                    else:
                        date_obj = datetime.strptime(date_str, '%d %B %Y')
                
                # Return formatted date
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue
    
    # If no date found, return current date
    return datetime.now().strftime('%Y-%m-%d')

def load_medical_template():
    """Load the medical test template from JSON file."""
    try:
        with open('medical_template.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("medical_template.json not found. Please ensure the template file exists.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in medical_template.json")

def parse_medical_results(document_result):
    """Parse document analysis result and structure it as JSON with medical test hierarchy."""
    # Load the template
    template = load_medical_template()
    
    # Initialize the result structure
    result = {
        "metadata": {
            "date": None
        },
        "HAEMATOLOGY": {}
    }
    
    # Extract date from the document
    for page in document_result.pages:
        for line in page.lines:
            date = extract_date_from_text(line.content)
            if date:
                result["metadata"]["date"] = date
                break
        if result["metadata"]["date"]:
            break
    
    if not result["metadata"]["date"]:
        result["metadata"]["date"] = datetime.now().strftime('%Y-%m-%d')
    
    # Process tables and key-value pairs
    for table in document_result.tables:
        # Process table rows
        for cell in table.cells:
            if cell.kind == "columnHeader":
                # This is a header cell, check if it matches any category
                if cell.content.upper() == "HAEMATOLOGY":
                    continue
                elif cell.content in template["HAEMATOLOGY"]:
                    current_category = cell.content
                    result["HAEMATOLOGY"][current_category] = {
                        param: "N/A" for param in template["HAEMATOLOGY"][current_category]
                    }
            elif cell.kind == "data":
                # This is a data cell, try to match parameters
                for category in template["HAEMATOLOGY"]:
                    for param in template["HAEMATOLOGY"][category]:
                        # Create variations of the parameter name
                        param_variations = [
                            param.lower(),
                            param.lower().replace(" count", ""),
                            param.lower().replace("count", "").strip(),
                            param.lower().replace(" packed cell volume", ""),
                            param.lower().replace("pcv", "").strip(),
                            param.lower().replace(" platelet", ""),
                            param.lower().replace(" neutrophils", ""),
                            param.lower().replace(" lymphocytes", ""),
                            param.lower().replace(" eosinophils", ""),
                            param.lower().replace(" monocytes", ""),
                            param.lower().replace(" basophils", ""),
                            param.lower().replace(" mylocytes", ""),
                            param.lower().replace(" metamylocytes", ""),
                            param.lower().replace(" blast", ""),
                            param.lower().replace(" prothrombin time", ""),
                            param.lower().replace(" inr", ""),
                        ]
                        
                        # Check if any variation matches
                        for variation in param_variations:
                            if variation in cell.content.lower():
                                # Look for value in adjacent cells
                                for adjacent_cell in table.cells:
                                    if (adjacent_cell.row_index == cell.row_index and 
                                        adjacent_cell.column_index > cell.column_index):
                                        # Extract the value using regex
                                        value_match = re.search(
                                            r'[-+]?\d*\.?\d+(?:\s*[-–]\s*\d*\.?\d+)?(?:\s*[x×]\s*10\s*\^\s*\d+)?(?:\s*[a-zA-Z/%]+)?',
                                            adjacent_cell.content
                                        )
                                        if value_match:
                                            value = value_match.group(0).strip()
                                            value = value.replace('–', '-')
                                            value = value.replace('×', 'x')
                                            result["HAEMATOLOGY"][category][param] = value
                                            break
    
    return result

def process_file(file_path, output_dir="output"):
    """Process a file (PDF or image) and extract text using Document Intelligence."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize document client
        document_client = get_document_client()
        
        # Read the file
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Start the analysis
        poller = document_client.begin_analyze_document(
            "prebuilt-document", file_content
        )
        result = poller.result()
        
        # Parse the results
        structured_data = parse_medical_results(result)
        
        # Save both raw text and structured JSON
        output_text_file = os.path.join(output_dir, "extracted_text.txt")
        output_json_file = os.path.join(output_dir, "structured_results.json")
        
        # Save raw text
        with open(output_text_file, "w", encoding="utf-8") as f:
            for page in result.pages:
                for line in page.lines:
                    f.write(line.content + "\n")
        
        # Save structured JSON
        with open(output_json_file, "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=4)
        
        print(f"Text extraction complete. Results saved to:")
        print(f"- Raw text: {output_text_file}")
        print(f"- Structured JSON: {output_json_file}")
        return output_json_file
        
    except Exception as e:
        error_msg = str(e)
        if "endpoint" in error_msg.lower():
            error_msg = "Invalid Document Intelligence endpoint. Please check your AZURE_DOCUMENT_ENDPOINT in .env file"
        elif "key" in error_msg.lower():
            error_msg = "Invalid Document Intelligence key. Please check your AZURE_DOCUMENT_KEY in .env file"
        raise Exception(error_msg)

if __name__ == "__main__":
    # Create and hide the root window
    root = tk.Tk()
    root.withdraw()

    # Show file dialog
    file_path = filedialog.askopenfilename(
        title="Select PDF or Image file",
        filetypes=[
            ("All supported files", "*.pdf;*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.tif;*.gif"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.jpg;*.jpeg;*.png;*.bmp;*.tiff;*.tif;*.gif"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        print("No file selected. Exiting...")
        sys.exit(0)
    
    if not os.path.exists(file_path):
        messagebox.showerror("Error", f"File {file_path} does not exist")
        sys.exit(1)
    
    try:
        output_file = process_file(file_path)
        messagebox.showinfo("Success", f"Text extraction complete!\nResults saved to: {output_file}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")
        sys.exit(1) 