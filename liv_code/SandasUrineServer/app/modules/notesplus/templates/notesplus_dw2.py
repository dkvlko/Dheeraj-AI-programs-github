<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Notes Plus</title>


    <!-- EasyMDE CSS -->
    <link
        rel="stylesheet"
        href="/notesplus/static/easymde.min.css"
    >


    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 20px;

            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;

            background: #f4f6f8;
            color: #222;
        }


        .notes-container {
            max-width: 1200px;
            margin: auto;
        }


        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;

            margin-bottom: 20px;
        }


        .header h1 {
            margin: 0;
        }


        .button {
            border: none;
            border-radius: 6px;

            padding: 10px 18px;

            font-size: 15px;

            cursor: pointer;

            background: #1976d2;
            color: white;
        }


        .button:hover {
            background: #125ea8;
        }


        .button.secondary {
            background: #666;
        }


        .button.danger {
            background: #c62828;
        }


        .field {
            margin-bottom: 15px;
        }


        .field label {
            display: block;

            margin-bottom: 5px;

            font-weight: 600;
        }


        .field input {
            width: 100%;

            padding: 11px;

            border: 1px solid #bbb;
            border-radius: 5px;

            font-size: 16px;
        }


        .metadata {
            margin-top: 15px;

            padding: 10px;

            background: white;

            border-radius: 6px;

            font-size: 13px;

            color: #666;
        }


        .readonly {
            background: white;

            padding: 25px;

            border-radius: 8px;

            min-height: 300px;

            line-height: 1.6;
        }


        .toolbar {
            display: flex;

            gap: 10px;

            margin-top: 15px;
        }


        #editor-area {
            display: none;
        }


        #save-status {
            margin-left: 10px;

            font-size: 14px;
        }


        @media (max-width: 600px) {

            body {
                padding: 10px;
            }

            .header {
                align-items: flex-start;

                gap: 10px;
            }

            .toolbar {
                flex-wrap: wrap;
            }

        }

    </style>

</head>


<body>

<div class="notes-container">


    <div class="header">

        <h1>Notes Plus</h1>

        <div>

            <button
                class="button"
                onclick="createTestNote()"
            >
                Create Test Note
            </button>

        </div>

    </div>


    <!-- Title -->

    <div class="field">

        <label for="title">
            Title
        </label>

        <input
            id="title"
            type="text"
            value="{{ note.title if note else '' }}"
            readonly
        >

    </div>


    <!-- Topic -->

    <div class="field">

        <label for="topic">
            Topic
        </label>

        <input
            id="topic"
            type="text"
            value="{{ note.topic if note else '' }}"
            readonly
        >

    </div>


    <!-- READ ONLY DISPLAY -->

    <div
        id="readonly-view"
        class="readonly"
    >

        {% if note %}

            <div id="rendered-note"></div>

        {% else %}

            <p>
                No note exists yet.
            </p>

        {% endif %}

    </div>


    <!-- EDITOR -->

    <div id="editor-area">

        <textarea id="editor"></textarea>

    </div>


    <!-- Buttons -->

    <div class="toolbar">

        <button
            id="edit-button"
            class="button"
            onclick="startEditing()"
        >
            Edit
        </button>


        <button
            id="save-button"
            class="button"
            onclick="saveNote()"
            style="display:none;"
        >
            Save
        </button>


        <button
            id="cancel-button"
            class="button secondary"
            onclick="cancelEditing()"
            style="display:none;"
        >
            Cancel
        </button>


        <span id="save-status"></span>

    </div>


    {% if note %}

    <div class="metadata">

        <div>
            Created:
            <span id="created-date">
                {{ note.created_at }}
            </span>
        </div>

        <div>
            Modified:
            <span id="modified-date">
                {{ note.modified_at }}
            </span>
        </div>

    </div>

    {% endif %}


</div>


<!-- EasyMDE JavaScript -->

<script
    src="/notesplus/static/easymde.min.js">
</script>


