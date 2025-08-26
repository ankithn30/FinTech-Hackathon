import os
import sys
import json
import concurrent.futures
import multiprocessing
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import base64
from datetime import datetime

# Import new OpenAI agents
from openai_agent_coordinator import OpenAIAgentCoordinator
from openai_form_filling_agent_web import OpenAIFormFillingAgentWeb

# Keep legacy imports for backward compatibility
try:
    from llama_utils import create_dynamic_schema, parse_pdf_with_dynamic_schema
    from pdfwriter import fill_pdf_from_llama
    from schema_utils import compile_schemas
    from agents_with_validation import process_forms_with_validation, MainAgent
    from validation_engine import ValidationEngine
    from batch_processor import BatchProcessor
    from streamlined_batch_processor import StreamlinedBatchProcessor
    from FormFIller import PyMuPDFTemporaryFiller, fill_forms_with_temporary_storage, preview_field_mappings
    LEGACY_AVAILABLE = True
except ImportError as e:
    print(f"Legacy modules not available: {e}")
    LEGACY_AVAILABLE = False
    # Define fallback functions for missing legacy components
    def parse_pdf_with_dynamic_schema(filepath):
        """Fallback function when legacy system is not available"""
        return {}
    
    def create_dynamic_schema(schema_data):
        """Fallback function when legacy system is not available"""
        return {}
    
    def fill_pdf_from_llama(data, pdf_path, output_path):
        """Fallback function when legacy system is not available"""
        return False
    
    def compile_schemas(schemas):
        """Fallback function when legacy system is not available"""
        return {}
    
    def process_forms_with_validation(form_paths):
        """Fallback function when legacy system is not available"""
        return {'status': 'error', 'message': 'Legacy system not available'}

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
    # Define fallback functions for missing llama_parser components
    def llama_parse(filepaths, schema):
        """Fallback function when llama_parser is not available"""
        return {}
    
    def simplify_llama_output(data):
        """Fallback function when llama_parser is not available"""
        if isinstance(data, dict):
            return data
        return {}
    
    def filter_filled_fields(data):
        """Fallback function when llama_parser is not available"""
        return data

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
FORMS_FOLDER = 'Forms'
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(FORMS_FOLDER):
    os.makedirs(FORMS_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FORMS_FOLDER'] = FORMS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Basic authentication configuration
BASIC_AUTH_USERS = {
    'admin': generate_password_hash('admin123'),
    'user': generate_password_hash('user123'),
    'demo': generate_password_hash('demo123')
}

# Detect if request is from desktop app
def is_desktop_request():
    """Check if request is from desktop application"""
    user_agent = request.headers.get('User-Agent', '').lower()
    return 'desktop' in user_agent or 'electron' in user_agent or request.headers.get('X-Desktop-App') == 'true'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'success': False, 'error': 'Authentication required', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated_function

def pdf_to_base64_preview(pdf_path, page_num=0):
    """Convert PDF page to base64 image for preview"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        
        if page_num >= len(doc):
            page_num = 0
        
        page = doc[page_num]
        # Render page as image (150 DPI for good quality preview)
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        
        # Convert to base64
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        doc.close()
        return {
            'success': True,
            'image': f"data:image/png;base64,{img_base64}",
            'page_count': len(doc),
            'current_page': page_num
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login - OAuth for web, basic auth for desktop"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # Use basic auth for desktop or fallback
        if username in BASIC_AUTH_USERS and check_password_hash(BASIC_AUTH_USERS[username], password):
            session['user'] = username
            session['auth_method'] = 'basic'
            return jsonify({'success': True, 'message': 'Login successful', 'user': username})
        else:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
    
    # Check if this is a desktop request
    if is_desktop_request():
        # Return basic auth form for desktop
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>FIFA: Financial Form Filling Agent - Desktop Login</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
                .login-form { background: #f5f5f5; padding: 30px; border-radius: 8px; }
                input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
                button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
                .error { color: red; margin-top: 10px; }
                .demo-creds { background: #e9ecef; padding: 15px; margin-top: 20px; border-radius: 4px; font-size: 14px; }
                .desktop-badge { background: #28a745; color: white; padding: 5px 10px; border-radius: 4px; font-size: 12px; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="login-form">
                <div class="desktop-badge">Desktop Application</div>
                <h2>FIFA: Financial Form Filling Agent - Desktop Login</h2>
                <form id="loginForm">
                    <input type="text" id="username" placeholder="Username" required>
                    <input type="password" id="password" placeholder="Password" required>
                    <button type="submit">Login</button>
                </form>
                <div id="error" class="error"></div>
                <div class="demo-creds">
                    <strong>Demo Credentials:</strong><br>
                    admin / admin123<br>
                    user / user123<br>
                    demo / demo123
                </div>
            </div>
            <script>
                document.getElementById('loginForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    
                    try {
                        const response = await fetch('/login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ username, password })
                        });
                        
                        const data = await response.json();
                        if (data.success) {
                            window.location.href = '/';
                        } else {
                            document.getElementById('error').textContent = data.error;
                        }
                    } catch (error) {
                        document.getElementById('error').textContent = 'Login failed. Please try again.';
                    }
                });
            </script>
        </body>
        </html>
        '''
    
    # Return improved login form for web requests
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FIFA: Financial Form Filling Agent - Login</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .login-container {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                padding: 40px;
                width: 100%;
                max-width: 420px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            .logo {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .logo h1 {
                color: #333;
                font-size: 28px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            
            .logo p {
                color: #666;
                font-size: 14px;
                font-weight: 400;
            }
            
            .form-group {
                margin-bottom: 20px;
                position: relative;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
                font-size: 14px;
            }
            
            .form-group input {
                width: 100%;
                padding: 15px 20px;
                border: 2px solid #e1e5e9;
                border-radius: 12px;
                font-size: 16px;
                transition: all 0.3s ease;
                background: #fff;
            }
            
            .form-group input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            .login-btn {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 10px;
            }
            
            .login-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
            }
            
            .login-btn:active {
                transform: translateY(0);
            }
            
            .login-btn:disabled {
                opacity: 0.7;
                cursor: not-allowed;
                transform: none;
            }
            
            .error {
                background: #fee;
                color: #c33;
                padding: 12px 16px;
                border-radius: 8px;
                margin-top: 15px;
                font-size: 14px;
                border-left: 4px solid #c33;
                display: none;
            }
            
            .error.show {
                display: block;
                animation: slideIn 0.3s ease;
            }
            
            .demo-creds {
                background: linear-gradient(135deg, #f8f9ff 0%, #e8f2ff 100%);
                padding: 20px;
                border-radius: 12px;
                margin-top: 25px;
                border: 1px solid #e1e8ff;
            }
            
            .demo-creds h4 {
                color: #333;
                margin-bottom: 12px;
                font-size: 14px;
                font-weight: 600;
            }
            
            .cred-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid rgba(102, 126, 234, 0.1);
                font-size: 13px;
            }
            
            .cred-item:last-child {
                border-bottom: none;
            }
            
            .cred-username {
                font-weight: 600;
                color: #667eea;
            }
            
            .cred-password {
                font-family: monospace;
                background: rgba(102, 126, 234, 0.1);
                padding: 2px 6px;
                border-radius: 4px;
                color: #333;
            }
            
            .loading {
                display: none;
                width: 20px;
                height: 20px;
                border: 2px solid #ffffff;
                border-top: 2px solid transparent;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-right: 10px;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 12px;
            }
            
            @media (max-width: 480px) {
                .login-container {
                    padding: 30px 20px;
                    margin: 10px;
                }
                
                .logo h1 {
                    font-size: 24px;
                }
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>📄 FIFA: Financial Form Filling Agent</h1>
                <p>Secure Document Processing Platform</p>
            </div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" required autocomplete="username">
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required autocomplete="current-password">
                </div>
                
                <button type="submit" class="login-btn" id="loginBtn">
                    <span class="loading" id="loading"></span>
                    <span id="btnText">Sign In</span>
                </button>
            </form>
            
            <div id="error" class="error"></div>
            
            <div class="demo-creds">
                <h4>🔑 Demo Credentials</h4>
                <div class="cred-item">
                    <span class="cred-username">admin</span>
                    <span class="cred-password">admin123</span>
                </div>
                <div class="cred-item">
                    <span class="cred-username">user</span>
                    <span class="cred-password">user123</span>
                </div>
                <div class="cred-item">
                    <span class="cred-username">demo</span>
                    <span class="cred-password">demo123</span>
                </div>
            </div>
            
            <div class="footer">
                <p>© 2024 FIFA: Financial Form Filling Agent. All rights reserved.</p>
            </div>
        </div>
        
        <script>
            const loginForm = document.getElementById('loginForm');
            const loginBtn = document.getElementById('loginBtn');
            const loading = document.getElementById('loading');
            const btnText = document.getElementById('btnText');
            const errorDiv = document.getElementById('error');
            
            function showError(message) {
                errorDiv.textContent = message;
                errorDiv.classList.add('show');
                setTimeout(() => {
                    errorDiv.classList.remove('show');
                }, 5000);
            }
            
            function setLoading(isLoading) {
                if (isLoading) {
                    loading.style.display = 'inline-block';
                    btnText.textContent = 'Signing In...';
                    loginBtn.disabled = true;
                } else {
                    loading.style.display = 'none';
                    btnText.textContent = 'Sign In';
                    loginBtn.disabled = false;
                }
            }
            
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const username = document.getElementById('username').value.trim();
                const password = document.getElementById('password').value;
                
                if (!username || !password) {
                    showError('Please enter both username and password.');
                    return;
                }
                
                setLoading(true);
                
                try {
                    const response = await fetch('/login', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify({ username, password })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        btnText.textContent = 'Success! Redirecting...';
                        setTimeout(() => {
                            window.location.href = '/';
                        }, 500);
                    } else {
                        showError(data.error || 'Login failed. Please check your credentials.');
                    }
                } catch (error) {
                    console.error('Login error:', error);
                    showError('Network error. Please check your connection and try again.');
                } finally {
                    if (btnText.textContent !== 'Success! Redirecting...') {
                        setLoading(false);
                    }
                }
            });
            
            // Auto-focus username field
            document.getElementById('username').focus();
        </script>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    """Handle user logout"""
    session.pop('user', None)
    session.pop('auth_method', None)
    session.pop('user_info', None)
    return redirect('/login')

@app.route('/check-auth')
def check_auth():
    """Check if user is authenticated"""
    if 'user' in session:
        return jsonify({
            'authenticated': True, 
            'user': session['user'],
            'auth_method': session.get('auth_method', 'unknown'),
            'user_info': session.get('user_info', {})
        })
    else:
        return jsonify({'authenticated': False})

@app.route('/user-info')
@login_required
def user_info():
    """Get detailed user information"""
    return jsonify({
        'user': session.get('user'),
        'auth_method': session.get('auth_method'),
        'user_info': session.get('user_info', {}),
        'session_data': {
            'login_time': session.get('login_time'),
            'last_activity': session.get('last_activity')
        }
    })

@app.route('/')
def index():
    """Serve the consolidated financial dashboard as the primary interface"""
    if 'user' not in session:
        return redirect('/login')
    return send_file('Frontend/index.html')

@app.route('/legacy')
@login_required
def legacy():
    """Serve the legacy dashboard for reference"""
    return render_template('index.html')

@app.route('/frontend')
@login_required
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
                # Also save to Forms folder
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = os.path.splitext(filename)[0]
                forms_filename = f"{base_name}_filled_{timestamp}.pdf"
                forms_path = os.path.join(app.config['FORMS_FOLDER'], forms_filename)
                import shutil
                shutil.copy2(output_filepath, forms_path)
                print(f"💾 Filled form saved to Forms folder: {forms_path}")
                
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

@app.route('/preview-filled-pdf/<filename>')
@login_required
def preview_filled_pdf(filename):
    """Generate a preview of a filled PDF form for web display"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Also check Forms folder
        if not os.path.exists(file_path):
            forms_path = os.path.join('Forms', filename)
            if os.path.exists(forms_path):
                file_path = forms_path
        
        if os.path.exists(file_path):
            # Get page number from query parameter (default to 0)
            page_num = int(request.args.get('page', 0))
            
            # Generate preview
            preview_result = pdf_to_base64_preview(file_path, page_num)
            
            if preview_result['success']:
                return jsonify({
                    'success': True,
                    'preview': preview_result,
                    'filename': filename,
                    'file_path': file_path
                })
            else:
                return jsonify({'success': False, 'error': preview_result['error']})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/preview-document', methods=['POST'])
@login_required
def preview_document():
    """
    Generate a preview of an uploaded PDF document
    """
    try:
        if 'document' not in request.files:
            return jsonify({'success': False, 'error': 'No document uploaded'})
        
        file = request.files['document']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No document selected'})
        
        if file and allowed_file(file.filename):
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"preview_{filename}")
            file.save(filepath)
            
            try:
                # Get page number from request (default to 0)
                page_num = int(request.form.get('page', 0))
                
                # Generate preview
                preview_result = pdf_to_base64_preview(filepath, page_num)
                
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                if preview_result['success']:
                    return jsonify({
                        'success': True,
                        'preview': preview_result,
                        'filename': filename
                    })
                else:
                    return jsonify({'success': False, 'error': preview_result['error']})
                    
            except Exception as e:
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'success': False, 'error': f'Preview generation error: {str(e)}'})
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Document preview error: {str(e)}'
        }), 500

