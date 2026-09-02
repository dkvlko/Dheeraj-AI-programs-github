"use strict";

/*****************************************************************
 * Global Variables
 *****************************************************************/

let websocket = null;

let currentDirectory = "";

let directoryEntries = [];


/*****************************************************************
 * Load Directory Listing
 *****************************************************************/

function loadDirectory()
{
    document.getElementById("DirectoryList").innerHTML = "";
    fetch("/lan_cloud/list")
    .then(function(response)
    {
        if (!response.ok)
            throw new Error("Failed to load directory.");

        return response.json();
    })
    .then(function(message)
    {
        currentDirectory =
            message.current_directory;

        directoryEntries =
            message.entries;

        document.getElementById(
            "CurrentDirectory"
        ).textContent =
            "Current Directory : " +
            currentDirectory;

        buildDirectoryList();
    })
    .catch(function(error)
    {
        console.error(error);

        alert(
            "Unable to load directory listing."
        );
    });
}


/*****************************************************************
 * Build Directory List
 *****************************************************************/

function buildDirectoryList()
{
    const container =
        document.getElementById("DirectoryList");

    container.innerHTML = "";

    directoryEntries.forEach(function(entry)
    {
        const row =
            document.createElement("div");

        row.className = "DirectoryRow";


        /* Checkbox */

        const checkCell =
            document.createElement("div");

        const checkbox =
            document.createElement("input");

        checkbox.type = "checkbox";

        checkbox.dataset.id = entry.id;

        checkbox.dataset.name = entry.name;

        checkCell.appendChild(checkbox);

        row.appendChild(checkCell);


        /* Name */

        const nameCell =
            document.createElement("div");

        nameCell.className =
            "DirectoryName";

        let icon =
            (entry.type === "directory")
            ? "📁 "
            : "📄 ";

        /*nameCell.textContent =
            icon + entry.name;*/

        if (entry.type === "directory")
        {
            const link =
                document.createElement("a");

            link.href = "#";

            link.textContent =
                icon + entry.name;

            link.onclick =
            function(event)
            {
                event.preventDefault();

                fetch(
                    "/lan_cloud/change-directory?id=" +
                    encodeURIComponent(entry.id)
                )
                .then(r => r.json())
                .then(function(message)
                {
                    currentDirectory =
                        message.current_directory;

                    directoryEntries =
                        message.entries;

                    document.getElementById(
                        "CurrentDirectory"
                    ).textContent =
                        "Current Directory : " +
                        (
                            currentDirectory === ""
                            ? "SharedDataOnLan"
                            : currentDirectory
                        );

                    buildDirectoryList();
                });
            };

            nameCell.appendChild(link);
        }
        else
        {
            nameCell.textContent =
                icon + entry.name;
        }

        row.appendChild(nameCell);


        /* Type */

        const typeCell =
            document.createElement("div");

        typeCell.className =
            "DirectoryType";

        typeCell.textContent =
            entry.type;

        row.appendChild(typeCell);


        /* Size */

        const sizeCell =
            document.createElement("div");

        sizeCell.className =
            "DirectorySize";

        sizeCell.textContent =
            formatSize(entry.size);

        row.appendChild(sizeCell);


        /* Modified */

        const modifiedCell =
            document.createElement("div");

        modifiedCell.className =
            "DirectoryModified";

        modifiedCell.textContent =
            entry.modified;

        row.appendChild(modifiedCell);

        container.appendChild(row);
    });
}


/*****************************************************************
 * Convert Size
 *****************************************************************/

function formatSize(bytes)
{
    if (bytes === 0)
        return "--";

    if (bytes < 1024)
        return bytes + " B";

    if (bytes < 1024 * 1024)
        return (bytes / 1024).toFixed(1) + " KB";

    if (bytes < 1024 * 1024 * 1024)
        return (bytes / 1024 / 1024).toFixed(1) + " MB";

    return (bytes / 1024 / 1024 / 1024).toFixed(1) + " GB";
}


/*****************************************************************
 * Selected Items
 *****************************************************************/

function getSelectedItems()
{
    let selected = [];

    document
        .querySelectorAll(
            "#DirectoryList input[type='checkbox']:checked"
        )
        .forEach(function(cb)
        {
            selected.push(
            {
                id: cb.dataset.id,
                name: cb.dataset.name
            });
        });

    return selected;
}


