from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import re
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from collections import OrderedDict

# Load environment variables
load_dotenv()

# Azure Document Intelligence configuration
AZURE_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_DI_KEY")

if not AZURE_ENDPOINT or not AZURE_KEY:
    raise ValueError("Azure Document Intelligence endpoint or key not found in environment variables")

# Initialize the client
client = DocumentIntelligenceClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(AZURE_KEY)
)

# Load template
with open("template.json", "r") as f:
    TEMPLATE = json.load(f)

# Define term variations
TERM_VARIATIONS = {
    # Complete Blood Count variations
    "WBC Count": ["wbc", "wbc count", "white blood cell", "white blood cell count", "leucocyte", "leucocyte count", "total leukocyte count", "total leucocyte count", "total leucocyte"],
    "RBC Count": ["rbc", "rbc count", "red blood cell", "red blood cell count", "erythrocyte", "erythrocyte count", "total rbc count", "total rbc"],
    "Hemoglobin": ["hgb", "hb", "hemoglobin", "haemoglobin", "hemoglobin value"],
    "Packed Cell Volume [PCV]": ["pcv", "packed cell volume", "hematocrit", "haematocrit", "hct", "hematocrit value"],
    "Platelet Count": ["platelet", "platelet count", "plt", "thrombocyte", "thrombocyte count"],

    # Differential Count variations
    "Neutrophils": ["neutrophil", "neutrophils", "neut", "polymorphs", "polymorphonuclear"],
    "Lymphocytes": ["lymphocyte", "lymphocytes", "lymph", "lymphs", "lymphocyte l"],
    "Eosinophils": ["eosinophil", "eosinophils", "eos"],
    "Monocytes": ["monocyte", "monocytes", "mono", "monocytes l"],
    "Basophils": ["basophil", "basophils", "baso"],
    "Mylocytes": ["mylocyte", "mylocytes", "myelo"],
    "Metamylocytes": ["metamylocyte", "metamylocytes", "meta"],
    "Blast": ["blast", "blasts", "blast cells"],

    # Prothrombin Time variations
    "Test": ["pt", "prothrombin time", "test", "pt test"],
    "Control": ["control", "pt control", "control value"],
    "INR": ["inr", "international normalized ratio"]
}

def extract_date_from_text(text):
    """
    Extract date from text using common date patterns
    """
    # Common date patterns
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or DD-MM-YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',  # DD Month YYYY
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}'  # Month DD, YYYY
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                # Try to parse the first match
                date_str = matches[0]
                # Handle different date formats
                if '/' in date_str or '-' in date_str:
                    # DD/MM/YYYY or DD-MM-YYYY
                    parts = re.split('[/-]', date_str)
                    if len(parts) == 3:
                        day, month, year = parts
                        if len(year) == 2:
                            year = '20' + year
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    # Try to parse with dateutil
                    from dateutil import parser
                    return parser.parse(date_str).strftime('%Y-%m-%d')
            except:
                continue
    
    # If no date found, return current date
    return datetime.now().strftime('%Y-%m-%d')