@app.route('/preview-batch-results', methods=['POST'])
@login_required
def preview_batch_results():
    """
    Generate previews of batch processing results
    """
    try:
        # Handle multiple document uploads
        documents = request.files.getlist('documents') if 'documents' in request.files else []
        forms = request.files.getlist('forms') if 'forms' in request.files else []
        
        if not documents:
            return jsonify({'success': False, 'error': 'No documents uploaded'})
        
        if not forms:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        # Limit preview to first 3 forms to avoid overwhelming the response
        preview_limit = min(3, len(forms))
        
        # Create temporary directories for processing
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        temp_docs_dir = os.path.join(temp_dir, 'Documents')
        temp_forms_dir = os.path.join(temp_dir, 'Forms')
        temp_output_dir = os.path.join(temp_dir, 'PreviewOutput')
        
        os.makedirs(temp_docs_dir, exist_ok=True)
        os.makedirs(temp_forms_dir, exist_ok=True)
        
        try:
            # Save uploaded documents
            document_paths = []
            for file in documents:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(temp_docs_dir, filename)
                    file.save(filepath)
                    document_paths.append(filepath)
            
            # Save uploaded forms (limited for preview)
            form_paths = []
            for i, file in enumerate(forms[:preview_limit]):
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(temp_forms_dir, filename)
                    file.save(filepath)
                    form_paths.append(filepath)
            
            if not document_paths:
                return jsonify({'success': False, 'error': 'No valid PDF documents uploaded'})
            
            if not form_paths:
                return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
            
            # Create streamlined batch processor for preview
            streamlined_processor = StreamlinedBatchProcessor(
                documents_folder=temp_docs_dir,
                forms_folder=temp_forms_dir,
                output_folder=temp_output_dir
            )
            
            # Run streamlined processing
            result = streamlined_processor.run_streamlined_processing()
            
            if result and result['status'] == 'success':
                # Generate previews of filled forms
                filled_forms = result['filled_forms']
                previews = []
                
                for i, filled_form in enumerate(filled_forms[:preview_limit]):
                    if os.path.exists(filled_form):
                        preview_result = pdf_to_base64_preview(filled_form, 0)
                        if preview_result['success']:
                            previews.append({
                                'filename': os.path.basename(filled_form),
                                'preview': preview_result,
                                'form_index': i
                            })
                
                return jsonify({
                    'success': True,
                    'message': f'Generated previews for {len(previews)} filled forms',
                    'previews': previews,
                    'stats': result['stats'],
                    'total_forms': len(forms),
                    'previewed_forms': len(previews),
                    'preview_note': f'Showing previews for first {preview_limit} forms' if len(forms) > preview_limit else 'Showing all forms'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Batch processing failed for preview'
                }), 500
                
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Batch preview error: {str(e)}'
        }), 500

