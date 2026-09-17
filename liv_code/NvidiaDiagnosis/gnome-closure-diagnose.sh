#!/usr/bin/env bash

###############################################################################
# GNOME Shell GClosure Diagnostic
#
# Purpose:
#   Investigate repeated:
#
#   g_closure_add_invalidate_notifier:
#   assertion 'closure->n_inotifiers < CLOSURE_MAX_N_INOTIFIERS' failed
#
# This script is diagnostic only. It does NOT modify GNOME, NVIDIA, extensions,
# GSettings, systemd, or any other system configuration.
#
# Run as the logged-in desktop user:
#
#   sudo ./gnome-closure-diagnose.sh
#
# Recommended:
#   Run this while the GClosure error is actively appearing in journalctl.
###############################################################################

set +e

###############################################################################
# CONFIGURATION
###############################################################################

OUTDIR="/tmp/gnome-closure-diagnosis-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTDIR"

MAINLOG="$OUTDIR/diagnosis.log"

exec > >(tee -a "$MAINLOG") 2>&1

###############################################################################
# HELPERS
###############################################################################

section()
{
    echo
    echo
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

run()
{
    echo
    echo "+ $*"
    timeout 30s "$@" 2>&1 || true
}

run_shell()
{
    echo
    echo "+ $*"
    timeout 30s bash -c "$*" 2>&1 || true
}

###############################################################################
# BASIC INFORMATION
###############################################################################

section "GNOME CLOSURE DIAGNOSTIC START"

date
hostnamectl 2>/dev/null || hostname
uname -a
uptime
id

echo
echo "Output directory:"
echo "$OUTDIR"

###############################################################################
# OS / GNOME / GLIB INFORMATION
###############################################################################

section "OPERATING SYSTEM"

run cat /etc/os-release

section "GNOME VERSION"

run gnome-shell --version

section "GLIB VERSION"

run pkg-config --modversion glib-2.0
run dpkg-query -W libglib2.0-0 2>/dev/null
run dpkg-query -W libglib2.0-bin 2>/dev/null
run dpkg-query -W libglib2.0-dev 2>/dev/null

###############################################################################
# FIND GNOME SHELL
###############################################################################

section "GNOME SHELL PROCESSES"

GNOME_PIDS="$(pgrep -x gnome-shell)"

if [ -z "$GNOME_PIDS" ]; then
    echo "ERROR: gnome-shell process was not found."
else
    echo "GNOME Shell PID(s):"
    echo "$GNOME_PIDS"

    for PID in $GNOME_PIDS; do
        echo
        echo "----- PID $PID -----"

        run ps -fp "$PID"

        echo
        echo "Command line:"
        tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null
        echo

        echo
        echo "Executable:"
        readlink -f "/proc/$PID/exe" 2>/dev/null

        echo
        echo "Working directory:"
        readlink -f "/proc/$PID/cwd" 2>/dev/null

        echo
        echo "Process state:"
        grep -E '^(Name|State|Pid|PPid|Uid|Gid|Threads):' \
            "/proc/$PID/status" 2>/dev/null

        echo
        echo "Process environment:"
        tr '\0' '\n' < "/proc/$PID/environ" 2>/dev/null |
            grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_SESSION_TYPE|XDG_CURRENT_DESKTOP|GNOME_SHELL|GJS|GDK|GTK|MUTTER|NVIDIA|LIBGL|__GLX|EGL|LD_LIBRARY_PATH|PATH)='

    done
fi

###############################################################################
# FIND DESKTOP SESSION
###############################################################################

section "LOGIN / GRAPHICAL SESSION"

run loginctl list-sessions

echo
run loginctl list-users

###############################################################################
# DETERMINE GNOME USER
###############################################################################

GNOME_PID="$(pgrep -xo gnome-shell)"

