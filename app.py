import os
import datetime
from collections import defaultdict, deque
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# --- Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_secret_key_123!@#')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- State Management (In-Memory) ---
MAX_HISTORY_LEN = 50
rooms_users = defaultdict(dict) # { room_name: { sid: username } }
message_history = defaultdict(lambda: deque(maxlen=MAX_HISTORY_LEN)) # { room_name: deque([message_dict, ...]) }
user_current_room = {} # { sid: current_room_name }

# --- Helper Functions ---
def get_timestamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC")

def get_user_list_for_room(room_name):
    return list(rooms_users.get(room_name, {}).values())

def add_message_to_history(room_name, message_data):
    message_history[room_name].append(message_data)

def get_message_history_for_room(room_name):
    return list(message_history.get(room_name, []))

def cleanup_room_if_empty(room_name):
    if room_name in rooms_users and not rooms_users[room_name]:
        print(f"Cleaning up empty room: {room_name}")
        del rooms_users[room_name]
        if room_name in message_history:
            del message_history[room_name]

# --- HTTP Routes ---
@app.route('/')
def index():
    return render_template('index.html')

# --- SocketIO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f"Client disconnected: {sid}")
    current_room = user_current_room.pop(sid, None)

    if current_room and current_room in rooms_users and sid in rooms_users[current_room]:
        username = rooms_users[current_room].pop(sid)
        print(f"User {username} removed from room {current_room}")

        leave_room(current_room)

        emit('update_user_list', {
            'room': current_room,
            'users': get_user_list_for_room(current_room)
            }, room=current_room)

        status_msg = {
            'msg': f"{username} has left the room.",
            'timestamp': get_timestamp(),
            'type': 'status',
            'room': current_room # Add room context to status message
        }
        emit('receive_message', status_msg, room=current_room)
        add_message_to_history(current_room, status_msg)
        cleanup_room_if_empty(current_room)

@socketio.on('join_room')
def handle_join_room(data):
    sid = request.sid
    username = data.get('username', '').strip()
    new_room = data.get('room', 'general').strip().lower() # Use lowercase room names

    if not username or not new_room:
        emit('error', {'msg': 'Username and room name cannot be empty.'}, room=sid)
        return

    if new_room in rooms_users and username.lower() in [name.lower() for name in rooms_users[new_room].values()]:
         emit('error', {'msg': f'Username "{username}" is taken in room "{new_room}".'}, room=sid)
         return

    # --- Leave previous room logic ---
    previous_room = user_current_room.get(sid)
    if previous_room and previous_room != new_room:
         if previous_room in rooms_users and sid in rooms_users[previous_room]:
             prev_username = rooms_users[previous_room].pop(sid, username) # Use provided username as fallback
             leave_room(previous_room)
             print(f"User {prev_username} left room {previous_room}")

             emit('update_user_list', {
                'room': previous_room,
                'users': get_user_list_for_room(previous_room)
                }, room=previous_room)
             status_msg_leave = {
                'msg': f"{prev_username} has left the room.",
                'timestamp': get_timestamp(),
                'type': 'status',
                'room': previous_room
             }
             emit('receive_message', status_msg_leave, room=previous_room)
             add_message_to_history(previous_room, status_msg_leave)
             cleanup_room_if_empty(previous_room)

    # --- Join new room logic ---
    if user_current_room.get(sid) != new_room: # Only join if not already in the room
        join_room(new_room)

    rooms_users[new_room][sid] = username
    user_current_room[sid] = new_room
    print(f"User {username} ({sid}) joined room: {new_room}")

    emit('room_joined', {
        'username': username,
        'room': new_room,
        'history': get_message_history_for_room(new_room)
        }, room=sid)

    emit('update_user_list', {
        'room': new_room,
        'users': get_user_list_for_room(new_room)
        }, room=new_room)

    status_msg_join = {
        'msg': f"{username} has joined the room!",
        'timestamp': get_timestamp(),
        'type': 'status',
        'room': new_room
    }
    emit('receive_message', status_msg_join, room=new_room, include_self=False)
    add_message_to_history(new_room, status_msg_join)

@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    message_text = data.get('msg', '').strip()
    current_room = user_current_room.get(sid)
    username = rooms_users.get(current_room, {}).get(sid)

    if not current_room or not username:
        emit('error', {'msg': 'Error: Not connected to a room.'}, room=sid)
        return

    if not message_text:
        return

    message_data = {
        'msg': message_text,
        'username': username,
        'timestamp': get_timestamp(),
        'type': 'user',
        'room': current_room
    }

    emit('receive_message', message_data, room=current_room)
    add_message_to_history(current_room, message_data)

@socketio.on('typing')
def handle_typing(data):
    sid = request.sid
    is_typing = data.get('is_typing', False)
    current_room = user_current_room.get(sid)
    username = rooms_users.get(current_room, {}).get(sid)

    if not current_room or not username:
        return

    emit('user_typing', {
        'username': username,
        'is_typing': is_typing,
        'room': current_room
    }, room=current_room, include_self=False)

# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Chat Server...")
    socketio.run(app, debug=False, host='0.0.0.0', port=os.environ.get('PORT', 5000))
