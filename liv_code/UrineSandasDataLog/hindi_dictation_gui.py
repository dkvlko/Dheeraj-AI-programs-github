import threading
import queue
import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from faster_whisper import WhisperModel

# -------------------------
# CONFIG
# -------------------------
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1         # mono
MODEL_SIZE = "medium"  # or "medium" if your machine can handle it

# -------------------------
# GLOBAL STATE
# -------------------------
audio_queue = queue.Queue()
recording = False
stream = None
model = None

# -------------------------
# AUDIO CALLBACK
# -------------------------
def audio_callback(indata, frames, time, status):
    if status:
        print("Audio status:", status)
    if recording:
        # Flatten to mono, copy to queue
        audio_queue.put(indata.copy())

# -------------------------
# TRANSCRIPTION LOGIC
# -------------------------
def transcribe_audio(app):
    """
    Pull all audio from the queue, run Whisper (Hindi only),
    and display the text in the GUI.
    """
    # Gather all audio frames from queue
    frames = []
    while not audio_queue.empty():
        frames.append(audio_queue.get())

    if not frames:
        app.append_text("\n[No audio captured]\n")
        return

    audio_data = np.concatenate(frames, axis=0)

    # Convert to mono if necessary
    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    # WhisperModel expects float32
    audio_data = audio_data.astype(np.float32)

    app.append_text("\n[Transcribing...]\n")

    def worker():
        global model
        try:
            if model is None:
                # Lazy-load model (so the app window appears quickly)
                app.append_text("[Loading Whisper model... this may take a while]\n")
                # For CPU: device="cpu", compute_type="int8"
                # For GPU: device="cuda", compute_type="float16"
                model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

            # Force Hindi, Devanagari output
            segments, info = model.transcribe(
                audio_data,
                language="hi",       # force Hindi
                task="transcribe",   # not "translate"
                beam_size=5
            )

            text = "".join(segment.text for segment in segments).strip()
            if not text:
                text = "[No text recognized]"

            def update_ui():
                app.append_text("\n--- Transcription (Hindi) ---\n")
                app.append_text(text + "\n")

            app.root.after(0, update_ui)

        except Exception as e:
            def update_ui_err():
                app.append_text(f"\n[Error during transcription: {e}]\n")
            app.root.after(0, update_ui_err)

    threading.Thread(target=worker, daemon=True).start()

# -------------------------
# APP GUI CLASS
# -------------------------
class HindiDictationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hindi Dictation (Whisper / faster-whisper)")
        self.root.geometry("700x400")

        # Buttons frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="Start Listening", command=self.start_listening, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(btn_frame, text="Stop + Transcribe", command=self.stop_listening, width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Info label
        self.label = tk.Label(root, text="Press 'Start Listening' and speak in Hindi. Then press 'Stop + Transcribe'.")
        self.label.pack(pady=5)

        # Text area
        self.text_area = ScrolledText(root, wrap=tk.WORD, font=("Nirmala UI", 14))  # font good for Devanagari
        self.text_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Initial help
        self.append_text("Ready.\nMake sure your microphone is allowed in Windows Settings > Privacy > Microphone.\n")

    def append_text(self, content):
        self.text_area.insert(tk.END, content)
        self.text_area.see(tk.END)

    def start_listening(self):
        global recording, stream
        if recording:
            return

        # Clear any old audio from queue
        while not audio_queue.empty():
            audio_queue.get()

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=audio_callback
            )
            stream.start()
            recording = True
            self.append_text("\n[Listening... speak in Hindi]\n")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.append_text(f"\n[Error accessing microphone: {e}]\n")
            self.append_text("Check Windows microphone permissions.\n")

    def stop_listening(self):
        global recording, stream
        if not recording:
            return

        recording = False
        try:
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
        except Exception as e:
            self.append_text(f"\n[Error stopping stream: {e}]\n")

        self.append_text("\n[Stopped listening]\n")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        # Now transcribe whatever we captured
        transcribe_audio(self)


# -------------------------
# MAIN
# -------------------------
def main():
    root = tk.Tk()
    app = HindiDictationApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