if [ -n "$GNOME_PID" ] && [ -r "/proc/$GNOME_PID/status" ]; then

    GNOME_UID="$(awk '/^Uid:/ {print $2}' "/proc/$GNOME_PID/status")"

    if [ -n "$GNOME_UID" ]; then
        GNOME_USER="$(getent passwd "$GNOME_UID" | cut -d: -f1)"
    fi
fi

echo
echo "GNOME Shell PID : ${GNOME_PID:-NOT FOUND}"
echo "GNOME UID       : ${GNOME_UID:-NOT FOUND}"
echo "GNOME USER      : ${GNOME_USER:-NOT FOUND}"

###############################################################################
# GRAPHICAL ENVIRONMENT
###############################################################################

section "GRAPHICAL ENVIRONMENT"

if [ -n "$GNOME_PID" ] && [ -r "/proc/$GNOME_PID/environ" ]; then

    tr '\0' '\n' < "/proc/$GNOME_PID/environ" 2>/dev/null |
        grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_SESSION_TYPE|XDG_RUNTIME_DIR|XDG_CURRENT_DESKTOP|DESKTOP_SESSION|GDMSESSION)='

else
    echo "Cannot read GNOME Shell environment."
fi

###############################################################################
# GNOME SHELL EXTENSIONS
###############################################################################

section "GNOME SHELL EXTENSIONS"

if command -v gnome-extensions >/dev/null 2>&1; then

    echo "All installed extensions:"
    run gnome-extensions list

    echo
    echo "Enabled extensions:"
    run gnome-extensions list --enabled

    echo
    echo "Extension information:"
    if [ -n "$GNOME_USER" ]; then
        run_shell "sudo -u '$GNOME_USER' gnome-extensions list --enabled"
    fi

else
    echo "gnome-extensions command not found."
fi

###############################################################################
# EXTENSION DIRECTORIES
###############################################################################

section "EXTENSION DIRECTORIES"

if [ -n "$GNOME_USER" ]; then

    USER_HOME="$(getent passwd "$GNOME_USER" | cut -d: -f6)"

    echo "User home: $USER_HOME"

    echo
    echo "~/.local/share/gnome-shell/extensions:"
    ls -la "$USER_HOME/.local/share/gnome-shell/extensions" 2>/dev/null

    echo
    echo "/usr/share/gnome-shell/extensions:"
    ls -la /usr/share/gnome-shell/extensions 2>/dev/null

fi

###############################################################################
# GNOME SHELL JOURNAL
###############################################################################

section "GNOME SHELL JOURNAL - LAST 10 MINUTES"

run journalctl --since "10 minutes ago" \
    -o short-precise \
    _COMM=gnome-shell

###############################################################################
# ONLY THE G_CLOSURE ERRORS
###############################################################################

section "G_CLOSURE ERROR FREQUENCY"

run_shell "journalctl --since '30 minutes ago' -o short-precise | \
grep -F 'g_closure_add_invalidate_notifier'"

echo
echo "Total GClosure assertions in last 30 minutes:"

journalctl --since "30 minutes ago" --no-pager 2>/dev/null |
    grep -F -c 'g_closure_add_invalidate_notifier' 2>/dev/null || true

###############################################################################
# TIMESTAMP ANALYSIS
###############################################################################

section "G_CLOSURE ERROR TIMING"

run_shell "journalctl --since '30 minutes ago' -o short-precise | \
grep -F 'g_closure_add_invalidate_notifier' | \
awk '{print \$1, \$2}'"

###############################################################################
# GNOME SHELL WARNINGS / CRITICALS
###############################################################################

section "GNOME SHELL WARNINGS / CRITICALS"

run_shell "journalctl --since '30 minutes ago' -o short-precise | \
grep -Ei 'gnome-shell.*(warning|critical|assert|failed|error)'"

###############################################################################
# GNOME SHELL JOURNAL WITH CONTEXT
###############################################################################

section "G_CLOSURE ERRORS WITH JOURNAL CONTEXT"

