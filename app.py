import os
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
# Generate a secret key or use an environment variable
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'fallback_secret_key_replace_me!')
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

users = {} # sid -> username
user_rooms = {} # sid -> room (if implementing rooms later)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('request_name')

@socketio.on('set_name')
def handle_set_name(name):
    clean_name = str(name).strip()
    if clean_name and request.sid not in users:
        users[request.sid] = clean_name
        print(f'User {request.sid} set name to: {users[request.sid]}')
        emit('name_accepted', {'name': clean_name, 'sid': request.sid})
        emit('user_list_update', {'users': list(users.values())}, broadcast=True)
        emit('notification', {'msg': f'{clean_name} has joined the chat.'}, broadcast=True, include_self=False)
    elif clean_name and request.sid in users:
        # Handle case where user might reconnect or try setting name again
        emit('name_accepted', {'name': users[request.sid], 'sid': request.sid})
        emit('user_list_update', {'users': list(users.values())}) # Send only to them
    else:
        emit('request_name') # Ask again if name is invalid


@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in users:
        disconnected_user_name = users.pop(request.sid)
        print(f'User {disconnected_user_name} left.')
        emit('user_list_update', {'users': list(users.values())}, broadcast=True)
        emit('notification', {'msg': f'{disconnected_user_name} has left the chat.'}, broadcast=True)
    if request.sid in user_rooms:
        # Handle room leaving if implemented
        del user_rooms[request.sid]


@socketio.on('send_message')
def handle_send_message(data):
    if request.sid in users and 'msg' in data:
        message_text = str(data['msg']).strip()
        if message_text:
            username = users[request.sid]
            print(f'Message from {username} ({request.sid}): {message_text}')
            emit('new_message', {
                'name': username,
                'msg': message_text,
                'sid': request.sid
            }, broadcast=True)
        else:
             print(f"Empty message received from {users.get(request.sid, 'Unknown SID ' + request.sid)}")
    elif request.sid not in users:
         print(f"Message received from unknown user {request.sid}")
         emit('request_name') # Ask for name if message sent before setting name


if __name__ == '__main__':
    import eventlet
    print("Starting server on http://127.0.0.1:5000")
    # Use 0.0.0.0 to be accessible externally if needed, Vercel handles this
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
    # For local dev without eventlet:
    # socketio.run(app, debug=True, allow_unsafe_werkzeug=True, host='0.0.0.0', port=5000)