import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from urllib.parse import quote
from config import *
from google import genai

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
    sanitized_filename = filename.replace(" ", "_").strip()
    return sanitized_filename

# Route to serve images from the uploads folder
@app.route('/uploads/<filename>')
def upload_file(filename):
    sanitized_filename = sanitize_filename(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], sanitized_filename)

# Route to serve images from the media folder (static images)
@app.route('/media/<filename>')
def media_file(filename):
    return send_from_directory(app.config['MEDIA_FOLDER'], filename)

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Route for All Items page
@app.route('/allitems.html')
def all_items():
    return render_template('allitems.html')

# Route for Chatbox page
@app.route('/chatbox.html')
def chatbox():
     return render_template('chatbox.html')
    


# Route for Chatbox page
@app.route('/api/chat', methods=['POST'])
def talkToGemini():
    # Initialize the Gemini client
    client = genai.Client(api_key=key)
    
    # Get the message from the POST request body
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    # Connect to the database and fetch items
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, description, location, photo_filename, timestamp FROM items
        ORDER BY timestamp DESC
    ''')
    items = cursor.fetchall()

    # Build a message for Gemini using the item descriptions
    items_list = "\n".join([f"ID: {item[0]}, Description: {item[1]}" for item in items])
    user_message = f"{user_message} Here is the list of items:\n{items_list}\n\nUsing this list, which item matches the closest to my message? Only return the ID of the matching item. If nothing matches, say 'I cannot find your lost item, sorry!' Make sure the match makes sense, remeber when it is a reach just to be on the safer side say the apology"

    # Send the message to the Gemini API
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents=user_message
    )

    ai_reply = response.text
   

    # Extract the ID from the response text
    if ai_reply.lower() == "i cannot find your lost item, sorry!":
        return jsonify({'reply': ai_reply})
    
    # Extract item ID from the AI reply (make sure it is an integer)
    try:
        item_id = int(ai_reply.strip())  # Ensure the response is an integer ID
    except ValueError:
        item_id = 0
    
    # Query the database for the item based on the extracted ID
    cursor.execute('''
        SELECT id, description, location, photo_filename, timestamp FROM items WHERE id = ?
    ''', (item_id,))
    item = cursor.fetchone()

    # If the item is found, return the details, otherwise return an error
    if item:
        item_details = item[1] + " at " + item[2]
        return jsonify({'reply': f"I found: {item_details}", 'photo': f"../uploads/{item[3]}" })
    else:
        return jsonify({'reply': ai_reply})


# API route to report a lost item
@app.route('/api/report', methods=['POST'])
def report_item():
    description = request.form.get('description')
    location = request.form.get('location')
    photo = request.files.get('photo')

    if photo:
        photo_filename = sanitize_filename(photo.filename)
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
    else:
        photo_filename = None

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute(''' 
        SELECT * FROM items WHERE description = ? AND location = ? AND photo_filename = ?
    ''', (description, location, photo_filename))
    
    existing_item = cursor.fetchone()
    message = ""
    if existing_item:
        message = "Item already exists!"
    else:
        cursor.execute('''
            INSERT INTO items (description, location, photo_filename) 
            VALUES (?, ?, ?)
        ''', (description, location, photo_filename))

        conn.commit()
        message = "Item added successfully!"
    conn.close()

    return jsonify({"message": message})

# API route to fetch top items with a limit
@app.route('/api/top_items', methods=['POST'])
def get_top_items():
    data = request.get_json() 
    limit = data.get("limit")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if limit == -1:
        cursor.execute('''
            SELECT id, description, location, photo_filename, timestamp FROM items
            ORDER BY timestamp DESC
        ''')
    else:
        cursor.execute('''
            SELECT id, description, location, photo_filename, timestamp FROM items
            ORDER BY timestamp DESC LIMIT 3
        ''',)

    items = cursor.fetchall()
    
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

# API route to remove an item from the database
@app.route('/api/remove_item/<int:item_id>', methods=['DELETE'])
def remove_item(item_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Fetch the photo filename associated with the item to be deleted
    cursor.execute('''
        SELECT photo_filename FROM items WHERE id = ?
    ''', (item_id,))
    item = cursor.fetchone()

    if item:
        photo_filename = item[0]

        # Delete the item from the database
        cursor.execute('''
            DELETE FROM items WHERE id = ?
        ''', (item_id,))

        # Commit the changes to the database
        conn.commit()

        # Remove the photo file if no other item is using it
        remove_unused_photo(photo_filename)

        message = f"Item {item_id} and its photo {photo_filename} removed successfully!"
    else:
        message = f"Item {item_id} not found."

    conn.close()

    return jsonify({"message": message})

# Function to remove the photo if it is not used by any other item
def remove_unused_photo(photo_filename):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Check if any other items are using the same photo
    cursor.execute('''
        SELECT COUNT(*) FROM items WHERE photo_filename = ?
    ''', (photo_filename,))
    count = cursor.fetchone()[0]

    # If no other items are using the photo, delete the photo from the uploads folder
    if count == 0 and photo_filename:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
        if os.path.exists(photo_path):
            os.remove(photo_path)  # Remove the photo file
            print(f"Removed unused photo: {photo_filename}")

    conn.close()

if __name__ == '__main__':
    app.run(debug=True)
