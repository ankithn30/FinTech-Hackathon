import os
import sys
import json
import concurrent.futures
import multiprocessing
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file
from werkzeug.utils import secure_filename
from llama_utils import create_dynamic_schema, parse_pdf_with_dynamic_schema
from pdfwriter import fill_pdf_from_llama
from schema_utils import compile_schemas
from agents_with_validation import process_forms_with_validation, MainAgent
from validation_engine import ValidationEngine
from batch_processor import BatchProcessor
from FormFIller import PyMuPDFTemporaryFiller, fill_forms_with_temporary_storage, preview_field_mappings

# Ensure we can import modules from the repository root (for llama_parser.py)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

try:
    from llama_parser import llama_parse, simplify_llama_output, filter_filled_fields
    LLAMA_PARSER_AVAILABLE = True
except Exception as _e:
    # Fall back if llama_parser has missing deps or cannot import
    LLAMA_PARSER_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Serve the consolidated financial dashboard as the primary interface"""
    return send_file('Frontend/index.html')

@app.route('/legacy')
def legacy():
    """Serve the legacy dashboard for reference"""
    return render_template('index.html')

@app.route('/frontend')
def frontend():
    """Redirect to main dashboard (for backward compatibility)"""
    return send_file('Frontend/index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        try:
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Try Llama parser first with a contact-info schema; fall back to PDF form extraction
            extracted_data = {}
            if LLAMA_PARSER_AVAILABLE:
                try:
                    # Define a simple schema for contact information extraction
                    schema_text = (
                        "I want to extract these fields:\n"
                        "name: Full legal name of the person or organization\n"
                        "phone_number: Primary phone number (digits, may include separators)\n"
                        "address: Full mailing address or location\n"
                        "email: Primary email address"
                    )
                    compiled_schema = compile_schemas([schema_text])
                    llama_results = llama_parse([filepath], compiled_schema)
                    
                    simplified = simplify_llama_output(llama_results)
                    print("=== EXTRACTED DATA (FILLED FIELDS ONLY) ===")
                    for field, value in simplified.items():
                        print(f"{field}: {value}")
                    print("=" * 45)
                    
                    if simplified:
                        extracted_data = simplified
                except Exception as _inner_e:
                    print(f"LlamaParser error: {_inner_e}")
                    extracted_data = {}
            
            # If llama parser unavailable or returned nothing, fall back to form-field extraction
            if not extracted_data:
                raw_form_data = parse_pdf_with_dynamic_schema(filepath)
                # Apply simplify_llama_output filtering to form data too
                extracted_data = simplify_llama_output(raw_form_data)
                print("=== PDF FORM EXTRACTION RESULTS (FILLED ONLY) ===")
                for field, value in extracted_data.items():
                    print(f"{field}: {value}")
                print("=" * 48)
            
    
            # Clean up uploaded file
            os.remove(filepath)

            # Create response with extracted data
            response = jsonify({
                'success': True,
                'data': extracted_data,
                'filename': filename
            })

            # Store extracted data in cookies (expires in 4 minutes)
            if extracted_data:
                # Convert data to JSON string for cookie storage
                cookie_data = json.dumps(extracted_data)
                response.set_cookie('extracted_data', cookie_data, max_age=240, httponly=False)
                response.set_cookie('has_data', 'true', max_age=240, httponly=False)

            return response

        except Exception as e:
            # Clean up file on error
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    flash('Invalid file type. Only PDF files are allowed.')
    return redirect(request.url)

@app.route('/custom-schema', methods=['POST'])
def update_schema():
    try:
        schema_data = request.json
        # LlamaParse does not support agents, so we only allow dynamic schema creation if needed
        create_dynamic_schema(schema_data)  # Create schema but don't store return value
        # You may want to store or use the schema elsewhere in future implementations
        return jsonify({'success': True, 'message': 'Schema updated successfully'})
    except Exception as e:
        print(f"Schema update error: {e}")  # Add logging
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get-stored-data')
def get_stored_data():
    """Get the stored extracted data from cookies"""
    try:
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')
        
        if has_data and extracted_data:
            data = json.loads(extracted_data)
            return jsonify({
                'success': True,
                'data': data,
                'has_data': True
            })
        else:
            return jsonify({
                'success': True,
                'data': None,
                'has_data': False
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/clear-stored-data')
def clear_stored_data():
    """Clear the stored extracted data from cookies"""
    response = jsonify({'success': True, 'message': 'Data cleared'})
    response.delete_cookie('extracted_data')
    response.delete_cookie('has_data')
    return response

@app.route('/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """
    Complete workflow: Multiple Documents → Main Agent → Sub-agents → 
    Schema Compilation → LlamaParse → Validation → Results
    """
    try:
        # Handle multiple file uploads
        if 'documents' not in request.files:
            return jsonify({'success': False, 'error': 'No documents uploaded'})
        
        files = request.files.getlist('documents')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'error': 'No documents selected'})
        
        # Save uploaded documents
        document_paths = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"doc_{filename}")
                file.save(filepath)
                document_paths.append(filepath)
        
        if not document_paths:
            return jsonify({'success': False, 'error': 'No valid PDF documents uploaded'})
        
        print(f"\n🚀 Starting complete workflow for {len(document_paths)} documents...")
        
        # Execute complete workflow with validation
        workflow_result = process_forms_with_validation(document_paths)
        
        # Clean up uploaded files
        for filepath in document_paths:
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Store results in session for form filling
        if workflow_result['status'] == 'success':
            compiled_schema = workflow_result['compiled_schema']
            validation_summary = workflow_result['validation_summary']
            
            # Store compiled schema and validation results
            response = jsonify({
                'success': True,
                'workflow_result': workflow_result,
                'message': f'Successfully processed {len(document_paths)} documents'
            })
            
            # Store in cookies for later use (expires in 4 minutes)
            cookie_data = json.dumps({
                'compiled_schema': compiled_schema,
                'validation_summary': validation_summary
            })
            response.set_cookie('workflow_data', cookie_data, max_age=240, httponly=False)
            response.set_cookie('has_workflow_data', 'true', max_age=240, httponly=False)
            
            return response
        else:
            return jsonify({
                'success': False,
                'error': workflow_result.get('message', 'Workflow processing failed')
            }), 500
            
    except Exception as e:
        # Clean up files on error
        for filepath in document_paths:
            if os.path.exists(filepath):
                os.remove(filepath)
        return jsonify({
            'success': False,
            'error': f'Workflow error: {str(e)}'
        }), 500

@app.route('/fill-multiple-forms', methods=['POST'])
def fill_multiple_forms():
    """
    Parallel PDF filling: Takes multiple forms and fills them with validated data
    """
    try:
        # Get workflow data from cookies
        workflow_data = request.cookies.get('workflow_data')
        has_workflow_data = request.cookies.get('has_workflow_data')
        
        if not has_workflow_data or not workflow_data:
            return jsonify({'success': False, 'error': 'No workflow data found. Please process documents first.'})
        
        workflow_info = json.loads(workflow_data)
        compiled_schema = workflow_info.get('compiled_schema', {})
        
        # Handle multiple form uploads
        if 'forms' not in request.files:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        form_files = request.files.getlist('forms')
        if not form_files or all(f.filename == '' for f in form_files):
            return jsonify({'success': False, 'error': 'No forms selected'})
        
        # Save form files
        form_paths = []
        for form_file in form_files:
            if form_file and allowed_file(form_file.filename):
                filename = secure_filename(form_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"form_{filename}")
                form_file.save(filepath)
                form_paths.append(filepath)
        
        if not form_paths:
            return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
        
        print(f"\n📄 Starting parallel PDF filling for {len(form_paths)} forms...")
        
        # Fill forms in parallel
        filled_forms = fill_multiple_pdfs_parallel(form_paths, compiled_schema)
        
        # Clean up form files
        for filepath in form_paths:
            if os.path.exists(filepath):
                os.remove(filepath)
        
        if filled_forms:
            # For now, return the first filled form (in production, you'd zip multiple files)
            first_filled = filled_forms[0]
            if os.path.exists(first_filled):
                return send_file(first_filled, as_attachment=True, 
                               download_name=f"filled_{os.path.basename(first_filled)}", 
                               mimetype='application/pdf')
        
        return jsonify({'success': False, 'error': 'Failed to fill PDF forms'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Form filling error: {str(e)}'
        }), 500

def fill_multiple_pdfs_parallel(form_paths, compiled_schema):
    """
    Fill multiple PDF forms in parallel using multiprocessing
    """
    def fill_single_form(args):
        form_path, schema_data = args
        try:
            # Extract field data from compiled schema
            form_data = {}
            for field in schema_data.get('fields', []):
                field_name = field.get('name', '')
                field_meaning = field.get('meaning', '')
                if field_name and field_meaning:
                    form_data[field_name] = field_meaning
            
            # Generate output path
            base_name = os.path.basename(form_path)
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"filled_{base_name}")
            
            # Fill the form
            success = fill_pdf_from_llama(form_data, form_path, output_path)
            return output_path if success else None
            
        except Exception as e:
            print(f"Error filling form {form_path}: {e}")
            return None
    
    # Prepare arguments for parallel processing
    args_list = [(form_path, compiled_schema) for form_path in form_paths]
    
    # Use ThreadPoolExecutor for parallel processing
    filled_forms = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(form_paths), 5)) as executor:
        results = executor.map(fill_single_form, args_list)
        filled_forms = [result for result in results if result is not None]
    
    print(f"✅ Successfully filled {len(filled_forms)} out of {len(form_paths)} forms")
    return filled_forms

@app.route('/batch-process', methods=['POST'])
def batch_process_web():
    """
    Web interface for batch processing - handles both documents and forms upload
    """
    try:
        # Handle multiple document uploads
        documents = request.files.getlist('documents') if 'documents' in request.files else []
        forms = request.files.getlist('forms') if 'forms' in request.files else []
        
        if not documents:
            return jsonify({'success': False, 'error': 'No documents uploaded'})
        
        if not forms:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        # Save uploaded documents
        document_paths = []
        for file in documents:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"batch_doc_{filename}")
                file.save(filepath)
                document_paths.append(filepath)
        
        # Save uploaded forms
        form_paths = []
        for file in forms:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"batch_form_{filename}")
                file.save(filepath)
                form_paths.append(filepath)
        
        if not document_paths:
            return jsonify({'success': False, 'error': 'No valid PDF documents uploaded'})
        
        if not form_paths:
            return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
        
        print(f"\n🚀 Starting web batch processing: {len(document_paths)} docs, {len(form_paths)} forms...")
        
        # Create temporary batch processor
        batch_processor = BatchProcessor(
            documents_folder=app.config['UPLOAD_FOLDER'],
            forms_folder=app.config['UPLOAD_FOLDER'],
            output_folder=os.path.join(app.config['UPLOAD_FOLDER'], 'batch_output')
        )
        
        # Process documents first
        workflow_result = process_forms_with_validation(document_paths)
        
        if workflow_result['status'] != 'success':
            # Clean up files
            for filepath in document_paths + form_paths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            return jsonify({
                'success': False,
                'error': f"Document processing failed: {workflow_result.get('message', 'Unknown error')}"
            }), 500
        
        # Fill forms with extracted data
        compiled_schema = workflow_result.get('compiled_schema', {})
        filled_forms = batch_processor.fill_forms_batch(form_paths, compiled_schema)
        
        # Clean up uploaded files
        for filepath in document_paths + form_paths:
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Generate response
        if filled_forms:
            # Create a zip file with all filled forms
            import zipfile
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"batch_filled_forms_{timestamp}.zip"
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for filled_form in filled_forms:
                    if os.path.exists(filled_form):
                        zipf.write(filled_form, os.path.basename(filled_form))
            
            return jsonify({
                'success': True,
                'message': f'Successfully processed {len(document_paths)} documents and filled {len(filled_forms)} forms',
                'filled_forms_count': len(filled_forms),
                'download_url': f'/download-batch-results/{zip_filename}',
                'workflow_summary': {
                    'documents_processed': len(document_paths),
                    'forms_filled': len(filled_forms),
                    'validation_summary': workflow_result.get('validation_summary', {})
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No forms were successfully filled'
            }), 500
            
    except Exception as e:
        # Clean up files on error
        try:
            for filepath in document_paths + form_paths:
                if os.path.exists(filepath):
                    os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'success': False,
            'error': f'Batch processing error: {str(e)}'
        }), 500

@app.route('/download-batch-results/<filename>')
def download_batch_results(filename):
    """Download batch processing results"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/batch-dashboard')