@app.route('/preview-filled-form', methods=['POST'])
@login_required
def preview_filled_form():
    """
    Generate a preview of a filled PDF form with custom data
    """
    try:
        # Get form data from request
        form_data_json = request.form.get('form_data')
        if form_data_json:
            try:
                custom_data = json.loads(form_data_json)
            except json.JSONDecodeError:
                custom_data = {}
        else:
            # Fall back to extracted data from cookies
            extracted_data = request.cookies.get('extracted_data')
            has_data = request.cookies.get('has_data')
            
            if not has_data or not extracted_data:
                return jsonify({'success': False, 'error': 'No form data found'})
            
            try:
                custom_data = json.loads(extracted_data)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid form data'})

        # Apply simplification and filtering to the data before filling
        simplified_data = simplify_llama_output(custom_data) if LLAMA_PARSER_AVAILABLE else custom_data
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"preview_form_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Use FormFIller for semantic form filling
                with PyMuPDFTemporaryFiller() as filler:
                    filled_path = filler.fill_single_form(simplified_data, form_filepath)
                    
                    if filled_path:
                        # Get page number from request (default to 0)
                        page_num = int(request.form.get('page', 0))
                        
                        # Generate preview of filled form
                        preview_result = pdf_to_base64_preview(filled_path, page_num)
                        
                        # Get processing stats
                        stats = filler.get_processing_stats()
                        
                        # Clean up uploaded form
                        if os.path.exists(form_filepath):
                            os.remove(form_filepath)
                        
                        if preview_result['success']:
                            return jsonify({
                                'success': True,
                                'preview': preview_result,
                                'filename': f"filled_{filename}",
                                'stats': {
                                    'fields_filled': stats['fields_filled'],
                                    'mapping_errors': stats['mapping_errors']
                                }
                            })
                        else:
                            return jsonify({'success': False, 'error': preview_result['error']})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to fill PDF form for preview'})
                        
            except Exception as e:
                # Clean up uploaded form
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({'success': False, 'error': f'Form filling preview error: {str(e)}'})
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Preview generation error: {str(e)}'
        }), 500

