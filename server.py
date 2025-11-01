from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import json
from pathlib import Path
from typing import Dict

app = FastAPI()

# Get the directory where this script is located
BASE_DIR = Path(__file__).parent

# Mount static files directory for images and other assets
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")

# Store active WebSocket connections
# Key: peer_id, Value: WebSocket
active_connections: Dict[str, WebSocket] = {}

# Store peer information
# Key: peer_id, Value: {"ws": WebSocket, "connected_to": peer_id or None}
peer_registry: Dict[str, Dict] = {}

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the index.html file"""
    html_path = BASE_DIR / "index-local.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    else:
        return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

@app.websocket("/ws/{peer_id}")
async def websocket_endpoint(websocket: WebSocket, peer_id: str):
    """WebSocket endpoint for WebRTC signaling"""
    await websocket.accept()
    
    # Register peer
    active_connections[peer_id] = websocket
    peer_registry[peer_id] = {
        "ws": websocket,
        "connected_to": None
    }
    
    print(f"Peer {peer_id} connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            target_peer = message.get("target")
            
            if message_type == "register":
                # Peer registration confirmation
                await websocket.send_text(json.dumps({
                    "type": "registered",
                    "peer_id": peer_id
                }))
                print(f"Peer {peer_id} registered")
                
            elif message_type == "connect":
                # Connection request
                if target_peer in active_connections:
                    target_ws = active_connections[target_peer]
                    await target_ws.send_text(json.dumps({
                        "type": "connection-request",
                        "from": peer_id
                    }))
                    print(f"Forwarded connection request from {peer_id} to {target_peer}")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "peer-unavailable",
                        "target": target_peer
                    }))
                    print(f"Peer {target_peer} not found")
                    
            elif message_type == "offer":
                # WebRTC offer
                if target_peer in active_connections:
                    target_ws = active_connections[target_peer]
                    await target_ws.send_text(json.dumps({
                        "type": "offer",
                        "from": peer_id,
                        "offer": message.get("offer")
                    }))
                    print(f"Forwarded offer from {peer_id} to {target_peer}")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "peer-unavailable",
                        "target": target_peer
                    }))
                    
            elif message_type == "answer":
                # WebRTC answer
                if target_peer in active_connections:
                    target_ws = active_connections[target_peer]
                    await target_ws.send_text(json.dumps({
                        "type": "answer",
                        "from": peer_id,
                        "answer": message.get("answer")
                    }))
                    print(f"Forwarded answer from {peer_id} to {target_peer}")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "peer-unavailable",
                        "target": target_peer
                    }))
                    
            elif message_type == "ice-candidate":
                # ICE candidate
                if target_peer in active_connections:
                    target_ws = active_connections[target_peer]
                    await target_ws.send_text(json.dumps({
                        "type": "ice-candidate",
                        "from": peer_id,
                        "candidate": message.get("candidate")
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "peer-unavailable",
                        "target": target_peer
                    }))
                    
            elif message_type == "disconnect":
                # Peer disconnection
                if target_peer in active_connections:
                    target_ws = active_connections[target_peer]
                    await target_ws.send_text(json.dumps({
                        "type": "peer-disconnected",
                        "from": peer_id
                    }))
                    
    except WebSocketDisconnect:
        print(f"Peer {peer_id} disconnected")
    except Exception as e:
        print(f"Error handling WebSocket for {peer_id}: {e}")
    finally:
        # Cleanup
        if peer_id in active_connections:
            del active_connections[peer_id]
        if peer_id in peer_registry:
            del peer_registry[peer_id]
        print(f"Cleaned up peer {peer_id}")

if __name__ == "__main__":
    import uvicorn
    
    # SSL certificate paths
    ssl_keyfile = BASE_DIR / "cert.key"
    ssl_certfile = BASE_DIR / "cert.crt"
    
    # Check if certificates exist
    if not ssl_keyfile.exists() or not ssl_certfile.exists():
        print("SSL certificates not found!")
        print("Please run: python generate_cert.py")
        print("Or provide your own certificates:")
        print(f"  - {ssl_keyfile}")
        print(f"  - {ssl_certfile}")
        exit(1)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=10500,
        ssl_keyfile=str(ssl_keyfile),
        ssl_certfile=str(ssl_certfile)
    )

