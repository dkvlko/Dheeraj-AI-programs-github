from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
import subprocess
import threading
import time

import requests
from flask import (
    Response,
    abort,
    render_template_string,
    request,
    stream_with_context,
    url_for,
)

from . import ziintrdata_bp


# Configuration
KIWIX_BIN = (
    Path.home()
    / "kiwix-tools_linux-x86_64-3.8.2"
    / "kiwix-serve"
)

ZIM_DIRECTORY = Path("/media/My Passport/Zim-Apps")

KIWIX_BASE_URL = "http://127.0.0.1:8090"
KIWIX_PREFIX = "/ziintrdata"
KIWIX_PORT = 8090

KIWIX_LOG = Path("/tmp/kiwix-on-demand.log")

# One process at a time; intended for a single-user Flask server.
kiwix_process = None
kiwix_lock = threading.RLock()

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}


CATALOG_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Kiwix Archive Catalogue</title>
    <style>
        body {
            max-width: 1000px;
            margin: 30px auto;
            padding: 0 18px;
            font-family: system-ui, sans-serif;
        }
        input {
            box-sizing: border-box;
            width: 100%;
            padding: 12px;
            margin: 18px 0;
            font-size: 16px;
        }
        .archive {
            padding: 12px 0;
            border-bottom: 1px solid #ddd;
            overflow-wrap: anywhere;
        }
        a { text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Kiwix Archive Catalogue</h1>
    <p>{{ archives|length }} archives available</p>

    <input id="search" type="search"
           placeholder="Search archives...">

    <div id="archives">
        {% for archive in archives %}
        <div class="archive" data-name="{{ archive.name|lower }}">
            <a href="{{ url_for('.open_zim', zim_name=archive.name) }}">
                {{ archive.name }}
            </a>
        </div>
        {% endfor %}
    </div>

    <script>
        document.getElementById("search").addEventListener(
            "input", function () {
                const term = this.value.toLowerCase();
                document.querySelectorAll(".archive").forEach(item => {
                    item.hidden = !item.dataset.name.includes(term);
                });
            }
        );
    </script>
</body>
</html>
"""


VIEWER_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ archive_name }} - Kiwix</title>
    <style>
        * { box-sizing: border-box; }
        html, body {
            width: 100%;
            height: 100%;
            margin: 0;
            font-family: system-ui, sans-serif;
        }
        #viewer {
            display: block;
            width: 100%;
            height: calc(100vh - 58px);
            border: 0;
        }
        #bottom-bar {
            height: 58px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 8px 14px;
            background: #202124;
            color: white;
        }
        #quit {
            padding: 9px 24px;
            border: 0;
            border-radius: 5px;
            background: #c62828;
            color: white;
            font-size: 16px;
            cursor: pointer;
        }
        #quit:disabled { opacity: 0.6; }
        #status {
            font-size: 13px;
            overflow-wrap: anywhere;
        }
    </style>
</head>
<body>
    <iframe id="viewer"
            src="{{ iframe_url }}"
            title="{{ archive_name }}"></iframe>

    <div id="bottom-bar">
        <span id="status">{{ archive_name }}</span>
        <button id="quit" type="button" onclick="quitArchive()">
            Quit
        </button>
    </div>

    <script>
        async function quitArchive() {
            const button = document.getElementById("quit");
            const status = document.getElementById("status");

            button.disabled = true;
            status.textContent = "Stopping Kiwix...";

            try {
                const response = await fetch(
                    "{{ url_for('.quit_kiwix') }}",
                    { method: "POST" }
                );

                if (!response.ok) {
                    throw new Error("Shutdown request failed");
                }

                window.location.replace(
                    "{{ url_for('.ziintrdata_catalogue') }}"
                );
            } catch (error) {
                status.textContent =
                    "Could not stop Kiwix. Please try again.";
                button.disabled = false;
            }
        }
    </script>
</body>
</html>
"""


def _stop_kiwix_locked():
    """Stop the process owned by this Python application."""
    global kiwix_process

    process = kiwix_process
    kiwix_process = None

    if process is None or process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _start_kiwix_locked(zim_path):
    """Start Kiwix with exactly one selected ZIM file."""
    global kiwix_process

    _stop_kiwix_locked()

    if not ZIM_DIRECTORY.is_dir():
        raise RuntimeError("ZIM directory is not available.")

    if not KIWIX_BIN.is_file():
        raise RuntimeError(f"Kiwix executable not found: {KIWIX_BIN}")

    if not zim_path.is_file() or zim_path.suffix.lower() != ".zim":
        raise RuntimeError("Selected ZIM file is unavailable.")

    # The log file helps diagnose startup failures.
    with KIWIX_LOG.open("a", encoding="utf-8") as log:
        kiwix_process = subprocess.Popen(
            [
                str(KIWIX_BIN),
                "--address=127.0.0.1",
                f"--port={KIWIX_PORT}",
                f"--urlRootLocation={KIWIX_PREFIX}",
                str(zim_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Wait for the selected archive URL to respond.
    archive_url = (
        f"{KIWIX_BASE_URL}{KIWIX_PREFIX}/"
        f"{quote(zim_path.stem, safe='')}"
    )
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if kiwix_process.poll() is not None:
            kiwix_process = None
            raise RuntimeError(
                f"Kiwix exited during startup. See {KIWIX_LOG}"
            )

        try:
            response = requests.get(
                archive_url,
                timeout=(1, 2),
                allow_redirects=False,
            )
            response.close()

            if response.status_code < 500:
                return
        except requests.RequestException:
            pass

        time.sleep(0.25)

    _stop_kiwix_locked()
    raise RuntimeError(
        f"Kiwix did not become ready. See {KIWIX_LOG}"
    )


@ziintrdata_bp.route("/", methods=["GET"])
def ziintrdata_catalogue():
    if not ZIM_DIRECTORY.is_dir():
        return "ZIM directory is unavailable.", 503

    archives = sorted(
        (
            {"name": file.name}
            for file in ZIM_DIRECTORY.glob("*.zim")
            if file.is_file()
        ),
        key=lambda item: item["name"].lower(),
    )

    return render_template_string(
        CATALOG_TEMPLATE,
        archives=archives,
    )


@ziintrdata_bp.route("/open/<path:zim_name>", methods=["GET"])
def open_zim(zim_name):
    # Only allow a filename directly inside the configured directory.
    if Path(zim_name).name != zim_name or not zim_name.lower().endswith(".zim"):
        abort(404)

    zim_path = (ZIM_DIRECTORY / zim_name).resolve()

    if zim_path.parent != ZIM_DIRECTORY.resolve():
        abort(404)

    if not zim_path.is_file():
        abort(404)

    with kiwix_lock:
        try:
            _start_kiwix_locked(zim_path)
        except (OSError, RuntimeError) as exc:
            return (
                f"Could not start Kiwix: {exc}",
                503,
            )

    iframe_url = (
        f"{KIWIX_PREFIX}/{quote(zim_path.stem, safe='')}"
    )

    return render_template_string(
        VIEWER_TEMPLATE,
        archive_name=zim_path.name,
        iframe_url=iframe_url,
    )


@ziintrdata_bp.route("/quit", methods=["POST"])
def quit_kiwix():
    with kiwix_lock:
        _stop_kiwix_locked()

    return {"ok": True}, 200


@ziintrdata_bp.route(
    "/<path:path>",
    methods=["GET", "HEAD"],
)
def proxy_kiwix(path):
    # This route forwards archive pages, assets and other Kiwix paths.
    with kiwix_lock:
        process = kiwix_process

        if process is None or process.poll() is not None:
            return "No ZIM archive is currently open.", 503

    upstream_url = f"{KIWIX_BASE_URL}{KIWIX_PREFIX}/{path}"

    try:
        upstream = requests.request(
            method=request.method,
            url=upstream_url,
            params=request.args,
            headers={
                key: value
                for key, value in request.headers.items()
                if key.lower() not in {
                    "host",
                    "connection",
                    "content-length",
                }
            },
            stream=True,
            allow_redirects=False,
            timeout=(5, 60),
        )
    except requests.RequestException:
        return "Kiwix backend is unavailable.", 502

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    # Rewrite absolute redirects that point to the internal backend.
    for key in list(response_headers):
        if key.lower() == "location":
            location = response_headers[key]
            parsed = urlsplit(location)

            if parsed.netloc == urlsplit(KIWIX_BASE_URL).netloc:
                response_headers[key] = urlunsplit((
                    "",
                    "",
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                ))

    def generate():
        try:
            for chunk in upstream.iter_content(
                chunk_size=64 * 1024
            ):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return Response(
        stream_with_context(generate()),
        status=upstream.status_code,
        headers=response_headers,
    )
