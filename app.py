import os
import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, send

app = Flask(__name__)
# Use environment variable for secret key in production, fallback for local dev
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secure_and_hard_to_guess_secret_key_!@#$%^&*()_+')
# Configure CORS (Cross-Origin Resource Sharing) - Allow all origins for simplicity,
# but restrict this to your frontend's domain in production for security.
# Example for production: cors_allowed_origins="https://your-chat-app-domain.vercel.app"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet') # eventlet is good for Vercel

# In-memory storage for users and their SIDs (Session IDs)
# { sid: username }
connected_users = {}

# Helper function to get current timestamp
def get_timestamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# --- HTTP Routes ---
@app.route('/')
def index():
    """Serves the main chat page."""
    return render_template('index.html')

# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print(f"Client connected: {request.sid}")
    # Don't add user yet, wait for 'set_username' event

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    print(f"Client disconnected: {request.sid}")
    username = connected_users.pop(request.sid, None) # Remove user and get username
    if username:
        # Notify others that the user left
        emit('user_status', {
            'msg': f"{username} has left the chat.",
            'timestamp': get_timestamp(),
            'type': 'status'
        }, broadcast=True)
        # Update the user list for everyone
        emit('update_user_list', list(connected_users.values()), broadcast=True)
    else:
        print(f"Disconnected client {request.sid} had no username set.")


@socketio.on('set_username')
def handle_set_username(data):
    """Sets the username for a connected client."""
    username = data.get('username', '').strip()
    sid = request.sid

    if not username:
        emit('error', {'msg': 'Username cannot be empty.'}, room=sid)
        return

    # Check if username is already taken (case-insensitive check)
    if username.lower() in [name.lower() for name in connected_users.values()]:
         emit('error', {'msg': f'Username "{username}" is already taken. Please choose another.'}, room=sid)
         return

    # Store the user
    connected_users[sid] = username
    print(f"Username set for {sid}: {username}")

    # Send confirmation back to the user
    emit('username_set', {'username': username}, room=sid)

    # Send updated user list to everyone
    emit('update_user_list', list(connected_users.values()), broadcast=True)

    # Announce the new user to everyone else
    emit('user_status', {
        'msg': f"{username} has joined the chat!",
        'timestamp': get_timestamp(),
        'type': 'status'
    }, broadcast=True, include_self=False) # Don't send join message to the user who just joined

    # Send a welcome message only to the newly connected user
    emit('receive_message', {
            'msg': f"Welcome to the chat, {username}!",
            'username': 'System',
            'timestamp': get_timestamp(),
            'type': 'system'
        }, room=sid)


@socketio.on('send_message')
def handle_send_message(data):
    """Handles incoming chat messages."""
    message_text = data.get('msg', '').strip()
    sid = request.sid
    username = connected_users.get(sid)

    if not username:
        emit('error', {'msg': 'You must set a username before sending messages.'}, room=sid)
        print(f"Message attempt from {sid} without username.")
        return

    if not message_text:
        # Maybe just ignore empty messages silently on the server
        print(f"Empty message received from {username} ({sid}).")
        return

    print(f"Message from {username} ({sid}): {message_text}")

    # Broadcast the message to everyone (including sender)
    emit('receive_message', {
        'msg': message_text,
        'username': username,
        'timestamp': get_timestamp(),
        'type': 'user'
    }, broadcast=True)


@socketio.on('typing')
def handle_typing(data):
    """Handles typing indicator events."""
    is_typing = data.get('is_typing', False)
    sid = request.sid
    username = connected_users.get(sid)

    if not username:
        # Ignore typing if username isn't set
        return

    # Broadcast typing status to everyone *except* the sender
    emit('user_typing', {
        'username': username,
        'is_typing': is_typing
    }, broadcast=True, include_self=False)


# --- Main Execution ---
# This part is mainly for local development. Vercel uses a WSGI server like Gunicorn.
if __name__ == '__main__':
    print("Starting Flask-SocketIO development server on http://localhost:5000")
    # Use eventlet for async operations, required for SocketIO production deploy
    # Make sure 'eventlet' is in requirements.txt
    # Host '0.0.0.0' makes it accessible on your local network
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
