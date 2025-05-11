from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from simple_ocr import cached_extract_text
import tempfile
import shutil
import logging
import traceback
from collections import OrderedDict
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Create a thread pool for CPU-bound tasks
thread_pool = ThreadPoolExecutor(max_workers=4)

# In-memory storage for results
session_results = {}

async def process_single_pdf(file, temp_file_path):
    """
    Process a single PDF file asynchronously
    """
    try:
        logger.debug(f"Starting OCR processing for {file.filename}")
        # Run the CPU-bound OCR processing in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            thread_pool,
            cached_extract_text,
            temp_file_path
        )
        
        if result is not None:
            logger.debug(f"Successfully processed {file.filename}")
            return file.filename, result
        else:
            logger.error(f"Failed to extract text from {file.filename}")
            return file.filename, {'error': 'Failed to extract text'}
            
    except Exception as e:
        logger.error(f"Error processing {file.filename}: {str(e)}")
        logger.error(traceback.format_exc())
        return file.filename, {'error': str(e)}

def combine_results(results):
    """
    Combine results from multiple documents
    """
    combined = OrderedDict([
        ("metadata", OrderedDict([
            ("date", None)
        ])),
        ("HAEMATOLOGY", OrderedDict([
            ("Complete Blood Count", OrderedDict()),
            ("Differential Count", OrderedDict()),
            ("Prothrombin Time", OrderedDict())
        ]))
    ])

    # Process each result
    for doc_name, result in results.items():
        if not result or 'extracted_data' not in result:
            continue

        data = result['extracted_data']
        
        # Update date if not set or if this document has a more recent date
        if data.get('metadata', {}).get('date'):
            if not combined['metadata']['date'] or data['metadata']['date'] > combined['metadata']['date']:
                combined['metadata']['date'] = data['metadata']['date']

        # Process each section
        for section in combined['HAEMATOLOGY']:
            if section in data.get('HAEMATOLOGY', {}):
                for field, value in data['HAEMATOLOGY'][section].items():
                    # Only update if the field is empty or if this value is more recent
                    if field not in combined['HAEMATOLOGY'][section] or value != 'N/A':
                        combined['HAEMATOLOGY'][section][field] = value

    return combined

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ocr', methods=['POST'])
async def process_pdf():
    """
    Process multiple PDF files concurrently and return the combined extracted data
    """
    try:
        if 'files' not in request.files:
            logger.error("No files provided in request")
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files:
            logger.error("Empty file list")
            return jsonify({'error': 'No files selected'}), 400

        # Generate a new session ID
        session_id = str(uuid.uuid4())
        results = {}
        temp_files = []
        tasks = []

        try:
            # Create temporary files and prepare tasks
            for file in files:
                if file.filename == '':
                    continue

                if not file.filename.lower().endswith('.pdf'):
                    logger.error(f"Invalid file type: {file.filename}")
                    continue

                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    logger.debug(f"Created temporary file: {temp_file.name}")
                    # Write the uploaded file to the temporary file
                    shutil.copyfileobj(file.stream, temp_file)
                    temp_file_path = temp_file.name
                    temp_files.append(temp_file_path)

                # Create task for processing this file
                task = asyncio.create_task(process_single_pdf(file, temp_file_path))
                tasks.append(task)

            # Wait for all tasks to complete
            completed_tasks = await asyncio.gather(*tasks)
            
            # Process results
            for filename, result in completed_tasks:
                results[filename] = result

            if not results:
                return jsonify({'error': 'No files were successfully processed'}), 400

            # Combine results from all documents
            combined_data = combine_results(results)
            
            # Store results in memory
            session_results[session_id] = {
                'document_names': list(results.keys()),
                'extracted_data': combined_data
            }
            
            return jsonify({
                'session_id': session_id,
                'document_names': list(results.keys()),
                'extracted_data': combined_data
            })

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file {temp_file}: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/ocr/append', methods=['POST'])
async def append_pdf():
    """
    Append new PDFs to existing results
    """
    try:
        if 'files' not in request.files:
            logger.error("No files provided in request")
            return jsonify({'error': 'No files provided'}), 400
        
        session_id = request.form.get('session_id')
        if not session_id or session_id not in session_results:
            logger.error("Invalid or missing session ID")
            return jsonify({'error': 'Invalid or missing session ID'}), 400

        files = request.files.getlist('files')
        if not files:
            logger.error("Empty file list")
            return jsonify({'error': 'No files selected'}), 400

        # Get existing results
        existing_results = session_results[session_id]
        results = {name: {'extracted_data': data} for name, data in zip(
            existing_results['document_names'],
            [existing_results['extracted_data']]
        )}
        
        temp_files = []
        tasks = []

        try:
            # Create temporary files and prepare tasks
            for file in files:
                if file.filename == '':
                    continue

                if not file.filename.lower().endswith('.pdf'):
                    logger.error(f"Invalid file type: {file.filename}")
                    continue

                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    logger.debug(f"Created temporary file: {temp_file.name}")
                    # Write the uploaded file to the temporary file
                    shutil.copyfileobj(file.stream, temp_file)
                    temp_file_path = temp_file.name
                    temp_files.append(temp_file_path)

                # Create task for processing this file
                task = asyncio.create_task(process_single_pdf(file, temp_file_path))
                tasks.append(task)

            # Wait for all tasks to complete
            completed_tasks = await asyncio.gather(*tasks)
            
            # Process results
            for filename, result in completed_tasks:
                results[filename] = result

            if not results:
                return jsonify({'error': 'No files were successfully processed'}), 400

            # Combine results from all documents
            combined_data = combine_results(results)
            
            # Update stored results
            session_results[session_id] = {
                'document_names': list(results.keys()),
                'extracted_data': combined_data
            }
            
            return jsonify({
                'session_id': session_id,
                'document_names': list(results.keys()),
                'extracted_data': combined_data
            })

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file {temp_file}: {str(e)}")

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