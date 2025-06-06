
import os
import json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from mistralai import Mistral
import asyncio
from typing import List, Dict, Any
import re
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Initialize Mistral client
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise ValueError("Mistral API key not found in environment variables")

client = Mistral(api_key=MISTRAL_API_KEY)

# Cache template at startup
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

def extract_test_value(test, text, pattern_cache):
    try:
        test_pattern = pattern_cache.get(test, re.compile(f"{re.escape(test)}[:\\s]+", re.IGNORECASE))
        pattern_cache[test] = test_pattern
        test_match = test_pattern.search(text)
        value = "N/A"
        if test_match:
            start_pos = test_match.end()
            value_match = re.search(r'\d+\.?\d*', text[start_pos:])
            if value_match:
                value = float(value_match.group())
        return test, value
    except Exception as e:
        print(f"Error extracting {test}: {str(e)}")
        return test, "N/A"

def extract_data_from_text(text: str) -> dict[str, any]:
    try:
        result = {}
        pattern_cache = {}
        for section_name, section_data in TEMPLATE.items():
            if section_name == "metadata":
                continue
            result[section_name] = {}
            for subsection_name, tests in section_data.items():
                result[section_name][subsection_name] = []
                with ThreadPoolExecutor() as executor:
                    test_results = executor.map(lambda test: extract_test_value(test, text, pattern_cache), tests)
                    for test, value in test_results:
                        result[section_name][subsection_name].append({
                            "name": test,
                            "value": value
                        })
        return result
    except Exception as e:
        print(f"Error in extract_data_from_text: {str(e)}")
        print(traceback.format_exc())
        return {}

async def process_file_async(content: bytes, filename: str):
    try:
        print(f"Processing {filename}...")
        # Upload file content as bytes
        uploaded_file = client.files.upload(
            file={
                "file_name": filename,
                "content": content,  # Use raw bytes instead of BytesIO
            },
            purpose="ocr"
        )
        print(f"File uploaded: {uploaded_file.id}")
        
        # Get signed URL for OCR processing
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
        print(f"Signed URL: {signed_url.url}")
        
        # Process with OCR
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": signed_url.url
            }
        )
        print("OCR processing complete")
        
        extracted_text = "\n".join(page.markdown for page in ocr_response.pages) if hasattr(ocr_response, 'pages') else ""
        structured_data = extract_data_from_text(extracted_text) if extracted_text else {}
        
        return {
            "metadata": {
                "date": datetime.now().isoformat(),
                "filename": filename,
                "model": "mistral-ocr-latest",
                "pages_processed": len(ocr_response.pages) if hasattr(ocr_response, 'pages') else 0,
                "document_size": len(content)
            },
            "content": {
                "extracted_text": extracted_text,
                "structured_data": structured_data
            }
        }
    except Exception as e:
        print(f"Error processing {filename}: {str(e)}")
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

@app.post("/upload/batch/")
async def upload_files(files: List[UploadFile]):
    try:
        tasks = [process_file_async(await file.read(), file.filename) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {"results": [result for result in results if not isinstance(result, Exception)]}
    except Exception as e:
        print(f"Error processing batch: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/template/")
async def get_template():
    return TEMPLATE

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)