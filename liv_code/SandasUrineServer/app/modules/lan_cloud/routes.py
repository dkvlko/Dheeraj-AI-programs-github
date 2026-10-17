
from flask import (request, 
                   render_template,
                   send_file,
                   Response,
                   abort,
                   jsonify,
                   current_app,
)

from pathlib import Path
import random
from app.common import paths
from . import  state 
from . import lancloud_bp
import shutil
import tempfile
import zipfile
from flask import after_this_request

import os

from .traversal import (
    get_current_directory,
    save_current_directory,
    resolve_path,
)

@lancloud_bp.route("/")
def LANcloud():
    return render_template("/lancloud/showdirfiles.html")

def build_current_listing():
    relative_path = get_current_directory()
    directory = resolve_path(relative_path)

    state.BuildLANcloudDirectoryJSON(directory)

    # Preserve your existing entries and entry structure.
    listing = dict(state.LANcloud_JSON)
    listing["current_directory"] = relative_path

    return listing

@lancloud_bp.route("/list")
def LANcloudList():
    try:
        return jsonify(build_current_listing())

    except (PermissionError, ValueError):
        return jsonify({"error": "Access denied"}), 403



@lancloud_bp.route("/change-directory", methods=["POST"])
def LANcloudChangeDirectory():
    data = request.get_json(silent=True) or {}
    relative_path = data.get("path", "")

    try:
        # This writes the new traversal record to disk.
        save_current_directory(relative_path)

        # Build a listing for the newly selected directory.
        return jsonify(build_current_listing())

    except PermissionError:
        return jsonify({"error": "Access denied"}), 403

    except (NotADirectoryError, FileNotFoundError, ValueError):
        return jsonify({"error": "Directory not found"}), 404


@lancloud_bp.route("/file-operation-download")
def file_operation_download():

    name = request.args.get("name")

    if not name:
        return "No file selected.", 400

    try:
        current_directory = get_current_directory()

        relative_path = (
            f"{current_directory}/{name}"
            if current_directory
            else name
        )

        path = resolve_path(relative_path)

    except (PermissionError, ValueError):
        return "Access denied.", 403

    print("Name of file:", name)
    print("Current directory:", current_directory)
    print("Path of file:", path)

    if not path.is_file() and not path.is_dir():
        return "Selected file or directory not found.", 404


    ###########################################################
    # Create Temporary ZIP
    ###########################################################

    temp_zip = tempfile.NamedTemporaryFile(

        suffix=".zip",

        delete=False

    )

    temp_zip.close()

    zip_filename = temp_zip.name


    ###########################################################
    # Build ZIP
    ###########################################################

    with zipfile.ZipFile(

            zip_filename,

            "w",

            compression=zipfile.ZIP_DEFLATED,

            compresslevel=9

    ) as archive:


        #######################################################
        # Selected item is a FILE
        #######################################################

        if path.is_file():

            archive.write(

                path,

                arcname=path.name

            )


        #######################################################
        # Selected item is a DIRECTORY
        #######################################################

        else:

            for root, dirs, files in os.walk(path):

                for filename in files:

                    full_path = Path(root) / filename

                    archive_name = full_path.relative_to(path.parent)

                    archive.write(

                        full_path,

                        arcname=archive_name

                    )


    ###########################################################
    # Delete ZIP after download completes
    ###########################################################

    @after_this_request
    def cleanup(response):

        try:

            os.remove(zip_filename)

        except Exception as e:

            print(e)

        return response


    ###########################################################
    # Download ZIP
    ###########################################################

    return send_file(

        zip_filename,

        as_attachment=True,

        download_name=path.name + ".zip",

        mimetype="application/zip"

    )



@lancloud_bp.route(
    "/file-operation-upload",
    methods=["POST"]
)
def file_operation_upload():
    try:

        uploaded_chunk = request.files["file"]

        filename = request.form["filename"]

        current_directory = request.form[
            "current_directory"
        ]

        chunk_number = int(
            request.form["chunk_number"]
        )

        total_chunks = int(
            request.form["total_chunks"]
        )


        ####################################################
        # Destination Directory
        ####################################################

# If we are in the root shared folder, don't append it again.
        current_directory = get_current_directory()

        destination_directory = resolve_path(
            current_directory
        )

        if not destination_directory.is_dir():
            return jsonify({
                "status": "error",
                "message": "Destination directory not found."
            }), 404

        destination_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        ####################################################
        # Temporary File
        ####################################################

        temporary_file = (

            paths.UPLOAD_TEMP_FOLDER /

            (filename + ".part")

        )


        ####################################################
        # First Chunk
        ####################################################

        if chunk_number == 0:

            if temporary_file.exists():

                temporary_file.unlink()


        ####################################################
        # Append Chunk
        ####################################################

        with open(

                temporary_file,

                "ab"

        ) as output_file:

            shutil.copyfileobj(

                uploaded_chunk.stream,

                output_file

            )


        ####################################################
        # Last Chunk
        ####################################################

        if chunk_number == total_chunks - 1:

            #if not filename.lower().endswith(".zip"):
             #   final_filename = filename + ".zip"
            #else:
            #    final_filename = filename

            final_file = (

                destination_directory /

                filename

            )

            temporary_file.replace(

                final_file

            )

            print(

                f"Uploaded : {final_file}"

            )

            state.BuildLANcloudDirectoryJSON(
                resolve_path(get_current_directory())
            )

        ####################################################
        # Success
        ####################################################

        return jsonify(

            {

                "status": "ok"

            }

        )

    except Exception as exception:

        print(exception)

        return jsonify(

            {

                "status": "error",

                "message": str(exception)

            }

        ), 500





@lancloud_bp.route("/file-operation", methods=["POST"])
def file_operation():
    data = request.get_json(silent=True) or {}

    if data.get("operation") != "delete":
        return jsonify({
            "status": "error",
            "message": "Unsupported operation."
        }), 400

    selected = data.get("selected", [])

    if not isinstance(selected, list):
        return jsonify({
            "status": "error",
            "message": "Invalid selection."
        }), 400

    current_directory = get_current_directory()
    deleted = []
    failed = []

    for name in selected:
        if not isinstance(name, str) or name in ("", ".", ".."):
            failed.append(str(name))
            continue

        try:
            relative_path = (
                f"{current_directory}/{name}"
                if current_directory
                else name
            )

            path = resolve_path(relative_path)

            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
            else:
                failed.append(name)
                continue

            deleted.append(name)

        except Exception as exc:
            failed.append(f"{name} ({exc})")

    return jsonify({
        "status": "ok",
        "deleted": deleted,
        "failed": failed,
        "message": f"Deleted {len(deleted)} item(s)."
    })



@lancloud_bp.route(
    "/file-operation-new-directory",
    methods=["POST"]
)
def file_operation_new_directory():
    try:
        data = request.get_json(silent=True) or {}
        directory_name = data.get("directory_name", "").strip()

        if (
            not directory_name
            or directory_name in (".", "..")
            or "/" in directory_name
            or "\\" in directory_name
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid directory name."
            }), 400

        destination = resolve_path(
            get_current_directory()
        )

        if not destination.is_dir():
            return jsonify({
                "status": "error",
                "message": "Current directory not found."
            }), 404

        new_directory = destination / directory_name

        if new_directory.exists():
            return jsonify({
                "status": "error",
                "message": "Directory already exists."
            }), 409

        new_directory.mkdir(exist_ok=False)

        return jsonify({
            "status": "ok",
            "message": "Directory created successfully."
        })

    except PermissionError:
        return jsonify({
            "status": "error",
            "message": "Access denied."
        }), 403

    except OSError as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 500
