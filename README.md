# Medical Report OCR

A web application for extracting structured data from medical reports using Azure's Document Intelligence service. The application processes PDF files and extracts specific medical test results in a structured format.

## Features

- Upload and process medical report PDFs
- Extract structured data using Azure Document Intelligence
- Display results in both JSON and formatted table views
- Maintain exact data structure as per template
- Real-time processing with loading indicators
- Responsive web interface

## Project Structure

```
.
├── main.py              # Flask backend server
├── simple_ocr.py        # OCR processing logic
├── template.json        # Data structure template
├── requirements.txt     # Python dependencies
├── templates/          # HTML templates
│   └── index.html      # Main application page
└── .env               # Environment variables (create this)
```

## Prerequisites

- Python 3.8 or higher
- Azure Document Intelligence service account
- Modern web browser

## Setup

1. Clone the repository:
```bash
git clone https://github.com/AkashChintaluri/elimai-q2
cd elimai-q2
```

2. Create a virtual environment and activate it:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your Azure credentials:
```
AZURE_DI_ENDPOINT=your_endpoint_here
AZURE_DI_KEY=your_key_here
```

## Running the Application

1. Start the Flask server:
```bash
python main.py
```

2. Open your web browser and navigate to:
```
http://localhost:8000
```

## Usage

1. On the web interface, click "Choose File" to select a medical report PDF
2. Click "Process PDF" to start the extraction
3. Wait for the processing to complete
4. View the results in either:
   - JSON View: Raw structured data
   - Pretty View: Formatted table view

## Data Structure

The application extracts data according to the following structure:

```json
{
    "metadata": {
        "date": "YYYY-MM-DD"
    },
    "HAEMATOLOGY": {
        "Complete Blood Count": {
            "WBC Count": "value",
            "RBC Count": "value",
            "Hemoglobin": "value",
            "Packed Cell Volume [PCV]": "value",
            "Platelet Count": "value"
        },
        "Differential Count": {
            "Neutrophils": "value",
            "Lymphocytes": "value",
            "Eosinophils": "value",
            "Monocytes": "value",
            "Basophils": "value",
            "Mylocytes": "value",
            "Metamylocytes": "value",
            "Blast": "value"
        },
        "Prothrombin Time": {
            "Test": "value",
            "Control": "value",
            "INR": "value"
        }
    }
}
```

## Error Handling

The application handles various error cases:
- Invalid file types (only PDFs accepted)
- Missing or invalid Azure credentials
- OCR processing failures
- File access issues

## Development

### Adding New Fields

To add new fields to the extraction:
1. Update `template.json` with the new field structure
2. Add corresponding term variations in `TERM_VARIATIONS` in `simple_ocr.py`
3. Update the frontend template in `templates/index.html`

### Modifying the Template

The template structure can be modified by editing `template.json`. The application will automatically maintain the order of fields as specified in the template.

## Troubleshooting

1. If you get a "Resource not found" error:
   - Verify your Azure Document Intelligence endpoint and key
   - Ensure the service is properly provisioned

2. If processing fails:
   - Check if the PDF is readable and not corrupted
   - Verify the PDF contains text (not just images)
   - Check the application logs for detailed error messages

3. If the web interface doesn't load:
   - Ensure the Flask server is running
   - Check if port 8000 is available
   - Verify all dependencies are installed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Azure Document Intelligence service
- Flask web framework
- Bootstrap for the UI