def batch_dashboard():
    """Serve the batch processing dashboard"""
    return render_template('batch_dashboard.html')

@app.route('/fill-pdf-form', methods=['POST'])
def fill_pdf_form():
    """Fill Sample.pdf form with extracted data from Llama schema"""
    # Get extracted data from cookies
    extracted_data = request.cookies.get('extracted_data')
    has_data = request.cookies.get('has_data')

    if not has_data or not extracted_data:
        return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})

    try:
        llama_data = json.loads(extracted_data)
    except Exception as e:
        return jsonify({'success': False, 'error': 'Invalid extracted data'})

    # Apply simplification and filtering to the data before filling
    simplified_data = simplify_llama_output(llama_data) if LLAMA_PARSER_AVAILABLE else llama_data
    print("=== DATA FOR PDF FILLING ===")
    for field, value in simplified_data.items():
        print(f"{field}: {value}")
    print("=" * 28)
   
    # Handle uploaded PDF form
    if 'form_pdf' not in request.files:
        return jsonify({'success': False, 'error': 'No PDF form uploaded'})
    form_pdf = request.files['form_pdf']
    if form_pdf.filename == '':
        return jsonify({'success': False, 'error': 'No PDF form selected'})
    if form_pdf and allowed_file(form_pdf.filename):
        try:
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"form_{filename}")
            form_pdf.save(form_filepath)
            output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"filled_{filename}")
            success = fill_pdf_from_llama(simplified_data, pdf_path=form_filepath, output_path=output_filepath)
            if success:
                return send_file(output_filepath, as_attachment=True, download_name=f"filled_{filename}", mimetype='application/pdf')
            else:
                return jsonify({'success': False, 'error': 'Failed to fill PDF form'})
        except Exception as e:
            if os.path.exists(form_filepath):
                os.remove(form_filepath)
            if os.path.exists(output_filepath):
                os.remove(output_filepath)
            return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})

