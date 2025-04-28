const http = require('http');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

const PORT = process.env.PORT || 3000;

// --- HTTP Server for serving static files ---
const server = http.createServer((req, res) => {
    if (req.url === '/' || req.url === '/index.html') {
        fs.readFile(path.join(__dirname, 'public', 'index.html'), (err, data) => {
            if (err) {
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Internal Server Error');
                console.error('Error reading index.html:', err);
            } else {
                res.writeHead(200, { 'Content-Type': 'text/html' });
                res.end(data);
            }
        });
    } else {
        // For simplicity, only serve index.html.
        // In a real app, you might serve CSS/JS files too.
        // Vercel often handles static file serving automatically from 'public'.
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
    }
});

// --- WebSocket Server ---
const wss = new WebSocket.Server({ server });

const clients = new Set();

console.log(`WebSocket server is starting on port ${PORT}`);

wss.on('connection', (ws) => {
    console.log('Client connected');
    clients.add(ws);
    
    ws.on('message', (message) => {
        console.log('Received message:', message.toString());
        try {
            // Broadcast the message to all other connected clients
            clients.forEach(client => {
                if (client !== ws && client.readyState === WebSocket.OPEN) {
                    client.send(message.toString()); // Forward the raw message string
                }
            });
        } catch (e) {
            console.error('Failed to process message or broadcast:', e);
            // Optionally send an error back to the sender
            ws.send(JSON.stringify({ type: 'error', payload: 'Invalid message format received.' }));
        }
    });
    
    ws.on('close', () => {
        console.log('Client disconnected');
        clients.delete(ws);
        // Optionally notify other users about the disconnection
        const notification = JSON.stringify({ type: 'notification', payload: 'A user has left the chat.' });
        clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(notification);
            }
        });
    });
    
    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        clients.delete(ws); // Remove client on error
    });
    
    // Send a welcome message or connection confirmation if needed
    ws.send(JSON.stringify({ type: 'notification', payload: 'Welcome to the chat!' }));
    // Notify others about the new connection
    const joinNotification = JSON.stringify({ type: 'notification', payload: 'A new user has joined the chat.' });
    clients.forEach(client => {
        if (client !== ws && client.readyState === WebSocket.OPEN) {
            client.send(joinNotification);
        }
    });
});

server.listen(PORT, () => {
    console.log(`HTTP server listening on port ${PORT}`);
});

// Graceful shutdown handling (optional but good practice)
process.on('SIGTERM', () => {
    console.log('SIGTERM signal received: closing HTTP server');
    server.close(() => {
        console.log('HTTP server closed');
        wss.close(() => {
            console.log('WebSocket server closed');
            process.exit(0);
        });
    });
});