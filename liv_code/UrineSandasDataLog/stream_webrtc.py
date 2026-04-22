# server.py
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

app = FastAPI()
pcs = set()

@app.get("/")
async def index():
    with open("web/index.html") as f:
        return HTMLResponse(f.read())

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()

    pc = RTCPeerConnection()
    pcs.add(pc)

    # 🔥 THIS pulls your RTP stream
    #player = MediaPlayer("rtp://127.0.0.1:5004", format="rtp")
    #player = MediaPlayer("stream.sdp")
    player = MediaPlayer("/home/dkvlko/stream.sdp")

    if player.video:
        pc.addTrack(player.video)
    if player.audio:
        pc.addTrack(player.audio)

    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    )

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }
