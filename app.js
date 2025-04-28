const express = require("express");
const http = require("http");
const socketIo = require("socket.io");
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

const PORT = process.env.PORT || 3000; // Use Vercel's port or 3000 locally

// --- User Management ---
// Simple in-memory storage for users
// In a real app, you'd use a database
const users = {};

function getRandomColor() {
  const letters = '0123456789ABCDEF';
  let color = '#';
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  // Ensure slightly darker colors for better readability on white background
  // Simple check: if luminance is too high, try again (not perfect but helps)
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  if (luminance > 0.75) {
      return getRandomColor(); // Recursive call if too light
  }
  return color;
}


// Serve static files from the "public" directory
app.use(express.static(path.join(__dirname, "public")));

// Default route (optional as static serving handles index.html)
// app.get("/", (req, res) => {
//   res.sendFile(path.join(__dirname, "public", "index.html"));
// });

// --- Socket.IO Logic ---
io.on("connection", (socket) => {
  console.log(`User connected: ${socket.id}`);

  // Assign a default nickname and color
  const defaultNickname = `User_${socket.id.substring(0, 4)}`;
  users[socket.id] = {
    nickname: defaultNickname,
    color: getRandomColor()
  };

  // Send the user their assigned info
  socket.emit('your info', users[socket.id]);

  // Broadcast to others when a new user joins
  socket.broadcast.emit("system message", {
      text: `${users[socket.id].nickname} has joined the chat.`,
      type: 'join'
  });

  // Send updated user list to everyone
  io.emit('update user list', Object.values(users));


  // Listen for chat messages from a client
  socket.on("chat message", (msg) => {
    console.log(`Message from ${users[socket.id]?.nickname || 'Unknown'}: ${msg}`);
    // Broadcast the message to everyone INCLUDING the sender
    io.emit("chat message", {
        text: msg,
        sender: users[socket.id]?.nickname || 'Unknown',
        color: users[socket.id]?.color || '#000000', // Use assigned color
        id: socket.id // Send sender's socket id
    });
  });

  // Listen for nickname changes
  socket.on('change nickname', (newNickname) => {
    const oldNickname = users[socket.id]?.nickname || 'Unknown';
    const cleanNickname = newNickname.trim().substring(0, 15); // Basic sanitization & length limit

    if (cleanNickname && oldNickname !== cleanNickname) {
      users[socket.id].nickname = cleanNickname;
      console.log(`User ${socket.id} changed nickname to ${cleanNickname}`);
      // Notify everyone about the nickname change
      io.emit("system message", {
          text: `${oldNickname} is now known as ${cleanNickname}.`,
          type: 'nick_change'
      });
      // Send updated user list
       io.emit('update user list', Object.values(users));
       // Also update the user's own info display
       socket.emit('your info', users[socket.id]);
    }
  });

  // Listen for typing events
  socket.on('typing', () => {
    socket.broadcast.emit('typing', { nickname: users[socket.id]?.nickname || 'Unknown' });
  });

  socket.on('stop typing', () => {
    socket.broadcast.emit('stop typing', { nickname: users[socket.id]?.nickname || 'Unknown' });
  });


  // Handle disconnection
  socket.on("disconnect", () => {
    const user = users[socket.id];
    console.log(`User disconnected: ${socket.id}`);
    if (user) {
        // Broadcast to others that the user has left
        socket.broadcast.emit("system message", {
            text: `${user.nickname} has left the chat.`,
            type: 'leave'
        });
        delete users[socket.id]; // Remove user from the list
         // Send updated user list
        io.emit('update user list', Object.values(users));
    }
  });
});

// --- Start Server ---
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

// Export the app (required by Vercel)
module.exports = app;