run_shell "journalctl --since '10 minutes ago' -o short-precise | \
grep -B 5 -A 5 -F 'g_closure_add_invalidate_notifier'"

###############################################################################
# GNOME SHELL CHILD PROCESSES
###############################################################################

section "GNOME SHELL CHILD PROCESSES"

if [ -n "$GNOME_PID" ]; then
    run pstree -alp "$GNOME_PID"
fi

###############################################################################
# GNOME SHELL OPEN FILES
###############################################################################

section "GNOME SHELL OPEN FILES"

if [ -n "$GNOME_PID" ]; then

    echo "Number of open file descriptors:"
    ls "/proc/$GNOME_PID/fd" 2>/dev/null | wc -l

    echo
    echo "Open files / libraries:"
    run lsof -p "$GNOME_PID"

fi

###############################################################################
# GNOME SHELL LIBRARIES
###############################################################################

section "GNOME SHELL MEMORY MAP / LIBRARIES"

if [ -n "$GNOME_PID" ]; then

    echo "Shared libraries:"
    run_shell "grep '\\.so' /proc/$GNOME_PID/maps | \
    sed 's/.* //' | sort -u"

fi

###############################################################################
# LOOK FOR GLIB / GOBJECT LIBRARY
###############################################################################

section "ACTUAL GLIB LIBRARY USED BY GNOME SHELL"

if [ -n "$GNOME_PID" ]; then

    run_shell "grep -E '/libglib|/libgobject' /proc/$GNOME_PID/maps | sort -u"

fi

###############################################################################
# GOBJECT / GLIB RELATED ENVIRONMENT
###############################################################################

section "GLIB / GOBJECT ENVIRONMENT"

if [ -n "$GNOME_PID" ]; then

    tr '\0' '\n' < "/proc/$GNOME_PID/environ" 2>/dev/null |
        grep -Ei 'GLIB|GOBJECT|GJS|GTK|MUTTER|GDK|DEBUG|TRACE|PROFILE'
fi

###############################################################################
# GSETTINGS
###############################################################################

section "GNOME SHELL GSETTINGS"

if [ -n "$GNOME_USER" ]; then

    run_shell "sudo -u '$GNOME_USER' gsettings list-recursively org.gnome.shell"

fi

###############################################################################
# EXTENSION SETTINGS
###############################################################################

section "GNOME SHELL EXTENSION SETTINGS"

if [ -n "$GNOME_USER" ]; then

    run_shell "sudo -u '$GNOME_USER' gsettings list-recursively org.gnome.shell.extensions"
fi

###############################################################################
# DBUS GNOME SHELL
###############################################################################

section "GNOME SHELL DBUS NAMES"

if [ -n "$GNOME_USER" ]; then

    USER_RUNTIME="/run/user/$GNOME_UID"

    if [ -S "$USER_RUNTIME/bus" ]; then

        run_shell "sudo -u '$GNOME_USER' \
            env XDG_RUNTIME_DIR='$USER_RUNTIME' \
            DBUS_SESSION_BUS_ADDRESS='unix:path=$USER_RUNTIME/bus' \
            busctl --user list"

    fi
fi

###############################################################################
# DBUS MONITOR - SHORT SAMPLE
###############################################################################

section "DBUS MONITOR - 15 SECOND SAMPLE"

if [ -n "$GNOME_USER" ] && [ -n "$GNOME_UID" ]; then

    USER_RUNTIME="/run/user/$GNOME_UID"

    if [ -S "$USER_RUNTIME/bus" ]; then

        echo "Capturing D-Bus activity for 15 seconds..."

        timeout 15s sudo -u "$GNOME_USER" \
            env \
            XDG_RUNTIME_DIR="$USER_RUNTIME" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=$USER_RUNTIME/bus" \
            busctl --user monitor 2>&1 |
            head -n 500

    fi
fi