<script>

    /*
     * Current note information supplied by Flask.
     */

    const currentNote = {% if note %}
        {{ note|tojson }};
    {% else %}
        null;
    {% endif %}


    let easyMDE = null;


    /*
     * Render Markdown.
     *
     * EasyMDE uses its Markdown parser internally.
     */

    function renderMarkdown(markdown) {

        if (!markdown) {
            document.getElementById(
                "rendered-note"
            ).innerHTML = "";

            return;
        }

        /*
         * EasyMDE's preview renderer is based on marked.
         *
         * We use it only after EasyMDE has been initialized.
         */

        if (easyMDE) {

            const html =
                easyMDE.options.previewRender(markdown);

            document.getElementById(
                "rendered-note"
            ).innerHTML = html;

        }

    }


    /*
     * Initialize EasyMDE.
     */

    function initializeEditor() {

        if (easyMDE) {
            return;
        }

        easyMDE = new EasyMDE({

            element:
                document.getElementById("editor"),

            spellChecker: false,

            status: false,

            autofocus: false,

            previewImagesInEditor: true,

            sideBySide: true,

            renderingConfig: {
                singleLineBreaks: false,
                codeSyntaxHighlighting: true
            }

        });

    }


    /*
     * Start editing.
     */

    function startEditing() {

        initializeEditor();


        document.getElementById(
            "readonly-view"
        ).style.display = "none";


        document.getElementById(
            "editor-area"
        ).style.display = "block";


        document.getElementById(
            "edit-button"
        ).style.display = "none";


        document.getElementById(
            "save-button"
        ).style.display = "inline-block";


        document.getElementById(
            "cancel-button"
        ).style.display = "inline-block";


        document.getElementById(
            "title"
        ).readOnly = false;


        document.getElementById(
            "topic"
        ).readOnly = false;


        easyMDE.value(
            currentNote
                ? currentNote.content
                : ""
        );


        easyMDE.codemirror.refresh();

    }


    /*
     * Cancel editing.
     */

    function cancelEditing() {

        document.getElementById(
            "readonly-view"
        ).style.display = "block";


        document.getElementById(
            "editor-area"
        ).style.display = "none";


        document.getElementById(
            "edit-button"
        ).style.display = "inline-block";


        document.getElementById(
            "save-button"
        ).style.display = "none";


        document.getElementById(
            "cancel-button"
        ).style.display = "none";


        document.getElementById(
            "title"
        ).readOnly = true;


        document.getElementById(
            "topic"
        ).readOnly = true;


        if (currentNote) {

            document.getElementById(
                "title"
            ).value = currentNote.title;


            document.getElementById(
                "topic"
            ).value = currentNote.topic;

        }

    }


    /*
     * Save note.
     */

    async function saveNote() {

        const title =
            document.getElementById("title").value.trim();


        let topic =
            document.getElementById("topic").value.trim();


        const content =
            easyMDE.value();


        if (!title) {

            alert("Title is required.");

            return;
        }


        /*
         * Requirement:
         *
         * Blank topic → title becomes topic.
         */

        if (!topic) {
            topic = title;

            document.getElementById(
                "topic"
            ).value = topic;
        }


        document.getElementById(
            "save-status"
        ).textContent = "Saving...";


        try {

            const response = await fetch(
                "/notesplus/save",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        id:
                            currentNote
                                ? currentNote.id
                                : null,

                        title: title,

                        topic: topic,

                        content: content

                    })
                }
            );


            const result =
                await response.json();


            if (!result.success) {

                throw new Error(
                    result.error ||
                    "Save failed."
                );

            }


            document.getElementById(
                "save-status"
            ).textContent = "Saved";


            /*
             * Reload the page so that the newly
             * saved Markdown is displayed read-only.
             */

            setTimeout(
                () => window.location.reload(),
                300
            );


        } catch (error) {

            console.error(error);

            document.getElementById(
                "save-status"
            ).textContent = "Save failed";

            alert(error.message);

        }

    }


    /*
     * Create the initial test note.
     */

    async function createTestNote() {

        try {

            const response =
                await fetch(
                    "/notesplus/create-test",
                    {
                        method: "POST"
                    }
                );


            const result =
                await response.json();


            if (!result.success) {

                alert(
                    result.error ||
                    "Could not create note."
                );

                return;
            }


            /*
             * Reload the page.
             */

            window.location.reload();

        } catch (error) {

            console.error(error);

            alert(
                "Error creating test note."
            );

        }

    }


    /*
     * Initial page rendering.
     */

    document.addEventListener(
        "DOMContentLoaded",
        function () {

            if (!currentNote) {
                return;
            }


            initializeEditor();


            /*
             * Render the stored Markdown.
             */

            renderMarkdown(
                currentNote.content
            );

        }
    );

</script>

</body>

</html>
