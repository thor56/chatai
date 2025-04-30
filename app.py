from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import requests
import json
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(minutes=30)  # Set session timeout

# Initialize SQLite database for user authentication
db = SQLAlchemy(app)

# Initialize MongoDB connection
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["conversation_branches"]
conversations = mongo_db["conversation"]
messages = mongo_db["messages"]
branches = mongo_db["branches"]

# Gemini API setup
GEMINI_API_KEY = 'AIzaSyDSGJdzVHFCNynXmuK-KUftyZeLjVPSxYA'
GEMINI_MODEL = "gemini-2.0-flash"

# Define User model for SQLite
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

# Create tables using a function
def create_tables():
    with app.app_context():
        db.create_all()

# Run this function once at startup
create_tables()

# Function to call Gemini API
def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

# Route for home page
@app.route('/')
def index():
    return render_template('index.html')

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        
        # Check if username already exists
        existing_user_by_username = User.query.filter_by(username=username).first()
        if existing_user_by_username:
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        
        # Check if email already exists
        existing_user_by_email = User.query.filter_by(email=email).first()
        if existing_user_by_email:
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
        
        # Hash the password before storing - using default method
        hashed_password = generate_password_hash(password)
        
        # Create new user
        new_user = User(username=username, email=email, password=hashed_password)
        
        # Add user to database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Find user by username
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    
    return render_template('login.html')

# Route for user dashboard (protected)
@app.route('/dashboard')
def dashboard():
    # Check if user is logged in
    if 'user_id' in session:
        # Get conversations for this user
        user_conversations = list(conversations.find({"user_id": str(session['user_id'])}))
        # Convert ObjectId to string for JSON serialization
        for conv in user_conversations:
            conv['_id'] = str(conv['_id'])
            if 'branch_id' in conv:
                conv['branch_id'] = str(conv['branch_id'])
        
        return render_template('dashboard.html', username=session['username'], conversations=user_conversations)
    else:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

# Route for user logout
@app.route('/logout')
def logout():
    # Remove user from session
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

#Route for creating a new conversation
@app.route('/conversation/new')
def new_conversation():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to start a conversation.', 'warning')
        return redirect(url_for('login'))
    
    # Create a new conversation
    conversation = {
        "title": "New Conversation",
        "model": GEMINI_MODEL,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "user_id": str(session['user_id'])
    }
    conversation_id = conversations.insert_one(conversation).inserted_id
    
    # Create a new branch
    branch = {
        "conversation_id": conversation_id,
        "parent_branch_id": None,
        "created_at": datetime.utcnow(),
        "description": "Initial branch"
    }
    branch_id = branches.insert_one(branch).inserted_id
    
    # Update conversation with branch_id
    conversations.update_one(
        {"_id": conversation_id},
        {"$set": {"branch_id": branch_id}}
    )
    
    return redirect(url_for('conversation', conversation_id=str(conversation_id)))


