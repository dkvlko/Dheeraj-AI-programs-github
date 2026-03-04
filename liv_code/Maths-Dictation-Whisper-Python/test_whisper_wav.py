import whisper
import time

audio_file = "Math-test.wav"

# start timer
start = time.time()

# choose model explicitly
model_name = "small"   # options: tiny, base, small, medium, large

# force CPU usage
model = whisper.load_model(model_name, device="cpu")

load_time = time.time()

# transcribe
result = model.transcribe(
    audio_file,
    language="en",
    fp16=False
)

end = time.time()

print("\nTranscription:\n")
print(result["text"])

print("\nTiming:")
print("Model:", model_name)
print("Model load time:", round(load_time - start,2),"sec")
print("Transcription time:", round(end - load_time,2),"sec")
print("Total time:", round(end - start,2),"sec")