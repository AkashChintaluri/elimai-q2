# Medical Report OCR

A web application for extracting structured data from medical reports using Azure's Document Intelligence and Computer Vision services.

## Features

- Upload medical reports in various formats (PDF, PNG, JPG, BMP, TIFF, GIF)
- Extract structured data using two methods:
  - Document Intelligence (Form Recognizer)
  - Layout Analysis (Computer Vision)
- Compare results from both methods
- Download raw text output
- Modern, responsive web interface
- Drag-and-drop file upload

## Project Structure

```
.
├── app.py                 # Flask application
├── pdf_ocr.py            # Document Intelligence implementation
├── pdf_ocr_layout.py     # Layout Analysis implementation
├── medical_template.json # Template for structured data
├── requirements.txt      # Python dependencies
├── templates/           # HTML templates
│   └── index.html      # Main application page
├── static/             # Static files (CSS, JS)
├── uploads/            # Temporary storage for uploaded files
└── output/            # Storage for processed results
```

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
Create a `.env` file with your Azure credentials:
```
AZURE_FORM_RECOGNIZER_ENDPOINT=your_endpoint
AZURE_FORM_RECOGNIZER_KEY=your_key
AZURE_VISION_ENDPOINT=your_endpoint
AZURE_VISION_KEY=your_key
```

3. Run the application:
```bash
python app.py
```

4. Access the application at `http://localhost:5000`

## Usage

1. Open the web interface in your browser
2. Drag and drop a medical report file or click to select
3. Wait for the processing to complete
4. View the extracted data in the structured format
5. Compare results from both methods using the tabs
6. Download raw text output if needed

## Technologies Used

- Backend:
  - Flask (Python web framework)
  - Azure Document Intelligence
  - Azure Computer Vision
  - PyMuPDF (PDF processing)

- Frontend:
  - HTML5
  - Tailwind CSS
  - Vanilla JavaScript
  - Modern CSS features

## License

MIT License
