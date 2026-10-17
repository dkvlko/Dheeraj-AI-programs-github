
from flask import (request,
                   render_template,
                   Response,
                   jsonify
                   )


from app.common import paths
from . import lanmaps_bp
import requests
import re

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



VALHALLA_URL = "http://127.0.0.1:8002/route"


def parse_coordinates(value):
    """
    Parse a string in:
        latitude, longitude

    Returns:
        (latitude, longitude)

    Raises:
        ValueError
    """

    if not isinstance(value, str):
        raise ValueError(
            "Coordinates must be a string."
        )

    pattern = (
        r"^\s*"
        r"(-?\d+(?:\.\d+)?)"
        r"\s*,\s*"
        r"(-?\d+(?:\.\d+)?)"
        r"\s*$"
    )

    match = re.fullmatch(pattern, value)

    if not match:
        raise ValueError(
            "Location must be in "
            "'latitude, longitude' format."
        )

    latitude = float(match.group(1))
    longitude = float(match.group(2))

    if not -90 <= latitude <= 90:
        raise ValueError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "Longitude must be between -180 and 180."
        )

    return latitude, longitude


@lanmaps_bp.route("/route")
def route_page():
    """
    Separate route-display page.

    Source and destination are passed from
    maps_landing.html as query parameters.
    """

    return render_template(
        "maps_route.html",
        source=request.args.get("source", ""),
        destination=request.args.get("destination", "")
    )

def decode_polyline6(encoded):
    """
    Decode a Valhalla polyline6 string.

    Valhalla uses:
        - 6 decimal places
        - coordinate order inside the encoded string: latitude, longitude

    Returns GeoJSON coordinate order:
        [longitude, latitude]
    """

    if not encoded or not isinstance(encoded, str):
        return []

    coordinates = []

    index = 0
    lat = 0
    lon = 0

    factor = 1_000_000

    try:
        while index < len(encoded):

            # -------------------------
            # Decode latitude
            # -------------------------
            result = 0
            shift = 0

            while True:
                if index >= len(encoded):
                    raise ValueError("Unexpected end of polyline")

                byte = ord(encoded[index]) - 63
                index += 1

                result |= (byte & 0x1F) << shift
                shift += 5

                if byte < 0x20:
                    break

            if result & 1:
                delta_lat = ~(result >> 1)
            else:
                delta_lat = result >> 1

            lat += delta_lat

            # -------------------------
            # Decode longitude
            # -------------------------
            result = 0
            shift = 0

            while True:
                if index >= len(encoded):
                    raise ValueError("Unexpected end of polyline")

                byte = ord(encoded[index]) - 63
                index += 1

                result |= (byte & 0x1F) << shift
                shift += 5

                if byte < 0x20:
                    break

            if result & 1:
                delta_lon = ~(result >> 1)
            else:
                delta_lon = result >> 1

            lon += delta_lon

            # GeoJSON requires [longitude, latitude]
            coordinates.append([
                lon / factor,
                lat / factor
            ])

        return coordinates

    except (IndexError, ValueError, TypeError):
        return []