@app.route('/fill-edited-form', methods=['POST'])
@login_required
def fill_edited_form():
    """
    Fill a PDF form with edited data and return the filled form for download
    """
    try:
        # Get form data from request
        form_data_json = request.form.get('form_data')
        if form_data_json:
            try:
                custom_data = json.loads(form_data_json)
            except json.JSONDecodeError:
                custom_data = {}
        else:
            # Fall back to extracted data from cookies
            extracted_data = request.cookies.get('extracted_data')
            has_data = request.cookies.get('has_data')
            
            if not has_data or not extracted_data:
                return jsonify({'success': False, 'error': 'No form data found'})
            
            try:
                custom_data = json.loads(extracted_data)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid form data'})

        # Apply simplification and filtering to the data before filling
        simplified_data = simplify_llama_output(custom_data) if LLAMA_PARSER_AVAILABLE else custom_data
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"edit_form_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Use FormFIller for semantic form filling
                with PyMuPDFTemporaryFiller() as filler:
                    filled_path = filler.fill_single_form(simplified_data, form_filepath)
                    
                    if filled_path:
                        # Copy filled form to permanent location for download
                        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"edited_filled_{filename}")
                        import shutil
                        shutil.copy2(filled_path, output_filepath)
                        
                        # Clean up uploaded form
                        if os.path.exists(form_filepath):
                            os.remove(form_filepath)
                        
                        # Return the filled form as a download
                        return send_file(output_filepath, as_attachment=True, 
                                       download_name=f"edited_{filename}", 
                                       mimetype='application/pdf')
                    else:
                        return jsonify({'success': False, 'error': 'Failed to fill PDF form'})
                        
            except Exception as e:
                # Clean up uploaded form
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({'success': False, 'error': f'Form filling error: {str(e)}'})
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Form filling error: {str(e)}'
        }), 500