# Route for viewing a conversation
# Route for viewing a conversation
@app.route('/conversation/<conversation_id>')
def conversation(conversation_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to view conversations.', 'warning')
        return redirect(url_for('login'))
    
    try:
        # Convert string ID to ObjectId
        conv_obj_id = ObjectId(conversation_id)
        
        # Get conversation details
        conversation = conversations.find_one({"_id": conv_obj_id})
        
        # Check if conversation exists and belongs to the current user
        if not conversation or conversation['user_id'] != str(session['user_id']):
            flash('Conversation not found or access denied.', 'danger')
            return redirect(url_for('dashboard'))
        
        # Get messages for this conversation
        conversation_messages = list(messages.find({"conversation_id": conv_obj_id}).sort("timestamp", 1))
        
        # Convert ObjectId to string for each message
        for msg in conversation_messages:
            msg['_id'] = str(msg['_id'])
        
        # Convert parent_conversation_id to string if it exists
        if 'parent_conversation_id' in conversation:
            conversation['parent_conversation_id'] = str(conversation['parent_conversation_id'])
        
        return render_template('conversation.html', 
                               conversation=conversation, 
                               messages=conversation_messages,
                               conversation_id=conversation_id)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

# API route for sending a message and getting a response
# API route for sending a message and getting a response
@app.route('/api/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    message_text = data.get('message')
    conversation_id = data.get('conversation_id')
    
    if not message_text or not conversation_id:
        return jsonify({"error": "Missing message or conversation ID"}), 400
    
    try:
        # Convert string ID to ObjectId
        conv_obj_id = ObjectId(conversation_id)
        
        # Get conversation details
        conversation = conversations.find_one({"_id": conv_obj_id})
        
        # Check if conversation exists and belongs to the current user
        if not conversation or conversation['user_id'] != str(session['user_id']):
            return jsonify({"error": "Conversation not found or access denied"}), 403
        
        # Save user message
        timestamp = datetime.utcnow()
        user_message = {
            "conversation_id": conv_obj_id,
            "sender": "user",
            "text": message_text,
            "timestamp": timestamp
        }
        user_message_id = messages.insert_one(user_message).inserted_id
        
        # Call Gemini API
        response = call_gemini(message_text)
        
        if response and "candidates" in response:
            ai_text = response["candidates"][0]["content"]["parts"][0]["text"]
            
            # Save AI response
            ai_message = {
                "conversation_id": conv_obj_id,
                "sender": "ai",
                "text": ai_text,
                "timestamp": datetime.utcnow()
            }
            ai_message_id = messages.insert_one(ai_message).inserted_id
            
            # Update conversation's updated_at field
            conversations.update_one(
                {"_id": conv_obj_id},
                {"$set": {"updated_at": datetime.utcnow()}}
            )
            
            return jsonify({
                "success": True,
                "ai_response": ai_text,
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": str(ai_message_id)  # Return the message ID for branching
            })
        else:
            return jsonify({"error": "Failed to get AI response"}), 500
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Route for updating conversation title
@app.route('/api/update_title', methods=['POST'])
def update_title():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    title = data.get('title')
    conversation_id = data.get('conversation_id')
    
    if not title or not conversation_id:
        return jsonify({"error": "Missing title or conversation ID"}), 400
    
    try:
        # Convert string ID to ObjectId
        conv_obj_id = ObjectId(conversation_id)
        
        # Update conversation title
        result = conversations.update_one(
            {"_id": conv_obj_id, "user_id": str(session['user_id'])},
            {"$set": {"title": title, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Conversation not found or not modified"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Route for creating a branch conversation
@app.route('/conversation/branch/<conversation_id>/<message_id>')
def create_branch(conversation_id, message_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to branch conversations.', 'warning')
        return redirect(url_for('login'))
    
    try:
        # Convert string IDs to ObjectId
        conv_obj_id = ObjectId(conversation_id)
        msg_obj_id = ObjectId(message_id)
        
        # Get the original conversation
        original_conversation = conversations.find_one({"_id": conv_obj_id})
        if not original_conversation or original_conversation['user_id'] != str(session['user_id']):
            flash('Conversation not found or access denied.', 'danger')
            return redirect(url_for('dashboard'))

        # Get the message we're branching from
        branch_message = messages.find_one({"_id": msg_obj_id})
        if not branch_message or str(branch_message['conversation_id']) != conversation_id:
            flash('Message not found or does not belong to this conversation.', 'danger')
            return redirect(url_for('conversation', conversation_id=conversation_id))
        
        # Create a new conversation with reference to parent
        branch_conversation = {
            "title": f"Branch from '{original_conversation['title']}'",
            "model": GEMINI_MODEL,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_id": str(session['user_id']),
            "parent_conversation_id": conv_obj_id,
            "parent_message_id": msg_obj_id
        }
        new_conversation_id = conversations.insert_one(branch_conversation).inserted_id
        
        # Create a new branch
        branch = {
            "conversation_id": new_conversation_id,
            "parent_branch_id": original_conversation.get('branch_id'),
            "created_at": datetime.utcnow(),
            "description": f"Branch from message: {branch_message['text'][:50]}..."
        }
        branch_id = branches.insert_one(branch).inserted_id
        
        # Update conversation with branch_id
        conversations.update_one(
            {"_id": new_conversation_id},
            {"$set": {"branch_id": branch_id}}
        )
        
        # Copy the branched message as context
        context_message = {
            "conversation_id": new_conversation_id,
            "sender": branch_message['sender'],
            "text": branch_message['text'],
            "timestamp": datetime.utcnow(),
            "is_context": True
        }
        messages.insert_one(context_message)
        
        return redirect(url_for('conversation', conversation_id=str(new_conversation_id)))
    
    except Exception as e:
        flash(f'Error creating branch: {str(e)}', 'danger')
        return redirect(url_for('conversation', conversation_id=conversation_id))
    
# Add to your existing code in app.py
@app.route('/api/get_branches_for_message/<message_id>')
def get_branches_for_message(message_id):
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    try:
        msg_obj_id = ObjectId(message_id)
        
        # Find all conversations that branch from this message
        branch_conversations = list(conversations.find({
            "parent_message_id": msg_obj_id,
            "user_id": str(session['user_id'])
        }))
        
        # Format the results
        branches = []
        for conv in branch_conversations:
            branches.append({
                "conversation_id": str(conv["_id"]),
                "title": conv["title"],
                "created_at": conv["created_at"].isoformat()
            })
        
        return jsonify({"branches": branches})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_conversation', methods=['POST'])
def delete_conversation():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    
    if not conversation_id:
        return jsonify({"error": "Missing conversation ID"}), 400
    
    try:
        # Convert string ID to ObjectId
        conv_obj_id = ObjectId(conversation_id)
        
        # Check if conversation exists and belongs to the current user
        conversation = conversations.find_one({"_id": conv_obj_id, "user_id": str(session['user_id'])})
        if not conversation:
            return jsonify({"error": "Conversation not found or access denied"}), 403
        
        # Get the branch_id for this conversation
        branch_id = conversation.get('branch_id')
        
        # Delete all messages belonging to this conversation
        messages.delete_many({"conversation_id": conv_obj_id})
        
        # Delete the conversation
        conversations.delete_one({"_id": conv_obj_id})
        
        # Delete the branch if it exists
        if branch_id:
            branches.delete_one({"_id": ObjectId(branch_id)})
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error deleting conversation: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)