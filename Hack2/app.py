import os
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file
from werkzeug.utils import secure_filename
from llama_utils import create_dynamic_schema, parse_pdf_with_dynamic_schema
from pdfwriter import fill_pdf_from_llama

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
    return render_template('index.html')

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
            
            # Extract data using dynamic schema based on PDF structure
            extracted_data = parse_pdf_with_dynamic_schema(filepath)

            # Clean up uploaded file
            os.remove(filepath)

            # Create response with extracted data
            response = jsonify({
                'success': True,
                'data': extracted_data,
                'filename': filename
            })

            # Store extracted data in cookies (expires in 1 hour)
            if extracted_data:
                # Convert data to JSON string for cookie storage
                cookie_data = json.dumps(extracted_data)
                response.set_cookie('extracted_data', cookie_data, max_age=3600, httponly=False)
                response.set_cookie('has_data', 'true', max_age=3600, httponly=False)

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
            success = fill_pdf_from_llama(llama_data, pdf_path=form_filepath, output_path=output_filepath)
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
