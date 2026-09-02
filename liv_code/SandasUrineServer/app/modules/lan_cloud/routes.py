
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



@lancloud_bp.route("/")
def LANcloud():

    state.BuildLANcloudDirectoryJSON()

    print(
        f"[LANcloud] "
        f"{len(state.LANcloud_JSON['entries'])} entries loaded."
    )

    return render_template("lancloud/showdirfiles.html")  


@lancloud_bp.route("/list")
def LANcloudList():

    folder = request.args.get("folder", "")

    requested = (paths.LAN_CLOUD_FOLDER / folder).resolve()

    #
    # Prevent leaving the shared folder.
    #
    if not str(requested).startswith(str(paths.LAN_CLOUD_FOLDER.resolve())):
        return jsonify({"error": "Access denied"}), 403

    if not requested.exists() or not requested.is_dir():
        return jsonify({"error": "Directory not found"}), 404

    state.BuildLANcloudDirectoryJSON(requested)

    return jsonify(state.LANcloud_JSON)


@lancloud_bp.route("/change-directory")
def LANcloudChangeDirectory():

    item_id = request.args.get("id")

    if item_id not in state.LANcloud_ID_MAP:
        return jsonify({"error": "Invalid directory"}), 404

    destination = state.LANcloud_ID_MAP[item_id]

    if not destination.is_dir():
        return jsonify({"error": "Not a directory"}), 400

    state.BuildLANcloudDirectoryJSON(destination)

    return jsonify(state.LANcloud_JSON)


@lancloud_bp.route("/file-operation-download")
def file_operation_download():

    name = request.args.get("name")

    if not name:
        return "No file selected.", 400

    path = paths.LAN_CLOUD_FOLDER / name

    if not path.exists():
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

        if current_directory == paths.LAN_CLOUD_FOLDER.name:

            destination_directory = paths.LAN_CLOUD_FOLDER

        else:

            destination_directory = (
                paths.LAN_CLOUD_FOLDER /
                current_directory
            )

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

            state.BuildLANcloudDirectoryJSON()


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

    data = request.get_json()

    operation = data.get("operation")

    selected = data.get("selected", [])

    if operation != "delete":

        return jsonify({

            "status": "error",

            "message": "Unsupported operation."

        })

    deleted = []

    failed = []

    for name in selected:

        path = paths.LAN_CLOUD_FOLDER / name

        try:

            if path.is_dir():

                shutil.rmtree(path)

            elif path.is_file():

                path.unlink()

            else:

                failed.append(name)

                continue

            deleted.append(name)

        except Exception as e:

            failed.append(f"{name} ({e})")

    state.BuildLANcloudDirectoryJSON()

    return jsonify({

        "status": "ok",

        "deleted": deleted,

        "failed": failed,

        "message":
            f"Deleted {len(deleted)} item(s)."

    })


@lancloud_bp.route(
    "/file-operation-new-directory",
    methods=["POST"]
)
def file_operation_new_directory():

    try:

        data = request.get_json()

        current_directory = data[
            "current_directory"
        ]

        directory_name = data[
            "directory_name"
        ].strip()


        #######################################################
        # Basic Validation
        #######################################################

        if (
            "/" in directory_name or
            "\\" in directory_name
        ):

            return jsonify(
            {
                "status":"error",
                "message":
                "Invalid directory name."
            })


        #######################################################
        # Destination
        #######################################################

        if current_directory == "":

            destination = paths.LAN_CLOUD_FOLDER

        else:

            destination = (
                paths.LAN_CLOUD_FOLDER /
                current_directory
            )


        new_directory = (
            destination /
            directory_name
        )


        #######################################################
        # Already Exists
        #######################################################

        if new_directory.exists():

            return jsonify(
            {
                "status":"error",

                "message":
                "Directory already exists."
            })


        #######################################################
        # Create Directory
        #######################################################

        new_directory.mkdir(
            parents=True,
            exist_ok=False
        )

        state.BuildLANcloudDirectoryJSON(
            destination
        )

        return jsonify(
        {
            "status":"ok",

            "message":
            "Directory created successfully."
        })


    except Exception as e:

        return jsonify(
        {
            "status":"error",

            "message":
            str(e)
        }),500
