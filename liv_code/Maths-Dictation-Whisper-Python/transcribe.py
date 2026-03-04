import numpy as np
import sounddevice as sd
import re
from faster_whisper import WhisperModel

# ---------- SETTINGS ----------
MODEL_SIZE = "medium"
SAMPLE_RATE = 16000
CHUNK_DURATION = 4
# ------------------------------

print("Loading Whisper model...")
model = WhisperModel(
    MODEL_SIZE,
    compute_type="int8"
)

INITIAL_PROMPT = """
This is mathematics dictation.
Common words: alpha, beta, gamma, plus, minus, divide,
flat divide, integral, sigma, theta, lambda, equals.
"""

def replace_math_symbols(text):
    text = text.lower()

    replacements = [
        (r"\bflat\s+divide\b", "÷"),
        (r"\bdivide\b", "/"),
        (r"\bplus\b", "+"),
        (r"\bminus\b", "-"),
        (r"\btimes\b", r"\\times"),
        (r"\bequals\b", "="),
        (r"\balpha\b|\balfa\b", r"\\alpha"),
        (r"\bbeta\b", r"\\beta"),
        (r"\bgamma\b", r"\\gamma"),
        (r"\btheta\b", r"\\theta"),
        (r"\blambda\b", r"\\lambda"),
        (r"\bpi\b", r"\\pi"),
        (r"\bsquared\b", "^2"),
        (r"\bcubed?\b", "^3"),
        (r"\bintegral\b", r"\\int"),
        (r"\bsigma\b", r"\\sigma"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text.strip()


print("\nControlled Math Dictation Started.")
print('Say "period" to finalize a segment.')
print('Say "stop" to exit.\n')

buffer_text = ""

try:
    while True:
        print("Listening...")

        audio = sd.rec(
            int(CHUNK_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32"
        )
        sd.wait()
        audio = np.squeeze(audio)

        segments, _ = model.transcribe(
            audio,
            language="en",
            initial_prompt=INITIAL_PROMPT,
            beam_size=7
        )

        for segment in segments:
            buffer_text += " " + segment.text.lower()

        # ---- Check stop command ----
        if "stop" in buffer_text:
            print("\nStopping by voice command.")
            break

        # ---- Check period trigger ----
        if "period" in buffer_text:
            before_period = buffer_text.split("period")[0]

            processed = replace_math_symbols(before_period)

            if processed.strip():
                print("\nTranscribed:")
                print(processed)
                print("-" * 40)

            # Reset buffer after first period
            buffer_text = ""

except KeyboardInterrupt:
    print("\nStopped by user.")