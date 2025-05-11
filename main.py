from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from simple_ocr import cached_extract_text
import tempfile
import shutil
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ocr', methods=['POST'])
def process_pdf():
    """
    Process a PDF file and return the extracted data
    """
    try:
        if 'file' not in request.files:
            logger.error("No file provided in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.error("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'File must be a PDF'}), 400

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            logger.debug(f"Created temporary file: {temp_file.name}")
            # Write the uploaded file to the temporary file
            shutil.copyfileobj(file.stream, temp_file)
            temp_file_path = temp_file.name

        try:
            logger.debug("Starting OCR processing")
            # Extract text from PDF
            result = cached_extract_text(temp_file_path)
            
            if result is None:
                logger.error("OCR processing returned None")
                return jsonify({'error': 'Failed to extract text from PDF'}), 400

            logger.debug("OCR processing completed successfully")
            return jsonify({
                'document_name': file.filename,
                'extracted_data': result['extracted_data']
            })

        except Exception as e:
            logger.error(f"Error during OCR processing: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f'OCR processing failed: {str(e)}'}), 500

        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)