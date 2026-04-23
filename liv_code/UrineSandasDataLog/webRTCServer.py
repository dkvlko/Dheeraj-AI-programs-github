import asyncio
import av
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
from pathlib import Path

app = FastAPI()
PROJECT_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "web"))
pcs = set()


# Custom Track to fix resolution / alignment issues
class ScreenCaptureTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.container = av.open(":1.0", format="x11grab", options={
            "video_size": "1366x768",
            "framerate": "15"
        })
        self.stream = self.container.streams.video[0]

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        for frame in self.container.decode(self.stream):
            new_frame = frame.to_image().resize((1024, 576))
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

    # Video track
    pc.addTrack(ScreenCaptureTrack())

    # Audio track
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
    await asyncio.gather(*[pc.close() for pc in pcs])
