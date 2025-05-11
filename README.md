# PDF OCR using Azure Computer Vision

This application uses Azure's Computer Vision API to perform OCR (Optical Character Recognition) on PDF documents.

## Prerequisites

1. Python 3.7 or higher
2. Azure Computer Vision API subscription

## Setup

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root with your Azure credentials:
   ```
   AZURE_VISION_KEY=your_subscription_key
   AZURE_VISION_ENDPOINT=your_endpoint_url
   ```

## Usage

Simply run the script:
```bash
python pdf_ocr.py
```

A file browser window will open where you can select your PDF file. The extracted text will be saved in the `output/extracted_text.txt` file.

## How it Works

1. A file browser dialog opens for selecting the PDF file
2. The PDF is converted to high-quality images using PyMuPDF
3. Each image is processed using Azure Computer Vision API
4. The extracted text from all pages is combined and saved to a text file
5. A success message shows the location of the output file

## Technical Details

- Uses PyMuPDF (fitz) for PDF to image conversion
- Images are converted at 300 DPI for optimal OCR results
- No temporary files are created during processing
- Memory-efficient processing of large PDFs