@app.route('/streamlined-batch-process', methods=['POST'])
@login_required
def streamlined_batch_process():
    """
    Streamlined batch processing that prevents over-filling by:
    1. First discovering what fields exist in forms
    2. Then extracting only those specific data points from documents
    3. Mapping them precisely to prevent incorrect assignments
    """
    try:
        # Handle multiple document uploads
        documents = request.files.getlist('documents') if 'documents' in request.files else []
        forms = request.files.getlist('forms') if 'forms' in request.files else []
        
        if not documents:
            return jsonify({'success': False, 'error': 'No documents uploaded'})
        
        if not forms:
            return jsonify({'success': False, 'error': 'No forms uploaded'})
        
        # Create temporary directories for processing
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        temp_docs_dir = os.path.join(temp_dir, 'Documents')
        temp_forms_dir = os.path.join(temp_dir, 'Forms')
        temp_output_dir = os.path.join(temp_dir, 'StreamlinedOutput')
        
        os.makedirs(temp_docs_dir, exist_ok=True)
        os.makedirs(temp_forms_dir, exist_ok=True)
        
        try:
            # Save uploaded documents
            document_paths = []
            for file in documents:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(temp_docs_dir, filename)
                    file.save(filepath)
                    document_paths.append(filepath)
            
            # Save uploaded forms
            form_paths = []
            for file in forms:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(temp_forms_dir, filename)
                    file.save(filepath)
                    form_paths.append(filepath)
            
            if not document_paths:
                return jsonify({'success': False, 'error': 'No valid PDF documents uploaded'})
            
            if not form_paths:
                return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
            
            print(f"\n🚀 Starting streamlined batch processing: {len(document_paths)} docs, {len(form_paths)} forms...")
            
            # Create streamlined batch processor
            streamlined_processor = StreamlinedBatchProcessor(
                documents_folder=temp_docs_dir,
                forms_folder=temp_forms_dir,
                output_folder=temp_output_dir
            )
            
            # Run streamlined processing
            result = streamlined_processor.run_streamlined_processing()
            
            if result and result['status'] == 'success':
                # Copy filled forms to permanent location
                filled_forms = result['filled_forms']
                permanent_filled_forms = []
                
                for filled_form in filled_forms:
                    if os.path.exists(filled_form):
                        base_name = os.path.basename(filled_form)
                        permanent_path = os.path.join(app.config['UPLOAD_FOLDER'], f"streamlined_{base_name}")
                        shutil.copy2(filled_form, permanent_path)
                        permanent_filled_forms.append(permanent_path)
                
                # Create a zip file with all filled forms and QA report
                import zipfile
                from datetime import datetime
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = f"streamlined_batch_results_{timestamp}.zip"
                zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    # Add filled forms
                    for filled_form in permanent_filled_forms:
                        if os.path.exists(filled_form):
                            zipf.write(filled_form, f"filled_forms/{os.path.basename(filled_form)}")
                    
                    # Add QA report if it exists
                    qa_report_file = result.get('qa_report_file')
                    if qa_report_file and os.path.exists(qa_report_file):
                        zipf.write(qa_report_file, f"qa_report/{os.path.basename(qa_report_file)}")
                    
                    # Add field mappings if they exist
                    field_mappings_dir = os.path.join(temp_output_dir, 'field_mappings')
                    if os.path.exists(field_mappings_dir):
                        for mapping_file in os.listdir(field_mappings_dir):
                            mapping_path = os.path.join(field_mappings_dir, mapping_file)
                            if os.path.isfile(mapping_path):
                                zipf.write(mapping_path, f"field_mappings/{mapping_file}")
                
                return jsonify({
                    'success': True,
                    'message': f'Streamlined processing completed successfully!',
                    'stats': result['stats'],
                    'qa_summary': {
                        'documents_processed': result['stats']['documents_processed'],
                        'forms_filled': result['stats']['forms_filled'],
                        'fields_discovered': result['stats']['fields_discovered'],
                        'fields_filled': result['stats']['fields_filled'],
                        'fill_rate': (result['stats']['fields_filled'] / max(result['stats']['fields_discovered'], 1)) * 100,
                        'error_count': len(result['stats']['errors'])
                    },
                    'download_url': f'/download-batch-results/{zip_filename}',
                    'qa_checks': {
                        'over_filling_prevented': True,
                        'targeted_extraction_used': True,
                        'semantic_mapping_applied': True,
                        'field_mappings_saved': True
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Streamlined batch processing failed'
                }), 500
                
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Streamlined batch processing error: {str(e)}'
        }), 500

