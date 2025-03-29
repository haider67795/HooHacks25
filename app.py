from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import os
from urllib.parse import quote  # for URL encoding the filenames

app = Flask(__name__)

# Folder to store uploaded photos
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Route to serve images from the uploads folder
@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def home():
    return render_template('index.html')  # Make sure 'index.html' exists in the templates folder

@app.route('/api/report', methods=['POST'])
def report_item():
    # Get data from the form
    description = request.form.get('description')
    location = request.form.get('location')
    photo = request.files.get('photo')

    # Save the uploaded photo
    if photo:
        # URL encode the filename to handle spaces and special characters
        photo_filename = quote(photo.filename)
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
        print(photo_filename)
        cursor.execute('''
            INSERT INTO items (description, location, photo_filename) 
            VALUES (?, ?, ?)
        ''', (description, location, photo_filename))

        # Commit the transaction to save the data
        conn.commit()
        message = "Item data inserted successfully!"

    conn.commit()
    conn.close()
    print(message)
    return jsonify({"message": message})

# New route to fetch the top 3 most recently added items
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

if __name__ == '__main__':
    app.run(debug=True)
