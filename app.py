import os
import datetime
from collections import defaultdict, deque
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, send

# --- Initialization ---

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yet_another_super_secret_key_!@#123')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- State Management ---

MAX_HISTORY_LEN = 50

# { room_name: { sid: username } }
rooms_users = defaultdict(dict)

# { room_name: deque([message_dict, ...], maxlen=MAX_HISTORY_LEN) }
message_history = defaultdict(lambda: deque(maxlen=MAX_HISTORY_LEN))

# { sid: current_room_name }
user_current_room = {}

# --- Helper Functions ---

def get_timestamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC")

def get_user_list_for_room(room_name):
    if room_name in rooms_users:
        return list(rooms_users[room_name].values())
    return []

def add_message_to_history(room_name, message_data):
    message_history[room_name].append(message_data)

def get_message_history_for_room(room_name):
    return list(message_history[room_name])

# --- HTTP Routes ---

@app.route('/')
def index():
    return render_template('index.html')

# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f"Client connected: {sid}")
    # User needs to join a room first

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f"Client disconnected: {sid}")
    current_room = user_current_room.pop(sid, None)

    if current_room and current_room in rooms_users and sid in rooms_users[current_room]:
        username = rooms_users[current_room].pop(sid)
        print(f"User {username} removed from room {current_room}")

        # Update user list for the room they left
        emit('update_user_list', {
            'room': current_room,
            'users': get_user_list_for_room(current_room)
            }, room=current_room) # Send only to users remaining in that room

        # Announce departure in that room
        status_msg = {
            'msg': f"{username} has left the room.",
            'timestamp': get_timestamp(),
            'type': 'status'
        }
        emit('receive_message', status_msg, room=current_room)
        add_message_to_history(current_room, status_msg)

        if not rooms_users[current_room]: # If room is empty, clear its history
            print(f"Room {current_room} is now empty, clearing history.")
            del rooms_users[current_room]
            if current_room in message_history:
                del message_history[current_room]
    else:
         print(f"Disconnected client {sid} was not in a known room or had no username.")


@socketio.on('join_room')
def handle_join_room(data):
    sid = request.sid
    username = data.get('username', '').strip()
    new_room = data.get('room', 'general').strip() # Default to 'general'

    if not username:
        emit('error', {'msg': 'Username cannot be empty.'}, room=sid)
        return
    if not new_room:
         emit('error', {'msg': 'Room name cannot be empty.'}, room=sid)
         return

    # Check if username is taken *in the target room*
    if new_room in rooms_users and username.lower() in [name.lower() for name in rooms_users[new_room].values()]:
         emit('error', {'msg': f'Username "{username}" is already taken in room "{new_room}". Please choose another.'}, room=sid)
         return

    # Leave previous room if exists
    previous_room = user_current_room.get(sid)
    if previous_room and previous_room in rooms_users and sid in rooms_users[previous_room]:
         # Remove user from previous room's state
         prev_username = rooms_users[previous_room].pop(sid, None)
         leave_room(previous_room)
         print(f"User {prev_username} left room {previous_room}")

         # Update user list and notify users in the *previous* room
         emit('update_user_list', {
            'room': previous_room,
            'users': get_user_list_for_room(previous_room)
            }, room=previous_room)
         status_msg_leave = {
            'msg': f"{prev_username} has left the room.",
            'timestamp': get_timestamp(),
            'type': 'status'
         }
         emit('receive_message', status_msg_leave, room=previous_room)
         add_message_to_history(previous_room, status_msg_leave)
         if not rooms_users[previous_room]: # Cleanup empty previous room
             print(f"Room {previous_room} is now empty, clearing history.")
             del rooms_users[previous_room]
             if previous_room in message_history:
                 del message_history[previous_room]


    # Join the new room
    join_room(new_room)
    rooms_users[new_room][sid] = username
    user_current_room[sid] = new_room
    print(f"User {username} ({sid}) joined room: {new_room}")

    # Send confirmation and history to the joining user
    emit('room_joined', {
        'username': username,
        'room': new_room,
        'history': get_message_history_for_room(new_room)
        }, room=sid)

    # Update user list for everyone in the *new* room
    emit('update_user_list', {
        'room': new_room,
        'users': get_user_list_for_room(new_room)
        }, room=new_room) # Send only to users in this room

    # Announce arrival to others in the *new* room
    status_msg_join = {
        'msg': f"{username} has joined the room!",
        'timestamp': get_timestamp(),
        'type': 'status'
    }
    emit('receive_message', status_msg_join, room=new_room, include_self=False) # Don't announce to self
    add_message_to_history(new_room, status_msg_join)


@socketio.on('send_message')
def handle_send_message(data):
    sid = request.sid
    message_text = data.get('msg', '').strip()
    current_room = user_current_room.get(sid)
    username = rooms_users.get(current_room, {}).get(sid)

    if not current_room or not username:
        emit('error', {'msg': 'You must be in a room with a username to send messages.'}, room=sid)
        print(f"Message attempt from {sid} without username/room.")
        return

    if not message_text:
        print(f"Empty message received from {username} in {current_room}.")
        return

    print(f"Message in {current_room} from {username}: {message_text}")

    message_data = {
        'msg': message_text,
        'username': username,
        'timestamp': get_timestamp(),
        'type': 'user',
        'room': current_room
    }

    # Broadcast message to the correct room
    emit('receive_message', message_data, room=current_room)
    # Add message to history for that room
    add_message_to_history(current_room, message_data)


@socketio.on('typing')
def handle_typing(data):
    sid = request.sid
    is_typing = data.get('is_typing', False)
    current_room = user_current_room.get(sid)
    username = rooms_users.get(current_room, {}).get(sid)

    if not current_room or not username:
        return # Ignore typing if user isn't properly set up in a room

    # Broadcast typing status to the correct room *except* the sender
    emit('user_typing', {
        'username': username,
        'is_typing': is_typing,
        'room': current_room
    }, room=current_room, include_self=False)

# --- Main Execution ---

if __name__ == '__main__':
    print("Starting Advanced Flask-SocketIO server on http://localhost:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=True)