# Cache for processed results
@lru_cache(maxsize=100)
def cached_extract_text(pdf_path):
    """
    Cached version of text extraction to avoid reprocessing the same file
    """
    return extract_text_from_pdf(pdf_path)

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using Azure Document Intelligence
    """
    try:
        # Check if file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Check if file is readable
        if not os.access(pdf_path, os.R_OK):
            raise PermissionError(f"Cannot read PDF file: {pdf_path}")

        # Check file size
        file_size = os.path.getsize(pdf_path)
        if file_size == 0:
            raise ValueError(f"PDF file is empty: {pdf_path}")

        print("Starting OCR operation...")
        # Start async OCR operation with the file path
        with open(pdf_path, "rb") as image_file:
            # Use Document Intelligence for document analysis
            operation = client.begin_analyze_document(
                "prebuilt-read",
                image_file
            )
            
            # Wait for the operation to complete
            result = operation.result()
            
            if result:
                print("OCR operation completed successfully")
                # Extract text from all pages using list comprehension for better performance
                extracted_text = "\n".join(
                    line.content
                    for page in result.pages
                    for line in page.lines
                )
                
                if not extracted_text.strip():
                    raise ValueError("No text could be extracted from the PDF")
                
                print(f"Extracted text length: {len(extracted_text)} characters")
                
                # Process the text with template
                extracted_data = match_template(extracted_text)
                
                return {
                    "raw_text": extracted_text,
                    "extracted_data": extracted_data
                }
            else:
                raise Exception("OCR operation failed - no result returned")
                
    except FileNotFoundError as e:
        print(f"File Error: {str(e)}")
        return None
    except PermissionError as e:
        print(f"Permission Error: {str(e)}")
        return None
    except ValueError as e:
        print(f"Value Error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return None

def find_value_for_term(lines, term_variations, current_index):
    """
    Find the value for a term considering all its variations
    """
    current_line = lines[current_index].lower()
    
    # Try each variation of the term
    for variation in term_variations:
        if variation in current_line:
            try:
                # Look at the next few lines for the value
                for i in range(current_index + 1, min(current_index + 4, len(lines))):
                    next_line = lines[i].strip()
                    # Use regex directly for better performance
                    match = re.search(r'[-+]?\d*\.?\d+', next_line)
                    if match:
                        return match.group()
            except:
                continue
    
    return None

def match_template(text):
    """
    Match extracted text against the template and return structured data
    """
    # Initialize result with template structure using OrderedDict
    result = OrderedDict([
        ("metadata", OrderedDict([
            ("date", extract_date_from_text(text))
        ])),
        ("HAEMATOLOGY", OrderedDict([
            ("Complete Blood Count", OrderedDict()),
            ("Differential Count", OrderedDict()),
            ("Prothrombin Time", OrderedDict())
        ]))
    ])
    
    errors = []
    # Split text into lines and clean them - do this once
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Process each section in the exact order from template
    for section, fields in TEMPLATE["HAEMATOLOGY"].items():
        # Process fields in the exact order from template
        for field in fields:
            found = False
            for i, line in enumerate(lines):
                value = find_value_for_term(lines, TERM_VARIATIONS[field], i)
                if value:
                    result["HAEMATOLOGY"][section][field] = value
                    found = True
                    break
            
            if not found:
                result["HAEMATOLOGY"][section][field] = "N/A"
                errors.append(f"No value found for {field}")
    
    return result

def process_pdf(pdf_path):
    """
    Process a PDF file and return the extracted data
    """
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    if text is None:
        return {
            "document_name": os.path.basename(pdf_path),
            "error": "Failed to extract text from PDF. Please check if the file is valid and readable.",
            "extracted_data": None
        }
    
    # Match against template
    result = match_template(text)
    
    return {
        "document_name": os.path.basename(pdf_path),
        "extracted_data": result
    }

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical Report OCR")
        self.root.geometry("800x600")
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File selection
        ttk.Label(main_frame, text="Select PDF File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.file_path = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.file_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_file).grid(row=0, column=2)
        
        # Process button
        ttk.Button(main_frame, text="Process PDF", command=self.process_file).grid(row=1, column=1, pady=10)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, length=300, mode='indeterminate')
        self.progress.grid(row=2, column=0, columnspan=3, pady=5)
        
        # Raw OCR text area
        ttk.Label(main_frame, text="Raw OCR Text:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.raw_text = scrolledtext.ScrolledText(main_frame, width=80, height=15)
        self.raw_text.grid(row=4, column=0, columnspan=3, pady=5)
        
        # Results text area
        ttk.Label(main_frame, text="Results:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.results_text = scrolledtext.ScrolledText(main_frame, width=80, height=15)
        self.results_text.grid(row=6, column=0, columnspan=3, pady=5)
        
        # Status label
        self.status_var = tk.StringVar()
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, pady=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        
        # Store raw OCR text
        self.raw_ocr_text = ""
        
        # Create thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.file_path.set(filename)

    def process_file(self):
        pdf_path = self.file_path.get()
        if not pdf_path:
            self.status_var.set("Please select a PDF file")
            return
        
        if not pdf_path.lower().endswith('.pdf'):
            self.status_var.set("Please select a PDF file")
            return
        
        # Clear previous results
        self.results_text.delete(1.0, tk.END)
        self.raw_text.delete(1.0, tk.END)
        self.status_var.set("Processing...")
        self.progress.start()
        
        # Process in a separate thread
        threading.Thread(target=self.process_in_thread, args=(pdf_path,), daemon=True).start()

    def process_in_thread(self, pdf_path):
        try:
            # First get the raw OCR text using cached version
            self.raw_ocr_text = cached_extract_text(pdf_path)
            if self.raw_ocr_text is None:
                self.root.after(0, self.show_error, "Failed to extract text from PDF")
                return
                
            # Update raw text display
            self.root.after(0, self.update_raw_text)
            
            # Then process with template
            result = process_pdf(pdf_path)
            self.root.after(0, self.update_results, result)
        except Exception as e:
            self.root.after(0, self.show_error, str(e))

    def update_results(self, result):
        self.progress.stop()
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, json.dumps(result, indent=2))
        self.status_var.set("Processing complete")

    def update_raw_text(self):
        self.raw_text.delete(1.0, tk.END)
        if self.raw_ocr_text:
            self.raw_text.insert(tk.END, self.raw_ocr_text)
        else:
            self.raw_text.insert(tk.END, "No text was extracted from the PDF")

    def show_error(self, error_message):
        self.progress.stop()
        self.status_var.set(f"Error: {error_message}")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, json.dumps({
            "document_name": os.path.basename(self.file_path.get()),
            "error": error_message,
            "extracted_data": None
        }, indent=2))
        # Also show the error in the raw text area
        self.raw_text.delete(1.0, tk.END)
        self.raw_text.insert(tk.END, f"Error during OCR: {error_message}\n\nRaw text (if any):\n{self.raw_ocr_text}")

    def __del__(self):
        # Clean up thread pool
        self.executor.shutdown(wait=False)

if __name__ == "__main__":
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop() 