@app.route('/fill-multiple-forms-single', methods=['POST'])
def fill_multiple_forms_single():
    """
    Fill multiple forms using data from a single document (for normal dashboard)
    """
    try:
        # Get extracted data from cookies
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')

        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})

        try:
            llama_data = json.loads(extracted_data)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid extracted data'})

        # Apply simplification and filtering to the data before filling
        simplified_data = simplify_llama_output(llama_data) if LLAMA_PARSER_AVAILABLE else llama_data
        
        # Handle multiple form uploads
        if 'forms' not in request.files:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        form_files = request.files.getlist('forms')
        if not form_files or all(f.filename == '' for f in form_files):
            return jsonify({'success': False, 'error': 'No forms selected'})
        
        # Save form files and fill them
        filled_forms = []
        form_paths = []
        
        for form_file in form_files:
            if form_file and allowed_file(form_file.filename):
                filename = secure_filename(form_file.filename)
                form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"multi_form_{filename}")
                form_file.save(form_filepath)
                form_paths.append(form_filepath)
                
                # Fill the form
                output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"filled_multi_{filename}")
                success = fill_pdf_from_llama(simplified_data, pdf_path=form_filepath, output_path=output_filepath)
                
                if success:
                    filled_forms.append(output_filepath)
        
        # Clean up form files
        for filepath in form_paths:
            if os.path.exists(filepath):
                os.remove(filepath)
        
        if filled_forms:
            # Create a zip file with all filled forms
            import zipfile
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"multiple_filled_forms_{timestamp}.zip"
            zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for filled_form in filled_forms:
                    if os.path.exists(filled_form):
                        zipf.write(filled_form, os.path.basename(filled_form))
            
            return jsonify({
                'success': True,
                'message': f'Successfully filled {len(filled_forms)} forms',
                'filled_forms_count': len(filled_forms),
                'download_url': f'/download-batch-results/{zip_filename}'
            })
        else:
            return jsonify({'success': False, 'error': 'No forms were successfully filled'})
            
    except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Multiple form filling error: {str(e)}'
            }), 500

