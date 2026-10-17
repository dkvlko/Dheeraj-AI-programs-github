from flask import Flask, request, jsonify, render_template_string
import pyautogui
import pyperclip

app = Flask(__name__)

# Optional: slow down typing a tiny bit to avoid issues
pyautogui.PAUSE = 1  # seconds between actions


HTML_PAGE = r"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>iPhone → PC Keyboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {
            font-family: sans-serif;
            margin: 0;
            padding: 10px;
            background: #f5f5f5;
        }
        h1 {
            font-size: 1.2rem;
        }
        #info {
            font-size: 0.9rem;
            color: #444;
            margin-bottom: 8px;
        }
        textarea {
            width: 100%;
            height: 60vh;          /* roughly 9–10 lines on a phone */
            font-size: 1rem;
            box-sizing: border-box;
        }
        #status {
            margin-top: 8px;
            font-size: 0.8rem;
            color: #555;
        }
    </style>
</head>
<body>
    <h1>Remote Keyboard for PC</h1>
    <div id="info">
        Type here on your iPhone. Keystrokes are sent to your Windows PC’s active window.
    </div>

    <textarea id="inputArea" spellcheck="false" autofocus></textarea>

    <div id="status">Ready.</div>

    <script>
        const textarea = document.getElementById('inputArea');
        const statusEl = document.getElementById('status');

        textarea.focus();

        // Helper: send a keystroke to the server
        async function sendKey(key, codePoint) {
            try {
                const response = await fetch('/keystroke', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        key: key,
                        codePoint: codePoint
                    })
                });
                if (!response.ok) {
                    statusEl.textContent = "Error sending key: " + response.status;
                } else {
                    const data = await response.json();
                    statusEl.textContent = "Sent: " + key + " (UTF: " + (codePoint ?? "n/a") + ")";
                }
            } catch (err) {
                statusEl.textContent = "Network error sending key.";
            }
        }

        textarea.addEventListener('keydown', function (e) {
            // e.key is the logical key, e.g. "a", "A", "Enter", "Backspace"
            let key = e.key;

            // Compute UTF code point only for single-character keys
            let codePoint = null;
            if (key.length === 1) {
                codePoint = key.codePointAt(0);
            }

            // Send every key press to the server
            sendKey(key, codePoint);

            // Let the browser handle the key normally so text appears in the textarea.
            // We do NOT call e.preventDefault() here.
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/keystroke", methods=["POST"])
def keystroke():
    data = request.get_json(force=True)
    key = data.get("key", "")
    code_point = data.get("codePoint", None)

    # Handle special keys normally
    if key == "Enter":
        pyautogui.press("enter")
        return jsonify({"status": "ok"})

    if key == "Backspace":
        pyautogui.press("backspace")
        return jsonify({"status": "ok"})

    if key in ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]:
        pyautogui.press(key.replace("Arrow", "").lower())
        return jsonify({"status": "ok"})

    # ---------- IMPORTANT ----------
    # For Unicode characters (like Hindi), use clipboard-paste
    if len(key) == 1:
        pyperclip.copy(key)   # put char into clipboard
        pyautogui.hotkey("ctrl", "v")
        return jsonify({"status": "ok"})

    return jsonify({"status": "ignored"})


if __name__ == "__main__":
    # host='0.0.0.0' makes it reachable from other devices on the LAN
    app.run(host="0.0.0.0", port=5000, debug=False)
