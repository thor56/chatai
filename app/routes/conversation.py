from flask import Blueprint, render_template, redirect, url_for, flash, session
from datetime import datetime
from bson.objectid import ObjectId
from app import conversations, messages, branches

conversation_bp = Blueprint('conversation', __name__)

@conversation_bp.route('/')
def index():
    return render_template('index.html')

@conversation_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('auth.login'))
    
    user_conversations = list(conversations.find({"user_id": str(session['user_id'])}))
    for conv in user_conversations:
        conv['_id'] = str(conv['_id'])
        if 'branch_id' in conv:
            conv['branch_id'] = str(conv['branch_id'])
    
    return render_template('dashboard.html', username=session['username'], conversations=user_conversations)

@conversation_bp.route('/conversation/new')
def new_conversation():
    if 'user_id' not in session:
        flash('Please log in to start a conversation.', 'warning')
        return redirect(url_for('auth.login'))
    
    conversation = {
        "title": "New Conversation",
        "model": "gemini-2.0-flash",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "user_id": str(session['user_id'])
    }
    conversation_id = conversations.insert_one(conversation).inserted_id
    
    branch = {
        "conversation_id": conversation_id,
        "parent_branch_id": None,
        "created_at": datetime.utcnow(),
        "description": "Initial branch"
    }
    branch_id = branches.insert_one(branch).inserted_id
    
    conversations.update_one(
        {"_id": conversation_id},
        {"$set": {"branch_id": branch_id}}
    )
    
    return redirect(url_for('conversation.conversation', conversation_id=str(conversation_id)))

@conversation_bp.route('/conversation/<conversation_id>')
def conversation(conversation_id):
    if 'user_id' not in session:
        flash('Please log in to view conversations.', 'warning')
        return redirect(url_for('auth.login'))
    
    try:
        conv_obj_id = ObjectId(conversation_id)
        conversation = conversations.find_one({"_id": conv_obj_id})
        
        if not conversation or conversation['user_id'] != str(session['user_id']):
            flash('Conversation not found or access denied.', 'danger')
            return redirect(url_for('conversation.dashboard'))
        
        conversation_messages = list(messages.find({"conversation_id": conv_obj_id}).sort("timestamp", 1))
        
        for msg in conversation_messages:
            msg['_id'] = str(msg['_id'])
        
        if 'parent_conversation_id' in conversation:
            conversation['parent_conversation_id'] = str(conversation['parent_conversation_id'])
        
        return render_template('conversation/conversation.html', 
                             conversation=conversation, 
                             messages=conversation_messages,
                             conversation_id=conversation_id)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('conversation.dashboard'))

@conversation_bp.route('/conversation/branch/<conversation_id>/<message_id>')
def create_branch(conversation_id, message_id):
    if 'user_id' not in session:
        flash('Please log in to branch conversations.', 'warning')
        return redirect(url_for('auth.login'))
    
    try:
        conv_obj_id = ObjectId(conversation_id)
        msg_obj_id = ObjectId(message_id)
        
        original_conversation = conversations.find_one({"_id": conv_obj_id})
        if not original_conversation or original_conversation['user_id'] != str(session['user_id']):
            flash('Conversation not found or access denied.', 'danger')
            return redirect(url_for('conversation.dashboard'))

        branch_message = messages.find_one({"_id": msg_obj_id})
        if not branch_message or str(branch_message['conversation_id']) != conversation_id:
            flash('Message not found or does not belong to this conversation.', 'danger')
            return redirect(url_for('conversation.conversation', conversation_id=conversation_id))
        
        branch_conversation = {
            "title": f"Branch from '{original_conversation['title']}'",
            "model": "gemini-2.0-flash",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_id": str(session['user_id']),
            "parent_conversation_id": conv_obj_id,
            "parent_message_id": msg_obj_id
        }
        new_conversation_id = conversations.insert_one(branch_conversation).inserted_id
        
        branch = {
            "conversation_id": new_conversation_id,
            "parent_branch_id": original_conversation.get('branch_id'),
            "created_at": datetime.utcnow(),
            "description": f"Branch from message: {branch_message['text'][:50]}..."
        }
        branch_id = branches.insert_one(branch).inserted_id
        
        conversations.update_one(
            {"_id": new_conversation_id},
            {"$set": {"branch_id": branch_id}}
        )
        
        context_message = {
            "conversation_id": new_conversation_id,
            "sender": branch_message['sender'],
            "text": branch_message['text'],
            "timestamp": datetime.utcnow(),
            "is_context": True
        }
        messages.insert_one(context_message)
        
        return redirect(url_for('conversation.conversation', conversation_id=str(new_conversation_id)))
    
    except Exception as e:
        flash(f'Error creating branch: {str(e)}', 'danger')
        return redirect(url_for('conversation.conversation', conversation_id=conversation_id)) 