@app.route('/semantic-form-fill', methods=['POST'])
def semantic_form_fill():
    """
    Fill PDF forms using the FormFIller semantic mapping system.
    Prevents incorrect field assignments by using semantic field matching.
    """
    try:
        # Get extracted data from cookies
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')

        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})

        try:
            llama_data = json.loads(extracted_data)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid extracted data'})

        # Apply simplification and filtering to the data before filling
        simplified_data = simplify_llama_output(llama_data) if LLAMA_PARSER_AVAILABLE else llama_data
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"semantic_form_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Use FormFIller for semantic form filling
                with PyMuPDFTemporaryFiller() as filler:
                    filled_path = filler.fill_single_form(simplified_data, form_filepath)
                    
                    if filled_path:
                        # Copy filled form to permanent location for download
                        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"semantic_filled_{filename}")
                        import shutil
                        shutil.copy2(filled_path, output_filepath)
                        
                        # Get processing stats
                        stats = filler.get_processing_stats()
                        
                        # Clean up uploaded form
                        if os.path.exists(form_filepath):
                            os.remove(form_filepath)
                        
                        return jsonify({
                            'success': True,
                            'message': f'Successfully filled form using semantic mapping',
                            'stats': {
                                'fields_filled': stats['fields_filled'],
                                'mapping_errors': stats['mapping_errors']
                            },
                            'download_url': f'/download-filled-form/{os.path.basename(output_filepath)}'
                        })
                    else:
                        return jsonify({'success': False, 'error': 'Failed to fill PDF form using semantic mapping'})
                        
            except Exception as e:
                # Clean up uploaded form
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({'success': False, 'error': f'Semantic form filling error: {str(e)}'})
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Semantic form filling error: {str(e)}'
        }), 500

