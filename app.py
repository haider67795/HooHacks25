from flask import Flask, render_template, jsonify, request
import sqlite3

# Initialize the Flask app
app = Flask(__name__)

# Function to get data from SQLite database
def get_users():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# Homepage route that renders the HTML page
@app.route('/')
def home():
    return render_template('index.html')

# API route to fetch user data from the database
@app.route('/api/users', methods=['GET'])
def api_users():
    users = get_users()
    # Convert data into a dictionary and return it as JSON
    return jsonify([{"id": user[0], "name": user[1], "email": user[2]} for user in users])

# API route to add a new user (via POST)
@app.route('/api/users', methods=['POST'])
def add_user():
    name = request.json.get('name')
    email = request.json.get('email')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    conn.close()
    return jsonify({"message": "User added successfully!"}), 201

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
