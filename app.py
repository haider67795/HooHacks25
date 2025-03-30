import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from urllib.parse import quote

app = Flask(__name__)

# Define the upload and media folders
UPLOAD_FOLDER = 'uploads'
MEDIA_FOLDER = 'media'  # Folder for static images (e.g., placeholders)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MEDIA_FOLDER'] = MEDIA_FOLDER

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Function to sanitize file names: remove spaces and trim
def sanitize_filename(filename):
    # Replace spaces with underscores and trim any leading/trailing whitespace
    sanitized_filename = filename.replace(" ", "_").strip()
    return sanitized_filename

# Route to serve images from the uploads folder (user-uploaded images)
@app.route('/uploads/<filename>')
def upload_file(filename):
    # Sanitize the filename before serving it
    sanitized_filename = sanitize_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], sanitized_filename)

# Route to serve images from the media folder (static images like placeholders)
@app.route('/media/<filename>')
def media_file(filename):
    return send_from_directory(app.config['MEDIA_FOLDER'], filename)

# Home route
@app.route('/')
def home():
    return render_template('index.html')  # Make sure 'index.html' exists in the templates folder

# Route for All Items page
@app.route('/allitems.html')
def all_items():
    return render_template('allitems.html')  # Make sure 'allitems.html' exists in the templates folder

# Route for Chatbox page
@app.route('/chatbox.html')
def chatbox():
    return render_template('chatbox.html')  # Make sure 'chatbox.html' exists in the templates folder

# API route to report a lost item
@app.route('/api/report', methods=['POST'])
def report_item():
    # Get data from the form
    description = request.form.get('description')
    location = request.form.get('location')
    photo = request.files.get('photo')

    # Save the uploaded photo with sanitized filename (remove spaces)
    if photo:
        # Sanitize the filename to handle spaces and special characters
        photo_filename = sanitize_filename(photo.filename)
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
    else:
        photo_filename = None

    # Insert the item data into the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(''' 
        SELECT * FROM items WHERE description = ? AND location = ? AND photo_filename = ?
    ''', (description, location, photo_filename))
    
    existing_item = cursor.fetchone()  # Fetch one result (if any)
    message = ""
    if existing_item:
        message = "Item already exists in the database!"
    else:
        # If not found, insert the new item
        cursor.execute('''
            INSERT INTO items (description, location, photo_filename) 
            VALUES (?, ?, ?)
        ''', (description, location, photo_filename))

        # Commit the transaction to save the data
        conn.commit()
        message = "Item data inserted successfully!"

    conn.commit()
    conn.close()

    # Run the cleanup function to remove unused photos from the uploads folder
    remove_unused_photos()

    return jsonify({"message": message})

# API route to fetch the top 3 most recently added items
@app.route('/api/top_items', methods=['GET'])
def get_top_items():
    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch the top 3 most recent items sorted by timestamp (latest first)
    cursor.execute('''
        SELECT id, description, location, photo_filename, timestamp FROM items
        ORDER BY timestamp DESC LIMIT 3
    ''')

    # Get the results
    items = cursor.fetchall()
    
    # Convert the results to a list of dictionaries
    top_items = []
    for item in items:
        top_items.append({
            "id": item[0],
            "description": item[1],
            "location": item[2],
            "photo_filename": item[3],
            "timestamp": item[4]
        })
    
    conn.close()

    return jsonify({"top_items": top_items})

# Function to remove unused photos from the uploads folder based on the database query
def remove_unused_photos():
    # Connect to the database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get all photo filenames from the database
    cursor.execute('SELECT photo_filename FROM items WHERE photo_filename IS NOT NULL')
    used_photos = {row[0] for row in cursor.fetchall()}

    conn.close()

    # Check files in the uploads folder
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if filename not in used_photos and os.path.isfile(file_path):
            os.remove(file_path)  # Delete the unused photo
            print(f"Removed unused photo: {filename}")

if __name__ == '__main__':
    app.run(debug=True)
