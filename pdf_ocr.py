import os
import sys
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image
import io
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# Load environment variables
load_dotenv()

def convert_pdf_to_images(pdf_path):
    """Convert PDF to images using PyMuPDF."""
    try:
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        images = []
        
        # Convert each page to an image
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            # Get page as image with higher resolution
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        
        pdf_document.close()
        return images
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}")

def get_vision_client():
    """Create and return Azure Computer Vision client."""
    subscription_key = os.getenv('AZURE_VISION_KEY')
    endpoint = os.getenv('AZURE_VISION_ENDPOINT')
    
    if not subscription_key or not endpoint:
        raise ValueError("Please set AZURE_VISION_KEY and AZURE_VISION_ENDPOINT in .env file")
    
    return ComputerVisionClient(
        endpoint=endpoint,
        credentials=CognitiveServicesCredentials(subscription_key)
    )

def extract_text_from_image(vision_client, image):
    """Extract text from an image using Azure Computer Vision."""
    # Convert PIL Image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    read_response = vision_client.read_in_stream(io.BytesIO(img_byte_arr), raw=True)
    read_operation_location = read_response.headers["Operation-Location"]
    operation_id = read_operation_location.split("/")[-1]

    # Wait for the operation to complete
    while True:
        read_result = vision_client.get_read_result(operation_id)
        if read_result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    # Extract text from the result
    text = ""
    if read_result.status == OperationStatusCodes.succeeded:
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                text += line.text + "\n"
    return text

def process_pdf(pdf_path, output_dir="output"):
    """Process a PDF file and extract text from each page."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert PDF to images
    print(f"Converting PDF to images: {pdf_path}")
    images = convert_pdf_to_images(pdf_path)
    
    # Initialize vision client
    vision_client = get_vision_client()
    
    # Process each page
    all_text = []
    for i, image in enumerate(images):
        print(f"Processing page {i+1}/{len(images)}")
        text = extract_text_from_image(vision_client, image)
        all_text.append(text)
    
    # Save all extracted text
    output_file = os.path.join(output_dir, "extracted_text.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))
    
    print(f"Text extraction complete. Results saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    # Create and hide the root window
    root = tk.Tk()
    root.withdraw()

    # Show file dialog
    pdf_path = filedialog.askopenfilename(
        title="Select PDF file",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    
    if not pdf_path:
        print("No file selected. Exiting...")
        sys.exit(0)
    
    if not os.path.exists(pdf_path):
        messagebox.showerror("Error", f"File {pdf_path} does not exist")
        sys.exit(1)
    
    try:
        output_file = process_pdf(pdf_path)
        messagebox.showinfo("Success", f"Text extraction complete!\nResults saved to: {output_file}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")
        sys.exit(1) 