# New OpenAI Two-Agent System Routes

@app.route('/openai-extract', methods=['POST'])
@login_required
def openai_extract():
    """
    Extract data using OpenAI Extraction Agent - with direct terminal output
    """
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }), 500
        
        # Handle file upload
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if file and allowed_file(file.filename):
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"openai_extract_{filename}")
            file.save(filepath)
            
            try:
                print("\n" + "="*100)
                print(f"🚀 STARTING DIRECT OPENAI EXTRACTION FOR: {filename}")
                print("="*100)
                
                # Initialize OpenAI extraction agent directly
                from openai_extraction_agent import OpenAIExtractionAgent
                agent = OpenAIExtractionAgent(api_key=api_key)
                
                # Extract data directly - this will print to terminal
                result = agent.extract_from_document(filepath)
                
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                if result["success"]:
                    extracted_data = result["extracted_data"]
                    json_path = result["json_file_path"]
                    
                    print("\n" + "="*100)
                    print("💾 FINAL EXTRACTION RESULT:")
                    print("="*100)
                    print(f"📄 Source file: {filename}")
                    print(f"💾 JSON saved to: {json_path}")
                    print(f"📊 Total fields extracted: {result['extraction_summary']['total_fields']}")
                    print("="*100)
                    
                    response = jsonify({
                        'success': True,
                        'data': extracted_data,
                        'filename': filename,
                        'extraction_summary': result.get("extraction_summary", {}),
                        'agent_info': 'OpenAI Extraction Agent (Direct)',
                        'json_file_path': json_path
                    })
                    
                    # Store data in cookies
                    if extracted_data:
                        cookie_data = json.dumps(extracted_data)
                        response.set_cookie('extracted_data', cookie_data, max_age=240, httponly=False)
                        response.set_cookie('has_data', 'true', max_age=240, httponly=False)
                        if json_path:
                            response.set_cookie('json_file_path', json_path, max_age=240, httponly=False)
                    
                    return response
                else:
                    print(f"\n❌ EXTRACTION FAILED: {result.get('error', 'Unknown error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get("error", "Extraction failed")
                    }), 500
                    
            except Exception as e:
                print(f"\n❌ EXTRACTION ERROR: {str(e)}")
                # Clean up uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    'success': False,
                    'error': f'OpenAI extraction error: {str(e)}'
                }), 500
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        print(f"\n❌ ROUTE ERROR: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'OpenAI extraction error: {str(e)}'
        }), 500

@app.route('/openai-fill-form', methods=['POST'])
@login_required
def openai_fill_form():
    """
    Fill PDF form using OpenAI Form Filling Agent
    """
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }), 500
        
        # Get JSON file path from cookies or check for extracted data
        json_path = request.cookies.get('json_file_path')
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')
        
        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"openai_form_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Initialize OpenAI coordinator
                coordinator = OpenAIAgentCoordinator(api_key=api_key)
                
                # If we have a JSON file path, use it directly
                if json_path and os.path.exists(json_path):
                    temp_json_path = json_path
                else:
                    # Create temporary JSON file from cookie data
                    temp_json_data = json.loads(extracted_data)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_json_filename = f"temp_extracted_{timestamp}.json"
                    temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_json_filename)
                    
                    with open(temp_json_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "metadata": {
                                "extraction_timestamp": datetime.now().isoformat(),
                                "source": "cookie_data",
                                "extraction_agent": "OpenAI Extraction Agent"
                            },
                            "extracted_data": temp_json_data
                        }, f, indent=2)
                
                # Fill form using OpenAI agent
                result = coordinator.fill_forms_with_json([form_filepath], temp_json_path)
                
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                if not json_path and os.path.exists(temp_json_path):  # Only remove temp file
                    os.remove(temp_json_path)
                
                if result["success"] and result["individual_results"]:
                    form_result = result["individual_results"][0]
                    if form_result["success"] and "output_pdf" in form_result:
                        return send_file(
                            form_result["output_pdf"], 
                            as_attachment=True, 
                            download_name=f"openai_filled_{filename}", 
                            mimetype='application/pdf'
                        )
                
                return jsonify({
                    'success': False,
                    'error': result.get("error", "Form filling failed")
                }), 500
                
            except Exception as e:
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({
                    'success': False,
                    'error': f'OpenAI form filling error: {str(e)}'
                }), 500
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OpenAI form filling error: {str(e)}'
        }), 500

