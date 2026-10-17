
from flask import (request,
                   render_template,
                   Response
                   )


from app.common import paths
from . import lanmaps_bp
import requests

@lanmaps_bp.route("/martin/<path:subpath>")
def martin_proxy(subpath):
    """
    Proxy requests from the HTTPS Flask server to the local
    HTTP Martin server.

    Browser:
        https://192.168.0.25:8000/lan_maps/martin/india/...

    Martin:
        http://127.0.0.1:3000/india/...
    """

    url = f"{paths.MARTIN_URL}/{subpath}"
    print("Martin_URL/subpath",url)

    try:
        response = requests.get(
            url,
            params=request.args,
            timeout=30
        )

        excluded_headers = {
            "content-encoding",
            "transfer-encoding",
            "connection",
            "content-length"
        }

        headers = [
            (key, value)
            for key, value in response.headers.items()
            if key.lower() not in excluded_headers
        ]

        return Response(
            response.content,
            status=response.status_code,
            headers=headers
        )

    except requests.RequestException as e:

        print(f"Martin proxy error: {e}")

        return Response(
            "Martin server unavailable",
            status=502,
            mimetype="text/plain"
        )

@lanmaps_bp.route("/")
def maps():
    return render_template("maps.html")

