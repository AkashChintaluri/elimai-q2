# Medical Report OCR Application

A web application for extracting structured data from medical reports using Azure's Document Intelligence service. The application processes PDF files asynchronously and allows for incremental addition of documents to build a complete dataset.

## Features

- Upload and process multiple PDF files concurrently
- Asynchronous processing for better performance
- Add more PDFs to existing results
- Maintains data structure according to template
- Combines results from multiple documents intelligently
- Toggle between JSON and Pretty views
- Real-time processing status updates
- Session-based result management

## Project Structure

```
.
├── main.py              # Flask application with async endpoints
├── simple_ocr.py        # OCR processing logic
├── template.json        # Data structure template
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in repo)
└── templates/
    └── index.html       # Web interface
```

## Prerequisites

- Python 3.8 or higher
- Azure Document Intelligence service account
- Environment variables set up in `.env` file

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ocr-elimai
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Unix/MacOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your Azure credentials:
   ```
   AZURE_DI_ENDPOINT=your_endpoint
   AZURE_DI_KEY=your_key
   ```

## Running the Application

1. Start the Hypercorn server:
   ```bash
   hypercorn main:app --bind 0.0.0.0:8000
   ```

2. Access the application:
   - Open your browser and navigate to `http://localhost:8000`
   - The web interface will be available for PDF upload and processing

## Usage Guide

1. Initial Upload:
   - Click "Choose Files" to select one or more PDF files
   - Click "Process PDFs" to start processing
   - Wait for the results to appear

2. Adding More PDFs:
   - After initial processing, click "Add More PDFs"
   - Select additional PDF files
   - New results will be combined with existing data

3. Viewing Results:
   - Toggle between "JSON View" and "Pretty View"
   - JSON View shows the raw structured data
   - Pretty View displays a formatted table of results

## Data Structure

The application maintains a structured format for extracted data:

```json
{
  "metadata": {
    "date": "YYYY-MM-DD"
  },
  "HAEMATOLOGY": {
    "Complete Blood Count": {
      "WBC Count": "value",
      "RBC Count": "value",
      // ... other fields
    },
    "Differential Count": {
      "Neutrophils": "value",
      "Lymphocytes": "value",
      // ... other fields
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
- Invalid file types
- Missing files
- OCR processing failures
- Azure service errors
- Network issues

Errors are logged and displayed to the user with appropriate messages.

## Development Information

### Adding New Fields

To add new fields to the template:
1. Update `template.json` with new field definitions
2. The application will automatically include new fields in processing
3. Results will maintain the specified order

### Async Processing

The application uses:
- Flask with async support
- Hypercorn as the ASGI server
- ThreadPoolExecutor for CPU-bound tasks
- Asyncio for concurrent PDF processing

### Session Management

- Each upload session gets a unique ID
- Results are stored in memory
- Multiple users can process files concurrently
- Session data persists until server restart

## Troubleshooting

Common issues and solutions:

1. Server won't start:
   - Check if port 8000 is available
   - Verify all dependencies are installed
   - Ensure environment variables are set

2. PDF processing fails:
   - Verify PDF file is not corrupted
   - Check Azure service credentials
   - Ensure PDF is readable and contains text

3. Async errors:
   - Verify Flask async support is installed
   - Check Hypercorn is running
   - Ensure Python 3.8+ is being used

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Azure Document Intelligence for OCR capabilities
- Flask for the web framework
- Hypercorn for async server support
