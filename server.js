const http = require('http');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');

const PORT = process.env.PORT || 3000;

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
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
    }
});

const wss = new WebSocket.Server({ server });

const clients = new Set();

console.log(`WebSocket server is starting on port ${PORT}`);

wss.on('connection', (ws) => {
    console.log('Client connected');
    clients.add(ws);
    
    ws.on('message', (message) => {
        console.log('Received message:', message.toString());
        try {
            clients.forEach(client => {
                if (client !== ws && client.readyState === WebSocket.OPEN) {
                    client.send(message.toString());
                }
            });
        } catch (e) {
            console.error('Failed to process message or broadcast:', e);
            ws.send(JSON.stringify({ type: 'error', payload: 'Invalid message format received.' }));
        }
    });
    
    ws.on('close', () => {
        console.log('Client disconnected');
        clients.delete(ws);
        const notification = JSON.stringify({ type: 'notification', payload: 'A user has left the chat.' });
        clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(notification);
            }
        });
    });
    
    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        clients.delete(ws);
    });
    
    ws.send(JSON.stringify({ type: 'notification', payload: 'Welcome to the chat!' }));
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