/*****************************************************************
 * Upload Button
 *****************************************************************/

document
.getElementById("UploadButton")
.addEventListener(
"click",
async function()
{

    alert(
        "Firefox cannot upload folders directly.\n\n" +
        "Please zip the folder before uploading."
    );

    const picker =
        document.createElement("input");

    picker.type = "file";

    picker.multiple = true;

    picker.style.display = "none";

    document.body.appendChild(picker);

    picker.onchange =
    async function()
    {

        if (picker.files.length === 0)
        {
            document.body.removeChild(picker);
            return;
        }

        for (const file of picker.files)
        {
            await uploadFile(file);
        }

        document.body.removeChild(picker);

        alert("Upload completed.");

        loadDirectory();
    };

    picker.click();

});


/*****************************************************************
 * Upload One File
 *****************************************************************/

async function uploadFile(file)
{

    const CHUNK_SIZE =
        1024 * 1024;          // 1 MB

    const totalChunks =
        Math.ceil(file.size / CHUNK_SIZE);

    for (
        let chunkNumber = 0;
        chunkNumber < totalChunks;
        chunkNumber++
    )
    {

        const start =
            chunkNumber * CHUNK_SIZE;

        const end =
            Math.min(
                start + CHUNK_SIZE,
                file.size
            );

        const blob =
            file.slice(start, end);

        const formData =
            new FormData();

        formData.append(
            "file",
            blob
        );

        formData.append(
            "filename",
            file.name
        );

        formData.append(
            "current_directory",
            currentDirectory
        );

        formData.append(
            "chunk_number",
            chunkNumber
        );

        formData.append(
            "total_chunks",
            totalChunks
        );

        formData.append(
            "file_size",
            file.size
        );

        const response =
            await fetch(
                "/lan_cloud/file-operation-upload",
                {
                    method: "POST",
                    body: formData
                }
            );

        if (!response.ok)
        {
            alert(
                "Upload failed for " +
                file.name
            );

            return;
        }

    }

}

/*****************************************************************
 * Download Button
 *****************************************************************/

document
.getElementById("DownloadButton")
.addEventListener(
"click",
function()
{
    const selected =
        getSelectedItems();

    if (selected.length === 0)
    {
        alert(
            "Please select the directory or folder to download"
        );
        return;
    }

    if (selected.length > 1)
    {
        alert(
            "Please select only one file or directory."
        );
        return;
    }

    const name = selected[0].name;

    alert(
        "You selected " +
        name +
        " to download"
    );

    window.location =
        "/lan_cloud/file-operation-download?name=" +
        encodeURIComponent(name);
});

/*****************************************************************
 * Delete Button
 *****************************************************************/

document
.getElementById("DeleteButton")
.addEventListener(
"click",
function()
{
    const selected =
        getSelectedItems();

    if (selected.length === 0)
    {
        alert(
            "Please select the directory or folder to delete"
        );
        return;
    }

    const names =
        selected.map(
            item => item.name
        );

    alert(
        "You selected " +
        names.join(", ") +
        " to delete"
    );


    fetch("/lan_cloud/file-operation", {

        method: "POST",

        headers:
        {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({

            operation: "delete",

            selected: names

        })

    })
    .then(response => response.json())
    .then(result =>
    {
        alert(result.message);

        loadDirectory();      // Refresh the list
    })
    .catch(error =>
    {
        console.error(error);

        alert("Delete operation failed.");
    });

});

/*****************************************************************
 * New Folder Button
 *****************************************************************/

document
.getElementById("NewFolderButton")
.addEventListener(
"click",
async function()
{

    let folderName =
        prompt(
            "Enter the new directory name:"
        );

    if(folderName == null)
        return;

    folderName =
        folderName.trim();

    if(folderName.length == 0)
    {
        alert("Directory name cannot be empty.");
        return;
    }

    const response =
        await fetch(
            "/lan_cloud/file-operation-new-directory",
            {
                method : "POST",

                headers :
                {
                    "Content-Type":
                        "application/json"
                },

                body :
                    JSON.stringify(
                    {
                        current_directory :
                            currentDirectory,

                        directory_name :
                            folderName
                    })
            });

    const result =
        await response.json();

    alert(result.message);

    if(result.status == "ok")
        loadDirectory();

});

/*****************************************************************
 * Start
 *****************************************************************/
window.addEventListener(
"load",
function()
{
    loadDirectory();
});