@lanmaps_bp.post("/api/route")
def route_api():
    """
    Receive Source and Destination coordinates,
    call local Valhalla and return route GeoJSON.
    """

    data = request.get_json(silent=True) or {}

    source_text = data.get("source", "")
    destination_text = data.get("destination", "")

    # ---------------------------------------------------------
    # Parse Source and Destination
    # ---------------------------------------------------------

    try:

        source_lat, source_lon = parse_coordinates(
            source_text
        )

        destination_lat, destination_lon = parse_coordinates(
            destination_text
        )

    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 400

    # ---------------------------------------------------------
    # Valhalla request
    #
    # Do NOT request GeoJSON shape here.
    # Valhalla's normal response contains an encoded
    # polyline6 in leg["shape"].
    # ---------------------------------------------------------

    valhalla_request = {

        "locations": [
            {
                "lat": source_lat,
                "lon": source_lon
            },
            {
                "lat": destination_lat,
                "lon": destination_lon
            }
        ],

        "costing": "auto",

        "units": "kilometers"

    }

    # ---------------------------------------------------------
    # Call Valhalla
    # ---------------------------------------------------------

    try:

        response = requests.post(
            VALHALLA_URL,
            json=valhalla_request,
            timeout=60
        )

        response.raise_for_status()

        valhalla_data = response.json()

    except requests.RequestException as e:

        print(
            "Valhalla request failed:",
            e
        )

        return jsonify({
            "error":
                "Valhalla routing service unavailable."
        }), 502

    except ValueError:

        return jsonify({
            "error":
                "Valhalla returned invalid JSON."
        }), 502

    # ---------------------------------------------------------
    # Get trip
    # ---------------------------------------------------------

    trip = valhalla_data.get("trip")

    if not trip:

        return jsonify({
            "error":
                "Valhalla did not return a trip.",
            "valhalla_response":
                valhalla_data
        }), 502

    # ---------------------------------------------------------
    # Get route legs
    # ---------------------------------------------------------

    legs = trip.get("legs", [])

    if not legs:

        return jsonify({
            "error":
                "Valhalla did not return route legs.",
            "valhalla_response":
                valhalla_data
        }), 502

    # ---------------------------------------------------------
    # Collect geometry from all legs
    # ---------------------------------------------------------

    all_coordinates = []

    for leg in legs:

        shape = leg.get("shape")

        if not shape:
            continue

        # -----------------------------------------------------
        # Case 1:
        # Valhalla returned GeoJSON geometry as a dictionary.
        # -----------------------------------------------------

        if isinstance(shape, dict):

            coordinates = shape.get(
                "coordinates",
                []
            )

        # -----------------------------------------------------
        # Case 2:
        # Valhalla returned its normal encoded polyline6.
        # -----------------------------------------------------

        elif isinstance(shape, str):

            coordinates = decode_polyline6(
                shape
            )

        # -----------------------------------------------------
        # Unknown shape type
        # -----------------------------------------------------

        else:

            coordinates = []

        # -----------------------------------------------------
        # Ignore empty geometry
        # -----------------------------------------------------

        if not coordinates:
            continue

        # -----------------------------------------------------
        # Append this leg.
        #
        # Avoid duplicating the point where two legs meet.
        # -----------------------------------------------------

        if all_coordinates:

            if all_coordinates[-1] == coordinates[0]:

                all_coordinates.extend(
                    coordinates[1:]
                )

            else:

                all_coordinates.extend(
                    coordinates
                )

        else:

            all_coordinates.extend(
                coordinates
            )

    # ---------------------------------------------------------
    # Validate final geometry
    # ---------------------------------------------------------

    if len(all_coordinates) < 2:

        print(
            "Valhalla returned no usable route geometry."
        )

        return jsonify({
            "error":
                "Valhalla returned no usable route geometry.",

            "legs":
                len(legs),

            "valhalla_response":
                valhalla_data
        }), 502

    # ---------------------------------------------------------
    # Route summary
    # ---------------------------------------------------------

    summary = trip.get(
        "summary",
        {}
    )

    # ---------------------------------------------------------
    # GeoJSON Feature
    # ---------------------------------------------------------

    route_geojson = {

        "type": "Feature",

        "properties": {},

        "geometry": {

            "type": "LineString",

            "coordinates":
                all_coordinates

        }

    }

    # ---------------------------------------------------------
    # Return route to browser
    # ---------------------------------------------------------

    return jsonify({

        "route":
            route_geojson,

        "summary": {

            "length_km":
                summary.get("length"),

            "time_minutes":
                (
                    summary.get("time", 0) / 60
                    if summary.get("time") is not None
                    else None
                )

        }

    })

@lanmaps_bp.route("/")
def maps():
    return render_template("maps_landing.html")


@lanmaps_bp.route("/cmaps")
def cmaps():
    return render_template("maps.html")