@app.route('/openai-batch-process', methods=['POST'])
@login_required
def openai_batch_process():
    """
    Complete two-agent workflow: extract from documents, fill multiple forms
    """
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }), 500
        
        # Handle multiple document and form uploads
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
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"openai_batch_doc_{filename}")
                file.save(filepath)
                document_paths.append(filepath)
        
        # Save uploaded forms
        form_paths = []
        for file in forms:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"openai_batch_form_{filename}")
                file.save(filepath)
                form_paths.append(filepath)
        
        if not document_paths:
            return jsonify({'success': False, 'error': 'No valid PDF documents uploaded'})
        
        if not form_paths:
            return jsonify({'success': False, 'error': 'No valid PDF forms uploaded'})
        
        try:
            # Initialize OpenAI coordinator
            coordinator = OpenAIAgentCoordinator(api_key=api_key)
            
            # Run complete two-agent workflow
            result = coordinator.extract_and_fill_workflow(document_paths, form_paths)
            
            # Clean up uploaded files
            for filepath in document_paths + form_paths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            if result["success"]:
                # Create ZIP file with filled forms
                filled_form_paths = result["workflow_summary"]["filled_form_paths"]
                
                if filled_form_paths:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    zip_filename = f"openai_batch_results_{timestamp}.zip"
                    zip_path = coordinator.create_zip_archive(filled_form_paths, f"openai_batch_results_{timestamp}")
                    
                    if zip_path:
                        # Copy to upload folder for download
                        final_zip_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(zip_path))
                        import shutil
                        shutil.copy2(zip_path, final_zip_path)
                        
                        return jsonify({
                            'success': True,
                            'message': f'OpenAI two-agent workflow completed successfully!',
                            'workflow_summary': result["workflow_summary"],
                            'agent_info': result["agent_info"],
                            'download_url': f'/download-batch-results/{os.path.basename(final_zip_path)}',
                            'stats': {
                                'documents_processed': result["workflow_summary"]["total_documents_processed"],
                                'forms_filled': result["workflow_summary"]["successful_form_fills"],
                                'workflow_duration': result["workflow_summary"]["workflow_duration_seconds"]
                            }
                        })
                
                return jsonify({
                    'success': True,
                    'message': 'Workflow completed but no forms were filled',
                    'workflow_summary': result["workflow_summary"]
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get("error", "Two-agent workflow failed"),
                    'stage': result.get("stage", "unknown")
                }), 500
                
        except Exception as e:
            # Clean up files on error
            for filepath in document_paths + form_paths:
                if os.path.exists(filepath):
                    os.remove(filepath)
            return jsonify({
                'success': False,
                'error': f'OpenAI batch processing error: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OpenAI batch processing error: {str(e)}'
        }), 500

@app.route('/openai-preview-mapping', methods=['POST'])
@login_required
def openai_preview_mapping():
    """
    Preview field mapping using OpenAI Form Filling Agent
    """
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }), 500
        
        # Get JSON file path from cookies or check for extracted data
        json_path = request.cookies.get('json_file_path')
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')
        
        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"openai_preview_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                # Initialize OpenAI coordinator
                coordinator = OpenAIAgentCoordinator(api_key=api_key)
                
                # If we have a JSON file path, use it directly
                if json_path and os.path.exists(json_path):
                    temp_json_path = json_path
                else:
                    # Create temporary JSON file from cookie data
                    temp_json_data = json.loads(extracted_data)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_json_filename = f"temp_preview_{timestamp}.json"
                    temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_json_filename)
                    
                    with open(temp_json_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "metadata": {
                                "extraction_timestamp": datetime.now().isoformat(),
                                "source": "cookie_data",
                                "extraction_agent": "OpenAI Extraction Agent"
                            },
                            "extracted_data": temp_json_data
                        }, f, indent=2)
                
                # Preview field mapping
                result = coordinator.preview_form_mapping(form_filepath, temp_json_path)
                
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                if not json_path and os.path.exists(temp_json_path):  # Only remove temp file
                    os.remove(temp_json_path)
                
                if result["success"]:
                    return jsonify({
                        'success': True,
                        'preview': result,
                        'message': f'OpenAI field mapping preview for {filename}',
                        'agent_info': 'OpenAI Form Filling Agent'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': result.get("error", "Preview generation failed")
                    }), 500
                    
            except Exception as e:
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({
                    'success': False,
                    'error': f'OpenAI preview error: {str(e)}'
                }), 500
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OpenAI preview error: {str(e)}'
        }), 500