###############################################################################
# X11 INFORMATION
###############################################################################

section "X11 INFORMATION"

X11_DISPLAY=""
X11_AUTH=""

if [ -n "$GNOME_PID" ] && [ -r "/proc/$GNOME_PID/environ" ]; then

    X11_DISPLAY="$(
        tr '\0' '\n' < "/proc/$GNOME_PID/environ" |
        sed -n 's/^DISPLAY=//p' | head -1
    )"

    X11_AUTH="$(
        tr '\0' '\n' < "/proc/$GNOME_PID/environ" |
        sed -n 's/^XAUTHORITY=//p' | head -1
    )"

fi

echo "DISPLAY    = ${X11_DISPLAY:-NOT FOUND}"
echo "XAUTHORITY = ${X11_AUTH:-NOT FOUND}"

if [ -n "$GNOME_USER" ] && [ -n "$X11_DISPLAY" ]; then

    if [ -z "$X11_AUTH" ]; then
        USER_HOME="$(getent passwd "$GNOME_USER" | cut -d: -f6)"

        if [ -f "$USER_HOME/.Xauthority" ]; then
            X11_AUTH="$USER_HOME/.Xauthority"
        fi
    fi

    echo
    echo "Running X11 queries..."

    run_shell "sudo -u '$GNOME_USER' \
        env DISPLAY='$X11_DISPLAY' XAUTHORITY='$X11_AUTH' \
        xrandr --query"

    run_shell "sudo -u '$GNOME_USER' \
        env DISPLAY='$X11_DISPLAY' XAUTHORITY='$X11_AUTH' \
        xrandr --listproviders"

    run_shell "sudo -u '$GNOME_USER' \
        env DISPLAY='$X11_DISPLAY' XAUTHORITY='$X11_AUTH' \
        xdpyinfo"

    run_shell "sudo -u '$GNOME_USER' \
        env DISPLAY='$X11_DISPLAY' XAUTHORITY='$X11_AUTH' \
        xinput list"

fi

###############################################################################
# WAYLAND
###############################################################################

section "WAYLAND INFORMATION"

if [ -n "$GNOME_PID" ]; then

    tr '\0' '\n' < "/proc/$GNOME_PID/environ" 2>/dev/null |
        grep -E '^(WAYLAND_DISPLAY|XDG_SESSION_TYPE|XDG_RUNTIME_DIR)='

fi

###############################################################################
# NVIDIA CORRELATION
###############################################################################

section "NVIDIA STATUS"

run nvidia-smi

run nvidia-smi --query-compute-apps=pid,process_name,used_memory \
    --format=csv

###############################################################################
# GPU PROCESSES
###############################################################################

section "GPU RELATED PROCESSES"

run_shell "ps aux | grep -Ei 'gnome-shell|mutter|Xorg|nvidia|firefox|chrome' | grep -v grep"

###############################################################################
# NVIDIA LIBRARIES USED BY GNOME SHELL
###############################################################################

section "NVIDIA LIBRARIES MAPPED INTO GNOME SHELL"

if [ -n "$GNOME_PID" ]; then

    run_shell "grep -Ei 'nvidia|libGL|libEGL|libcuda|libnv' \
        /proc/$GNOME_PID/maps | sort -u"

fi

###############################################################################
# STRACE
###############################################################################

section "STRACE SAMPLE OF GNOME SHELL"

if [ -n "$GNOME_PID" ]; then

    echo
    echo "IMPORTANT:"
    echo "A short strace is being taken."
    echo "GNOME Shell may briefly consume additional CPU."
    echo "No files are modified."

    STRACE_FILE="$OUTDIR/gnome-shell-strace.txt"

    timeout 12s strace \
        -f \
        -tt \
        -T \
        -p "$GNOME_PID" \
        -e trace=write,writev,sendmsg,recvmsg,read,openat,close,ioctl \
        -o "$STRACE_FILE" 2>&1 || true

    echo
    echo "Strace saved to:"
    echo "$STRACE_FILE"

    echo
    echo "Strace lines mentioning likely diagnostics:"
    grep -Ei \
        'g_closure|GLib|GObject|gnome-shell|assert|critical|warning' \
        "$STRACE_FILE" 2>/dev/null | tail -n 100

