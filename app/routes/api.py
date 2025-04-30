from flask import Blueprint, request, jsonify, session
from datetime import datetime
from bson.objectid import ObjectId
from app import conversations, messages, branches
from app.utils.ai_service import call_gemini

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    message_text = data.get('message')
    conversation_id = data.get('conversation_id')
    
    if not message_text or not conversation_id:
        return jsonify({"error": "Missing message or conversation ID"}), 400
    
    try:
        conv_obj_id = ObjectId(conversation_id)
        conversation = conversations.find_one({"_id": conv_obj_id})
        
        if not conversation or conversation['user_id'] != str(session['user_id']):
            return jsonify({"error": "Conversation not found or access denied"}), 403
        
        timestamp = datetime.utcnow()
        user_message = {
            "conversation_id": conv_obj_id,
            "sender": "user",
            "text": message_text,
            "timestamp": timestamp
        }
        user_message_id = messages.insert_one(user_message).inserted_id
        
        response = call_gemini(message_text)
        
        if response and "candidates" in response:
            ai_text = response["candidates"][0]["content"]["parts"][0]["text"]
            
            ai_message = {
                "conversation_id": conv_obj_id,
                "sender": "ai",
                "text": ai_text,
                "timestamp": datetime.utcnow()
            }
            ai_message_id = messages.insert_one(ai_message).inserted_id
            
            conversations.update_one(
                {"_id": conv_obj_id},
                {"$set": {"updated_at": datetime.utcnow()}}
            )
            
            return jsonify({
                "success": True,
                "ai_response": ai_text,
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": str(ai_message_id)
            })
        else:
            return jsonify({"error": "Failed to get AI response"}), 500
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/update_title', methods=['POST'])
def update_title():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    title = data.get('title')
    conversation_id = data.get('conversation_id')
    
    if not title or not conversation_id:
        return jsonify({"error": "Missing title or conversation ID"}), 400
    
    try:
        conv_obj_id = ObjectId(conversation_id)
        
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

@api_bp.route('/api/get_branches_for_message/<message_id>')
def get_branches_for_message(message_id):
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
        
    try:
        msg_obj_id = ObjectId(message_id)
        
        branch_conversations = list(conversations.find({
            "parent_message_id": msg_obj_id,
            "user_id": str(session['user_id'])
        }))
        
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

@api_bp.route('/api/delete_conversation', methods=['POST'])
def delete_conversation():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    
    if not conversation_id:
        return jsonify({"error": "Missing conversation ID"}), 400
    
    try:
        conv_obj_id = ObjectId(conversation_id)
        
        conversation = conversations.find_one({"_id": conv_obj_id, "user_id": str(session['user_id'])})
        if not conversation:
            return jsonify({"error": "Conversation not found or access denied"}), 403
        
        branch_id = conversation.get('branch_id')
        
        messages.delete_many({"conversation_id": conv_obj_id})
        conversations.delete_one({"_id": conv_obj_id})
        
        if branch_id:
            branches.delete_one({"_id": ObjectId(branch_id)})
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error deleting conversation: {str(e)}")
        return jsonify({"error": str(e)}), 500 