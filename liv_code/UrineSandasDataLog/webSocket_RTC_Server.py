import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from pathlib import Path

app = FastAPI()
PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web"))
pcs = set()

@app.post("/offer")
async def offer(request: Request):
    data = await request.json()
    
    # Logic to handle client dimensions
    client_w = data.get("width", 1024)
    client_h = data.get("height", 768)
    
    # "Safe" Resolution Logic: Must be divisible by 16 for iPad A7 chip
    # We also cap it at 1024 to ensure the iPad Mini 2 CPU isn't overwhelmed
    safe_w = min((client_w // 16) * 16, 1024)
    safe_h = min((client_h // 16) * 16, 768)
    
    print(f"--- [SERVER] Client detected. Adapting to {safe_w}x{safe_h} ---")

    pc = RTCPeerConnection()
    pcs.add(pc)

    options = {
        "framerate": "15",
        "video_size": f"{safe_w}x{safe_h}", 
        "pixel_format": "yuv420p",
    }
    
    try:
        # Use display :1.0 as established in your UDP success
        player = MediaPlayer(":1.0", format="x11grab", options=options)
        
        if player.video:
            pc.addTrack(player.video)
            print(f"--- [SERVER] Adaptive Video track added ({safe_w}x{safe_h}) ---")
        
        # Audio setup remains consistent with your previous success
        audio_player = MediaPlayer("default", format="pulse", options={"sample_rate": "44100"})
        if audio_player.audio:
            pc.addTrack(audio_player.audio)
            
    except Exception as e:
        print(f"--- [SERVER] MEDIA ERROR: {e} ---")

    await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type=data["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.on_event("shutdown")
async def on_shutdown():
    close_coros = [pc.close() for pc in pcs]
    await asyncio.gather(*close_coros)
import av
from aiortc import VideoStreamTrack
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()
PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web"))
pcs = set()

# Custom Track to fix 1366x768 Stride/Alignment Issues
class ScreenCaptureTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        # Capture the FULL screen
        self.container = av.open(":1.0", format="x11grab", options={
            "video_size": "1366x768",
            "framerate": "15"
        })
        self.stream = self.container.streams.video[0]

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # Grab the frame from X11
        for frame in self.container.decode(self.stream):
            # SCALE and REFORMAT to fix Pink Lines/Green Screen
            # 1024x576 is 16:9 and perfectly divisible by 16
            new_frame = frame.to_image().resize((1024, 576))
            
            # Convert back to VideoFrame for WebRTC
            final_frame = av.VideoFrame.from_image(new_frame)
            final_frame.pts = pts
            final_frame.time_base = time_base
            return final_frame

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ["failed", "closed"]:
            await pc.close()
            pcs.discard(pc)

    # Add our custom High-Compatibility Track
    pc.addTrack(ScreenCaptureTrack())

    # Audio remains as established in your previous successful build
    try:
        audio_player = MediaPlayer("default", format="pulse", options={"sample_rate": "44100"})
        if audio_player.audio:
            pc.addTrack(audio_player.audio)
    except Exception as e:
        print(f"Audio error: {e}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.on_event("shutdown")
async def on_shutdown():
    close_coros = [pc.close() for pc in pcs]
    await asyncio.gather(*close_coros)
