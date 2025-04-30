from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pymongo import MongoClient
from datetime import timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
mongo_db = mongo_client["conversation_branches"]
conversations = mongo_db["conversation"]
messages = mongo_db["messages"]
branches = mongo_db["branches"]

def create_app():
    app = Flask(__name__)
    
    # Load configuration from environment variables
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key_here')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///users.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Set session lifetime from environment variable
    session_lifetime = int(os.getenv('SESSION_LIFETIME_MINUTES', '30'))
    app.permanent_session_lifetime = timedelta(minutes=session_lifetime)

    # Initialize extensions with app
    db.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.conversation import conversation_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(conversation_bp)
    app.register_blueprint(api_bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app