@app.route('/semantic-batch-fill', methods=['POST'])
def semantic_batch_fill():
    """
    Fill multiple PDF forms using the FormFIller semantic mapping system.
    """
    try:
        # Get extracted data from cookies
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')

        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})

        try:
            llama_data = json.loads(extracted_data)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid extracted data'})

        # Apply simplification and filtering to the data before filling
        simplified_data = simplify_llama_output(llama_data) if LLAMA_PARSER_AVAILABLE else llama_data
        
        # Handle multiple form uploads
        if 'forms' not in request.files:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        form_files = request.files.getlist('forms')
        if not form_files or all(f.filename == '' for f in form_files):
            return jsonify({'success': False, 'error': 'No forms selected'})
        
        # Save form files
        form_paths = []
        for form_file in form_files:
            if form_file and allowed_file(form_file.filename):
                filename = secure_filename(form_file.filename)
                form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"semantic_batch_{filename}")
                form_file.save(form_filepath)
                form_paths.append(form_filepath)
        
        if not form_paths:
            return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
        
        try:
            # Use FormFIller for semantic batch form filling
            with PyMuPDFTemporaryFiller() as filler:
                filled_paths = filler.fill_forms_batch(simplified_data, form_paths)
                
                if filled_paths:
                    # Copy filled forms to permanent location
                    permanent_filled_forms = []
                    for i, filled_path in enumerate(filled_paths):
                        base_name = os.path.basename(form_paths[i])
                        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"semantic_batch_filled_{base_name}")
                        import shutil
                        shutil.copy2(filled_path, output_filepath)
                        permanent_filled_forms.append(output_filepath)
                    
                    # Get processing stats
                    stats = filler.get_processing_stats()
                    
                    # Clean up uploaded forms
                    for filepath in form_paths:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    
                    # Create a zip file with all filled forms
                    import zipfile
                    from datetime import datetime
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_filename = f"semantic_batch_filled_{timestamp}.zip"
                    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for filled_form in permanent_filled_forms:
                            if os.path.exists(filled_form):
                                zipf.write(filled_form, os.path.basename(filled_form))
                    
                    return jsonify({
                        'success': True,
                        'message': f'Successfully filled {len(filled_paths)} forms using semantic mapping',
                        'stats': {
                            'forms_processed': stats['forms_processed'],
                            'fields_filled': stats['fields_filled'],
                            'mapping_errors': stats['mapping_errors'],
                            'fill_errors': stats['fill_errors']
                        },
                        'filled_forms_count': len(filled_paths),
                        'download_url': f'/download-batch-results/{zip_filename}'
                    })
                else:
                    return jsonify({'success': False, 'error': 'No forms were successfully filled using semantic mapping'})
                    
        except Exception as e:
            # Clean up uploaded forms
            for filepath in form_paths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            return jsonify({'success': False, 'error': f'Semantic batch filling error: {str(e)}'})
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Semantic batch filling error: {str(e)}'
        }), 500

@app.route('/preview-field-mapping', methods=['POST'])
def preview_field_mapping():
    """
    Preview how extracted data would be mapped to form fields without actually filling.
    """
    try:
        # Get extracted data from cookies
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')

        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})

        try:
            llama_data = json.loads(extracted_data)
        except Exception as e:
            return jsonify({'success': False, 'error': 'Invalid extracted data'})

        # Apply simplification and filtering to the data before mapping
        simplified_data = simplify_llama_output(llama_data) if LLAMA_PARSER_AVAILABLE else llama_data
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"preview_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Use FormFIller to preview field mapping
                with PyMuPDFTemporaryFiller() as filler:
                    preview = filler.get_field_mapping_preview(simplified_data, form_filepath)
                    
                    # Clean up uploaded form
                    if os.path.exists(form_filepath):
                        os.remove(form_filepath)
                    
                    if "error" in preview:
                        return jsonify({'success': False, 'error': preview['error']})
                    
                    return jsonify({
                        'success': True,
                        'preview': preview,
                        'message': f'Field mapping preview for {filename}'
                    })
                        
            except Exception as e:
                # Clean up uploaded form
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({'success': False, 'error': f'Field mapping preview error: {str(e)}'})
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Field mapping preview error: {str(e)}'
        }), 500

@app.route('/download-filled-form/<filename>')
def download_filled_form(filename):
    """Download a single filled form"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
