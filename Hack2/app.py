import os
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file
from werkzeug.utils import secure_filename
from llama_cloud_services import LlamaExtract
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import tempfile

# Load environment variables
load_dotenv()

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

# Initialize LlamaCloud extractor
def get_extractor():
    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set")
    return LlamaExtract()

# Define default schema for contact information extraction
class ContactInfo(BaseModel):
    name: str = Field(description="Full name of person")
    phone_number: str = Field(description="Phone number")
    address: str = Field(description="Full address or location")
    email: str = Field(description="Email address")

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
        fields = {}
        for field_name, field_info in schema_data.items():
            field_type = str if field_info.get('type') == 'string' else list[str] if field_info.get('type') == 'list' else str
            description = field_info.get('description', '')
            fields[field_name] = (field_type, Field(description=description))
        
        # Create dynamic class
        DynamicSchema = type('DynamicSchema', (BaseModel,), fields)
        
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
    """Fill a PDF form with extracted data"""
    if 'form_pdf' not in request.files:
        return jsonify({'success': False, 'error': 'No PDF form uploaded'})
    
    form_pdf = request.files['form_pdf']
    if form_pdf.filename == '':
        return jsonify({'success': False, 'error': 'No PDF form selected'})
    
    if form_pdf and allowed_file(form_pdf.filename):
        try:
            # Get extracted data from cookies
            extracted_data = request.cookies.get('extracted_data')
            has_data = request.cookies.get('has_data')
            
            if not has_data or not extracted_data:
                return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})
            
            data = json.loads(extracted_data)
            
            # Save the form PDF temporarily
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"form_{filename}")
            form_pdf.save(form_filepath)
            
            # For now, we'll create a simple filled PDF using reportlab
            # In a production environment, you might want to use PyPDF2 or similar
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                
                # Create output filename
                output_filename = f"filled_{filename}"
                output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
                
                # Create PDF with extracted data
                doc = SimpleDocTemplate(output_filepath, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                
                # Add title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=30,
                    alignment=1  # Center alignment
                )
                story.append(Paragraph("Filled Contact Information Form", title_style))
                story.append(Spacer(1, 20))
                
                # Add extracted data
                data_style = ParagraphStyle(
                    'DataStyle',
                    parent=styles['Normal'],
                    fontSize=12,
                    spaceAfter=15,
                    leftIndent=50
                )
                
                story.append(Paragraph(f"<b>Name:</b> {data.get('name', 'N/A')}", data_style))
                story.append(Paragraph(f"<b>Phone Number:</b> {data.get('phone_number', 'N/A')}", data_style))
                story.append(Paragraph(f"<b>Address:</b> {data.get('address', 'N/A')}", data_style))
                story.append(Paragraph(f"<b>Email:</b> {data.get('email', 'N/A')}", data_style))
                
                # Build PDF
                doc.build(story)
                
                # Clean up form PDF
                os.remove(form_filepath)
                
                # Return the filled PDF
                return send_file(
                    output_filepath,
                    as_attachment=True,
                    download_name=output_filename,
                    mimetype='application/pdf'
                )
                
            except ImportError:
                # Fallback if reportlab is not available
                return jsonify({
                    'success': False, 
                    'error': 'PDF generation library not available. Please install reportlab: pip install reportlab'
                })
                
        except Exception as e:
            # Clean up files on error
            if os.path.exists(form_filepath):
                os.remove(form_filepath)
            if 'output_filepath' in locals() and os.path.exists(output_filepath):
                os.remove(output_filepath)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
