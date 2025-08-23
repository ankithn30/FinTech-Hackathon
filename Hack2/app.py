import os
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file
from werkzeug.utils import secure_filename
from llama_utils import get_extractor, ContactInfo, create_dynamic_schema
from pdfwriter import fill_pdf_from_llama
import tempfile

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
            
            # Extract data using LlamaCloud
            extractor = get_extractor()
            
            # Create or get extraction agent
            try:
                agent = extractor.get_agent(name="contact-parser")
            except:
                # Create new agent if it doesn't exist
                agent = extractor.create_agent(name="contact-parser", data_schema=ContactInfo)
            
            # Extract data from PDF
            result = agent.extract(filepath)
            
            # Clean up uploaded file
            os.remove(filepath)
            
            # Create response with extracted data
            response = jsonify({
                'success': True,
                'data': result.data,
                'filename': filename
            })
            
            # Store extracted data in cookies (expires in 1 hour)
            if result.data:
                # Convert data to JSON string for cookie storage
                cookie_data = json.dumps(result.data)
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
        extractor = get_extractor()

        # Create dynamic schema class with proper type annotations
        DynamicSchema = create_dynamic_schema(schema_data)

        # Update agent with new schema
        try:
            agent = extractor.get_agent(name="custom-parser")
        except:
            agent = extractor.create_agent(name="custom-parser", data_schema=DynamicSchema)

        agent.data_schema = DynamicSchema
        agent.save()

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

    # Fill Sample.pdf using pdfwriter
    pdf_path = os.path.join('Hack2', 'Sample.pdf')
    output_path = os.path.join('Hack2', 'Sample_filled_pdfrw.pdf')
    try:
        success = fill_pdf_from_llama(llama_data, pdf_path=pdf_path, output_path=output_path)
        if success:
            return send_file(output_path, as_attachment=True, download_name='Sample_filled_pdfrw.pdf', mimetype='application/pdf')
        else:
            return jsonify({'success': False, 'error': 'Failed to fill PDF form'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
