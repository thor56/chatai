# ChatAI

A Flask-based web application for AI-powered conversations.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/ktvgs/chatai.git
   cd chatai
   ```

2. **Create and activate a virtual environment**
   ```bash
   # On Windows
   python -m venv myenv
   myenv\Scripts\activate

   # On macOS/Linux
   python3 -m venv myenv
   source myenv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with the following variables:
   ```
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here (Optional)
   ```

5. **Setting up the database**
   ```bash
   Connect a new or exsiting MongoDB server and change the db url in the .env file to connect to your db (either local or web) 
   ```

6. **Run the application**
   ```bash
   flask run
   ```

   The application will be available at `http://localhost:5000`

## Development

- The application uses Flask as the web framework
- SQLAlchemy for database operations
- MongoDB for data storage
- Flask-SQLAlchemy for ORM
- Gunicorn for production deployment

## Features

- User authentication (login/register)
- AI-powered conversations
- Dashboard interface
- Responsive web design

## API Documentation

### Authentication APIs

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/register` | POST | Register a new user | `{ username, email, password, confirm_password }` | Redirects to login on success |
| `/login` | POST | Authenticate user | `{ username, password }` | Redirects to dashboard on success |
| `/logout` | GET | Logout user | None | Redirects to index page |

### Conversation APIs

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/send_message` | POST | Send a message to AI and get response | `{ message, conversation_id }` | `{ success, ai_response, timestamp, message_id }` |
| `/api/update_title` | POST | Update conversation title | `{ title, conversation_id }` | `{ success }` |
| `/api/get_branches_for_message/<message_id>` | GET | Get all branches for a message | None | `{ branches: [{ conversation_id, title, created_at }] }` |
| `/api/delete_conversation` | POST | Delete a conversation | `{ conversation_id }` | `{ success }` |

### Error Responses

All APIs return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## Project Structure

```
chatai
├─ app
│  ├─ models
│  │  ├─ user.py
│  │  └─ __init__.py
│  ├─ routes
│  │  ├─ api.py
│  │  ├─ auth.py
│  │  ├─ conversation.py
│  │  └─ __init__.py
│  ├─ static
│  │  ├─ css
│  │  │  └─ style.css
│  │  └─ js
│  ├─ templates
│  │  ├─ auth
│  │  │  ├─ login.html
│  │  │  └─ register.html
│  │  ├─ conversation
│  │  │  └─ conversation.html
│  │  ├─ dashboard.html
│  │  ├─ index.html
│  │  └─ layout.html
│  ├─ utils
│  │  ├─ ai_service.py
│  │  └─ __init__.py
│  └─ __init__.py
├─ instance
│  └─ users.db
├─ README.md
├─ .env
├─ requirements.txt
└─ run.py
```
