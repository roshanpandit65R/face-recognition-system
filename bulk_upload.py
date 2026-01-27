# bulk_upload.py
"""
Bulk User Registration from Folder
Upload multiple user photos at once with automatic email generation
"""

from flask import Flask, render_template, request, jsonify
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
from utils.db_config import db
from utils import face_utils
from dotenv import load_dotenv
import shutil
import zipfile

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['BULK_UPLOAD_FOLDER'] = 'static/bulk_uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Create folders if not exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BULK_UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_email(filename):
    """
    Generate email from filename
    Example: Pinki.Kumari.jpg -> pinki.kumari@gmail.com
    """
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Convert to lowercase and replace dots/spaces with dots
    email_name = name_without_ext.lower().replace(' ', '.').replace('_', '.')
    
    # Generate email
    email = f"{email_name}@gmail.com"
    
    return email

def format_display_name(filename):
    """
    Format filename to display name
    Example: Pinki.Kumari.jpg -> Pinki Kumari
    """
    name_without_ext = os.path.splitext(filename)[0]
    # Replace dots and underscores with spaces, then title case
    display_name = name_without_ext.replace('.', ' ').replace('_', ' ').title()
    return display_name

def process_single_image(filepath, original_filename):
    """Process single image and return registration data"""
    result = {
        'filename': original_filename,
        'success': False,
        'message': '',
        'name': '',
        'email': ''
    }
    
    try:
        # Generate name and email
        display_name = format_display_name(original_filename)
        email = generate_email(original_filename)
        
        result['name'] = display_name
        result['email'] = email
        
        # Validate image has face
        is_valid, message = face_utils.validate_image(filepath)
        if not is_valid:
            result['message'] = message
            return result
        
        # Resize image
        face_utils.resize_image(filepath)
        
        # Get face encoding
        face_encoding = face_utils.get_face_encoding(filepath)
        
        if face_encoding is None:
            result['message'] = 'Failed to encode face'
            return result
        
        # Encode for database
        encoded_binary = face_utils.encode_for_database(face_encoding)
        
        # Save new filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = secure_filename(f"{display_name.replace(' ', '_')}_{timestamp}.jpg")
        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        
        # Copy to uploads folder
        shutil.copy2(filepath, new_filepath)
        
        # Save to database
        query = """
        INSERT INTO Users (name, email, face_encoding, image_path)
        VALUES (?, ?, ?, ?)
        """
        
        db.execute_query(query, (display_name, email, encoded_binary, f'/static/uploads/{new_filename}'))
        
        result['success'] = True
        result['message'] = 'Successfully registered'
        
    except Exception as e:
        result['message'] = f'Error: {str(e)}'
    
    return result

@app.route('/')
def index():
    """Bulk upload home page"""
    return render_template('bulk_upload.html')

@app.route('/upload_folder', methods=['POST'])
def upload_folder():
    """Handle folder/multiple files upload"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'message': 'No files uploaded'}), 400
        
        files = request.files.getlist('files[]')
        
        if len(files) == 0:
            return jsonify({'success': False, 'message': 'No files selected'}), 400
        
        results = []
        success_count = 0
        failed_count = 0
        
        # Create temporary folder for processing
        temp_folder = os.path.join(app.config['BULK_UPLOAD_FOLDER'], 'temp_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(temp_folder, exist_ok=True)
        
        for file in files:
            if file and allowed_file(file.filename):
                original_filename = file.filename
                temp_filepath = os.path.join(temp_folder, secure_filename(original_filename))
                file.save(temp_filepath)
                
                # Process image
                result = process_single_image(temp_filepath, original_filename)
                results.append(result)
                
                if result['success']:
                    success_count += 1
                else:
                    failed_count += 1
        
        # Cleanup temp folder
        shutil.rmtree(temp_folder)
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(files)} files: {success_count} successful, {failed_count} failed',
            'results': results,
            'success_count': success_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        print(f"Bulk upload error: {e}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500

@app.route('/upload_zip', methods=['POST'])
def upload_zip():
    """Handle ZIP file upload"""
    try:
        if 'zipfile' not in request.files:
            return jsonify({'success': False, 'message': 'No ZIP file uploaded'}), 400
        
        zip_file = request.files['zipfile']
        
        if zip_file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not zip_file.filename.endswith('.zip'):
            return jsonify({'success': False, 'message': 'Only ZIP files allowed'}), 400
        
        # Save ZIP file
        temp_zip_path = os.path.join(app.config['BULK_UPLOAD_FOLDER'], 'temp_' + secure_filename(zip_file.filename))
        zip_file.save(temp_zip_path)
        
        # Extract ZIP
        extract_folder = os.path.join(app.config['BULK_UPLOAD_FOLDER'], 'extracted_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(extract_folder, exist_ok=True)
        
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        
        # Process all images in extracted folder
        results = []
        success_count = 0
        failed_count = 0
        
        for root, dirs, files in os.walk(extract_folder):
            for filename in files:
                if allowed_file(filename):
                    filepath = os.path.join(root, filename)
                    result = process_single_image(filepath, filename)
                    results.append(result)
                    
                    if result['success']:
                        success_count += 1
                    else:
                        failed_count += 1
        
        # Cleanup
        os.remove(temp_zip_path)
        shutil.rmtree(extract_folder)
        
        return jsonify({
            'success': True,
            'message': f'Processed ZIP file: {success_count} successful, {failed_count} failed',
            'results': results,
            'success_count': success_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        print(f"ZIP upload error: {e}")
        return jsonify({'success': False, 'message': f'ZIP upload failed: {str(e)}'}), 500

@app.route('/preview_files', methods=['POST'])
def preview_files():
    """Preview files before upload"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'message': 'No files uploaded'}), 400
        
        files = request.files.getlist('files[]')
        preview_data = []
        
        for file in files:
            if file and allowed_file(file.filename):
                display_name = format_display_name(file.filename)
                email = generate_email(file.filename)
                
                preview_data.append({
                    'filename': file.filename,
                    'name': display_name,
                    'email': email
                })
        
        return jsonify({
            'success': True,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/stats')
def get_stats():
    """Get upload statistics"""
    try:
        query = "SELECT COUNT(*) FROM Users WHERE is_active = 1"
        result = db.execute_query(query, fetch=True)
        total_users = result[0][0] if result else 0
        
        return jsonify({
            'success': True,
            'total_users': total_users
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("BULK USER UPLOAD SYSTEM")
    print("=" * 60)
    print("Upload multiple photos at once!")
    print("Filename format: FirstName.LastName.jpg")
    print("Example: Pinki.Kumari.jpg → Name: Pinki Kumari, Email: pinki.kumari@gmail.com")
    print("")
    print("Access at: http://localhost:5002")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5002, debug=True)