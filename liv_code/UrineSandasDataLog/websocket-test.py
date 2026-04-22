import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# Store connected clients
clients = []

# ----------------------
# HTTP route (test page)
# ----------------------
@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test</title>
    </head>
    <body>
        <h2>Async WebSocket Test</h2>
        <button onclick="sendPing()">Send Ping</button>

        <script>
            const ws = new WebSocket("ws://" + location.host + "/ws");

            ws.onopen = () => {
                console.log("Connected to server");
            };

            ws.onmessage = (event) => {
                console.log("Server says:", event.data);
            };

            function sendPing() {
                ws.send(JSON.stringify({type: "ping", msg: "Hello from browser"}));
            }
        </script>
    </body>
    </html>
    """)

# ----------------------
# WebSocket endpoint
# ----------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)

    print("Client connected")

    try:
        while True:
            data = await websocket.receive_text()
            print("Received:", data)

            # Respond back
            await websocket.send_text("pong from server")

    except WebSocketDisconnect:
        print("Client disconnected")
        clients.remove(websocket)
