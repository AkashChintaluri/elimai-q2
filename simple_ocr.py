import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mistralai import Mistral
from mistralai.models import APIEndpoint
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any, Optional
import re
import traceback
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize Mistral client
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("Mistral API key not found in environment variables")

client = Mistral(api_key=MISTRAL_API_KEY)

# Create necessary directories
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load template
try:
    with open("template.json", "r") as f:
        TEMPLATE = json.load(f)
except Exception as e:
    print(f"Error loading template: {str(e)}")
    TEMPLATE = {
        "HAEMATOLOGY": {
            "Complete Blood Count": [
                "WBC Count",
                "RBC Count",
                "Hemoglobin",
                "Packed Cell Volume [PCV]",
                "Platelet Count"
            ],
            "Differential Count": [
                "Neutrophils",
                "Lymphocytes",
                "Eosinophils",
                "Monocytes",
                "Basophils",
                "Mylocytes",
                "Blast"
            ],
            "Prothrombin Time": [
                "Test",
                "Control",
                "INR"
            ]
        }
    }

def extract_data_from_text(text: str) -> dict[str, any]:
    """Extract relevant data from OCR text based on template structure."""
    try:
        result = {}
        print(f"Extracting data from text (length: {len(text)} characters)")
        
        # Process each main section in the template
        for section_name, section_data in TEMPLATE.items():
            if section_name == "metadata":
                continue
                
            result[section_name] = {}
            
            # Process each subsection in the section
            for subsection_name, tests in section_data.items():
                result[section_name][subsection_name] = []
                
                # Process each test in the subsection
                for test in tests:
                    try:
                        # Find the test name in the text
                        test_pattern = re.compile(f"{re.escape(test)}[:\\s]+", re.IGNORECASE)
                        test_match = test_pattern.search(text)
                        
                        value = "N/A"
                        if test_match:
                            print(f"Found test: {test} at position {test_match.start()}")
                            # Get the text after the test name
                            start_pos = test_match.end()
                            remaining_text = text[start_pos:start_pos+100]  # Limit for logging
                            print(f"Text after {test}: {remaining_text}")
                            
                            # Find the first numerical value
                            value_match = re.search(r'\d+\.?\d*', text[start_pos:])
                            if value_match:
                                value = float(value_match.group())
                                print(f"Extracted value for {test}: {value}")
                                
                        result[section_name][subsection_name].append({
                            "name": test,
                            "value": value
                        })
                    except Exception as e:
                        print(f"Error extracting {test} in {subsection_name}: {str(e)}")
                        result[section_name][subsection_name].append({
                            "name": test,
                            "value": "N/A"
                        })
        
        print(f"Extracted structured data: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"Error in extract_data_from_text: {str(e)}")
        print(traceback.format_exc())
        return {}

async def process_file_async(content: bytes, filename: str):
    """Process a single file asynchronously."""
    try:
        # Save the uploaded file
        file_path = UPLOAD_DIR / filename
        with open(file_path, "wb") as f:
            f.write(content)
        print("File saved successfully")
        
        # Upload to Mistral
        with open(file_path, "rb") as f:
            print("Uploading to Mistral...")
            uploaded_file = client.files.upload(
                file={
                    "file_name": filename,
                    "content": f,
                },
                purpose="ocr"
            )
            print(f"File uploaded to Mistral: {uploaded_file.id}")
        
        # Get signed URL
        print("Getting signed URL...")
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
        print(f"Signed URL: {signed_url.url}")
        
        # Process with OCR
        print("Processing OCR...")
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": signed_url.url
            }
        )
        print("OCR processing complete")
        
        # Extract text from all pages
        if not hasattr(ocr_response, 'pages') or not ocr_response.pages:
            error_msg = "No pages found in OCR response"
            print(error_msg)
            return {
                "metadata": {
                    "date": datetime.now().isoformat(),
                    "filename": filename,
                    "error": error_msg
                },
                "content": {
                    "extracted_text": "",
                    "structured_data": {}
                }
            }
        
        # Combine text from all pages
        extracted_text = "\n".join(page.markdown for page in ocr_response.pages)
        print(f"Extracted text (first 500 chars): {extracted_text[:500]}")
        print(f"Total extracted text length: {len(extracted_text)} characters")
        
        # Extract structured data based on template
        print("Extracting structured data...")
        try:
            structured_data = extract_data_from_text(extracted_text)
        except Exception as e:
            print(f"Error extracting structured data: {str(e)}")
            structured_data = {}
        print("Structured data extraction complete")
        
        # Prepare metadata
        metadata = {
            "date": datetime.now().isoformat(),
            "filename": filename,
            "model": "mistral-ocr-latest",
            "pages_processed": len(ocr_response.pages),
            "document_size": len(content)
        }
        
        # Prepare result
        result = {
            "metadata": metadata,
            "content": {
                "extracted_text": extracted_text,
                "structured_data": structured_data or {}
            }
        }
        
        print(f"Processing complete for {filename}")
        return result
        
    except Exception as e:
        print(f"Error in async processing of {filename}: {str(e)}")
        print(traceback.format_exc())
        return {
            "metadata": {
                "date": datetime.now().isoformat(),
                "filename": filename,
                "error": str(e)
            },
            "content": {
                "extracted_text": "",
                "structured_data": {}
            }
        }
    finally:
        # Clean up the temporary file
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"Cleaned up {filename}")
        except Exception as e:
            print(f"Error cleaning up {filename}: {str(e)}")

@app.post("/upload/")
async def upload_file(file: UploadFile):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Read file content
        content = await file.read()
        
        # Process file asynchronously
        result = await process_file_async(content, file.filename)
        return result
        
    except Exception as e:
        print(f"Error processing {file.filename}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/template/")
async def get_template():
    try:
        with open("template.json", "r") as f:
            template = json.load(f)
        return template
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template file not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid template file format")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)