@app.route('/openai-schema-fill', methods=['POST'])
@login_required
def openai_schema_fill():
    """
    Web-compatible schema-based form filling with OpenAI agents
    """
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.'
            }), 500
        
        # Get JSON file path from cookies or check for extracted data
        json_path = request.cookies.get('json_file_path')
        extracted_data = request.cookies.get('extracted_data')
        has_data = request.cookies.get('has_data')
        
        if not has_data or not extracted_data:
            return jsonify({'success': False, 'error': 'No extracted data found. Please extract data first.'})
        
        # Handle form upload
        if 'form_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No PDF form uploaded'})
        
        form_pdf = request.files['form_pdf']
        if form_pdf.filename == '':
            return jsonify({'success': False, 'error': 'No PDF form selected'})
        
        if form_pdf and allowed_file(form_pdf.filename):
            filename = secure_filename(form_pdf.filename)
            form_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"schema_form_{filename}")
            form_pdf.save(form_filepath)
            
            try:
                print("\n" + "="*100)
                print(f"🔍 STARTING SCHEMA-BASED FORM FILLING FOR: {filename}")
                print("="*100)
                
                # Initialize web-compatible form filling agent
                agent = OpenAIFormFillingAgentWeb(api_key=api_key)
                
                # If we have a JSON file path, use it directly
                if json_path and os.path.exists(json_path):
                    temp_json_path = json_path
                else:
                    # Create temporary JSON file from cookie data
                    temp_json_data = json.loads(extracted_data)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_json_filename = f"temp_schema_{timestamp}.json"
                    temp_json_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_json_filename)
                    
                    with open(temp_json_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            "metadata": {
                                "extraction_timestamp": datetime.now().isoformat(),
                                "source": "cookie_data",
                                "extraction_agent": "OpenAI Extraction Agent"
                            },
                            "extracted_data": temp_json_data
                        }, f, indent=2)
                
                # Fill form using web-compatible agent
                result = agent.fill_form_from_json_web(form_filepath, temp_json_path)
                
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                if not json_path and os.path.exists(temp_json_path):  # Only remove temp file
                    os.remove(temp_json_path)
                
                if result["success"]:
                    print("\n" + "="*100)
                    print("✅ SCHEMA-BASED FORM FILLING COMPLETED")
                    print("="*100)
                    print(f"📄 Form: {filename}")
                    print(f"📊 Fields filled: {result['fields_mapped']}/{result['total_form_fields']}")
                    print(f"🎯 Auto-approved (90%+): {result['mapping_summary']['auto_approved_count']}")
                    print(f"📊 Medium confidence (70-89%): {result['mapping_summary']['medium_confidence_count']}")
                    print(f"⏭️  Skipped (<70%): {result['mapping_summary']['skipped_count']}")
                    print("="*100)
                    
                    # Generate timestamp for unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"{base_name}_filled_{timestamp}.pdf"
                    
                    # Copy filled form to Forms folder (primary storage)
                    forms_path = os.path.join(app.config['FORMS_FOLDER'], output_filename)
                    import shutil
                    shutil.copy2(result["output_pdf"], forms_path)
                    
                    # Also copy to uploads folder for web download
                    web_download_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
                    shutil.copy2(result["output_pdf"], web_download_path)
                    
                    print(f"💾 Filled form saved to: {forms_path}")
                    print(f"🌐 Web download available at: {web_download_path}")
                    
                    return jsonify({
                        'success': True,
                        'message': f'Schema-based form filling completed for {filename}',
                        'filename': output_filename,
                        'original_filename': filename,
                        'fields_mapped': result['fields_mapped'],
                        'total_form_fields': result['total_form_fields'],
                        'schema_analysis': result['schema_analysis'],
                        'mapping_summary': result['mapping_summary'],
                        'high_confidence_mappings': result['high_confidence_mappings'],
                        'medium_confidence_mappings': result['medium_confidence_mappings'],
                        'skipped_mappings': result['skipped_mappings'],
                        'agent_info': 'OpenAI Schema-Based Form Filling Agent (Web)',
                        'download_url': f'/download-filled-form/{output_filename}',
                        'preview_url': f'/preview-filled-pdf/{output_filename}',
                        'forms_folder_path': forms_path,
                        'timestamp': timestamp
                    })
                else:
                    print(f"\n❌ SCHEMA-BASED FORM FILLING FAILED: {result.get('error', 'Unknown error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get("error", "Schema-based form filling failed")
                    }), 500
                    
            except Exception as e:
                print(f"\n❌ SCHEMA FILLING ERROR: {str(e)}")
                # Clean up files
                if os.path.exists(form_filepath):
                    os.remove(form_filepath)
                return jsonify({
                    'success': False,
                    'error': f'OpenAI schema filling error: {str(e)}'
                }), 500
        
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})
        
    except Exception as e:
        print(f"\n❌ SCHEMA ROUTE ERROR: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'OpenAI schema filling error: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