fi

###############################################################################
# GDB BACKTRACE
###############################################################################

section "GDB BACKTRACE OF GNOME SHELL"

if [ -n "$GNOME_PID" ]; then

    if command -v gdb >/dev/null 2>&1; then

        echo "Attempting a non-interactive backtrace."

        GDB_FILE="$OUTDIR/gnome-shell-gdb-backtrace.txt"

        timeout 30s gdb \
            -q \
            -batch \
            -ex "set pagination off" \
            -ex "thread apply all bt 8" \
            -p "$GNOME_PID" \
            > "$GDB_FILE" 2>&1 || true

        echo
        echo "GDB backtrace saved to:"
        echo "$GDB_FILE"

        echo
        echo "Backtrace summary:"
        grep -Ei \
            'g_closure|gobject|glib|gnome|mutter|st_|clutter|gjs|javascript|extension' \
            "$GDB_FILE" | head -n 200

    else
        echo "gdb is not installed."
        echo "Install with:"
        echo "sudo apt install gdb"
    fi
fi

###############################################################################
# GNOME SHELL COREDUMP INFORMATION
###############################################################################

section "GNOME SHELL COREDUMP HISTORY"

run coredumpctl list gnome-shell

###############################################################################
# JOURNAL STATISTICS
###############################################################################

section "GNOME SHELL ERROR STATISTICS"

echo "Last 30 minutes:"

run_shell "journalctl --since '30 minutes ago' -o cat |
grep -Ei 'gnome-shell.*(assertion|critical|warning|error|failed)' |
sed 's/^.*gnome-shell[^:]*: //' |
sort |
uniq -c |
sort -nr |
head -n 50"

###############################################################################
# POSSIBLE EXTENSION REFERENCES IN JOURNAL
###############################################################################

section "GNOME JOURNAL REFERENCES TO EXTENSIONS"

run_shell "journalctl --since '30 minutes ago' -o short-precise |
grep -Ei 'extension|GJS|gjs|workspace|shell' |
head -n 500"

###############################################################################
# SYSTEM JOURNAL AROUND GNOME SHELL
###############################################################################

section "SYSTEM JOURNAL AROUND GNOME SHELL"

run_shell "journalctl --since '10 minutes ago' -o short-precise |
grep -Ei 'gnome-shell|mutter|gjs|clutter|glib|gobject' |
head -n 1000"

###############################################################################
# PACKAGE VERSIONS
###############################################################################

section "GNOME / MUTTER / GLIB PACKAGES"

run_shell "dpkg-query -W -f='\${Package}\t\${Version}\n' |
grep -Ei 'gnome-shell|mutter|libglib2.0|libgobject|libgtk|libclutter'"

###############################################################################
# FINAL SUMMARY
###############################################################################

section "DIAGNOSTIC SUMMARY"

echo "GNOME Shell PID : ${GNOME_PID:-NOT FOUND}"
echo "GNOME User      : ${GNOME_USER:-NOT FOUND}"
echo "GNOME UID       : ${GNOME_UID:-NOT FOUND}"
echo "DISPLAY         : ${X11_DISPLAY:-NOT FOUND}"
echo "XAUTHORITY      : ${X11_AUTH:-NOT FOUND}"

echo
echo "Output directory:"
echo "$OUTDIR"

echo
echo "Main log:"
echo "$MAINLOG"

echo
echo "Files produced:"
find "$OUTDIR" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | sort

echo
echo "======================================================================"
echo "GNOME CLOSURE DIAGNOSTIC COMPLETE"
echo "======================================================================"

exit 0
