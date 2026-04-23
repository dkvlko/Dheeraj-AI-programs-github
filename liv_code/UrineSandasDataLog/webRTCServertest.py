import json
import pyautogui
import asyncio
from fastapi import FastAPI, WebSocket,WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# -------- WebSocket --------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("WebSocket Connected")

    try :
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            action = msg.get("action")

            if action == "move":

                x2, y2 = pyautogui.position()
                #print(f"[BEFORE] x={x2}, y={y2}")
                
                raw_dx = msg.get("dx", 0)
                raw_dy = msg.get("dy", 0)
                #print(f"[RAW] dx={raw_dx}, dy={raw_dy}")

                # --- tuning ---
                dx = int(raw_dx * 1)
                dy = int(raw_dy * 1)

                # ignore tiny jitter
                #if abs(dx) < 2:
                #    dx = 0
                #if abs(dy) < 2:
                #    dy = 0

                #print(f"[PROC] dx={dx}, dy={dy}")
                # --- get current position ---
                x, y = pyautogui.position()
                screen_w, screen_h = pyautogui.size()

                # --- clamp to avoid corners ---
                new_x = max(10, min(screen_w - 10, x + dx))
                new_y = max(10, min(screen_h - 10, y + dy))

                pyautogui.moveTo(new_x, new_y)

                x2, y2 = pyautogui.position()
                #print(f"[AFTER] x={x2}, y={y2}")
            elif action == "left_click":
                pyautogui.click()

            elif action == "right_click":
                pyautogui.click(button="right")
    except WebSocketDisconnect:
        print("WebSocket disconnected by client")

    except asyncio.CancelledError:
        print("WebSocket task cancelled (server shutting down)")

    finally:
        print("Cleaning up WebSocket")

        try:
            await ws.close()
        except RuntimeError:
            # already closed → ignore
            pass

        print("Cleanup done")
# -------- UI --------
@app.get("/")
async def index():
    with open("web/control.html") as f:
        return HTMLResponse(f.read())


app.mount("/static", StaticFiles(directory="web/static"), name="static")
