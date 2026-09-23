<!doctype html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width,
                   initial-scale=1,
                   maximum-scale=1,
                   user-scalable=no,
                   viewport-fit=cover">

    <meta name="apple-mobile-web-app-capable"
          content="yes">

    <meta name="apple-mobile-web-app-status-bar-style"
          content="black">

    <meta name="theme-color"
          content="#111111">

    <title>Remote — TV</title>

    <link rel="stylesheet"
          href="{{ url_for(
              'tvremote.static',
              filename='tvremote.css'
          ) }}">

</head>

<body>

<div id="tvRemoteScreen">

    <header class="topbar">

        <button id="tvBackButton"
                class="topButton"
                type="button">
            ← Back
        </button>

        <div class="title">
            Android TV
        </div>

        <div id="connectionStatus"
             class="connectionStatus">

            <span id="statusDot"
                  class="statusDot offline">
            </span>

            <span id="statusText">
                Connecting…
            </span>

        </div>

    </header>


    <main class="remote">


        <!-- POWER -->

        <section class="powerRow">

            <button class="roundButton powerButton"
                    data-command="power"
                    aria-label="Power">
                ⏻
            </button>

        </section>


        <!-- D-PAD -->

        <section class="dpad"
                 aria-label="TV navigation">

            <button class="remoteButton dpadUp"
                    data-command="up">
                ▲
            </button>

            <button class="remoteButton dpadLeft"
                    data-command="left">
                ◀
            </button>

            <button class="remoteButton dpadOK"
                    data-command="select">
                OK
            </button>

            <button class="remoteButton dpadRight"
                    data-command="right">
                ▶
            </button>

            <button class="remoteButton dpadDown"
                    data-command="down">
                ▼
            </button>

        </section>


        <!-- NAVIGATION -->

        <section class="threeButtons">

            <button class="remoteButton"
                    data-command="back">

                <span class="largeIcon">↩</span>
                <span>BACK</span>

            </button>

            <button class="remoteButton"
                    data-command="home">

                <span class="largeIcon">⌂</span>
                <span>HOME</span>

            </button>

            <button class="remoteButton"
                    data-command="mute">

                <span class="largeIcon">🔇</span>
                <span>MUTE</span>

            </button>

        </section>


        <!-- VOLUME -->

        <section class="volumeControl">

            <button class="volumeButton"
                    data-command="vol_down">
                −
            </button>

            <span class="volumeLabel">
                VOLUME
            </span>

            <button class="volumeButton"
                    data-command="vol_up">
                +
            </button>

        </section>


        <!-- APPS -->

        <section class="apps">

            <button class="appButton youtube"
                    data-command="youtube">
                YouTube
            </button>

            <button class="appButton netflix"
                    data-command="netflix">
                Netflix
            </button>

            <button class="appButton"
                    data-package="org.videolan.vlc">
                VLC
            </button>

        </section>


        <!-- TEXT ENTRY -->

        <section class="textEntry">

            <input id="tvTextInput"
                   type="text"
                   autocomplete="off"
                   autocorrect="off"
                   autocapitalize="sentences"
                   spellcheck="false"
                   placeholder="Type text on TV">

            <button id="sendTextButton"
                    type="button">
                SEND
            </button>

        </section>


        <!-- OTHER -->

        <section class="utilityButtons">

            <button class="remoteButton"
                    data-command="status">
                ↻ Status
            </button>

            <button class="remoteButton"
                    data-command="screenshot">
                📷 Screenshot
            </button>

            <button id="fullscreenButton"
                    class="remoteButton"
                    type="button">
                ⛶ Fullscreen
            </button>

        </section>


    </main>

</div>


<div id="toast"
     class="toast">
</div>


<script src="{{ url_for(
    'static',
    filename='socket.io.min.js'
) }}"></script>

<script src="{{ url_for(
    'tvremote.static',
    filename='tvremote/tvremote.js'
) }}"></script>

</body>

</html>
