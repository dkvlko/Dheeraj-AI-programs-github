#!/bin/bash

# ============================================================
# NVIDIA Driver / Display Diagnostic Monitor
# Ubuntu 24.04 Noble
#
# Runs once, records diagnostics, then sleeps 5 minutes.
# Intended to be launched by systemd before graphical login.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/nvidia-driver-monitor-log.txt"

INTERVAL=300   # 5 minutes

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

log_section()
{
    echo
    echo "================================================================"
    echo "$1"
    echo "================================================================"
}

log_command()
{
    echo
    echo "+ $*"
    "$@" 2>&1 || echo "[command exited with status $?: $*]"
}

# ------------------------------------------------------------
# Main monitoring loop
# ------------------------------------------------------------

while true
do

    TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S %Z')"

    {
        echo
        echo
        echo "################################################################"
        echo "# NVIDIA DRIVER DIAGNOSTIC SNAPSHOT"
        echo "# $TIMESTAMP"
        echo "################################################################"

        # --------------------------------------------------------
        # System information
        # --------------------------------------------------------

        log_section "SYSTEM INFORMATION"

        echo "Hostname:"
        hostname

        echo
        echo "Kernel:"
        uname -a

        echo
        echo "Uptime:"
        uptime

        echo
        echo "Current boot:"
        who -b

        # --------------------------------------------------------
        # NVIDIA driver basic information
        # --------------------------------------------------------

        log_section "NVIDIA-SMI BASIC INFORMATION"

        if command -v nvidia-smi >/dev/null 2>&1
        then
            log_command nvidia-smi
        else
            echo "ERROR: nvidia-smi command not found"
        fi

        # --------------------------------------------------------
        # Display-specific NVIDIA information
        # --------------------------------------------------------

        log_section "NVIDIA DISPLAY INFORMATION"

        if command -v nvidia-smi >/dev/null 2>&1
        then

            echo "Display-related query:"
            nvidia-smi \
                --query-gpu=index,name,driver_version,display_mode,display_active \
                --format=csv 2>&1

            echo
            echo "Full NVIDIA display information:"
            nvidia-smi -q -d DISPLAY 2>&1 || true

        else
            echo "nvidia-smi unavailable"
        fi

        # --------------------------------------------------------
        # GPU health / utilization
        # --------------------------------------------------------

        log_section "GPU HEALTH / UTILIZATION"

        if command -v nvidia-smi >/dev/null 2>&1
        then
            nvidia-smi \
                --query-gpu=index,name,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free,pstate,clocks.gr,clocks.sm,clocks.mem,power.draw \
                --format=csv 2>&1
        else
            echo "nvidia-smi unavailable"
        fi

        # --------------------------------------------------------
        # NVIDIA complete query
        # --------------------------------------------------------

        log_section "NVIDIA-SMI COMPLETE QUERY"

        if command -v nvidia-smi >/dev/null 2>&1
        then
            nvidia-smi -q 2>&1
        else
            echo "nvidia-smi unavailable"
        fi

        # --------------------------------------------------------
        # NVIDIA processes
        # --------------------------------------------------------

        log_section "NVIDIA PROCESSES"

        if command -v nvidia-smi >/dev/null 2>&1
        then
            nvidia-smi --query-compute-apps=pid,process_name,used_memory \
                --format=csv 2>&1 || true

            echo
            echo "Processes using /dev/nvidia*:"
            lsof /dev/nvidia* 2>&1 || true
        fi

        # --------------------------------------------------------
        # NVIDIA kernel modules
        # --------------------------------------------------------

        log_section "NVIDIA KERNEL MODULES"

        lsmod | grep -i nvidia || echo "No NVIDIA modules reported by lsmod"

        echo
        echo "modinfo nvidia:"
        modinfo nvidia 2>&1 || true

        # --------------------------------------------------------
        # NVIDIA DRM
        # --------------------------------------------------------

        log_section "NVIDIA DRM INFORMATION"

        echo "DRM devices:"
        ls -l /sys/class/drm/ 2>&1

        echo
        echo "DRM device status:"
        for card in /sys/class/drm/card*/status
        do
            if [ -f "$card" ]
            then
                echo
                echo "$card:"
                cat "$card" 2>&1
            fi
        done

        echo
        echo "DRM connectors:"
        for connector in /sys/class/drm/card*-*/status
        do
            if [ -f "$connector" ]
            then
                echo "$connector = $(cat "$connector" 2>/dev/null)"
            fi
        done

    # ------------------------------------------------------------
    # X11 SESSION INFORMATION
    # ------------------------------------------------------------

    log_section "X11 SESSION INFORMATION"

    X11_USER=""
    X11_UID=""
    X11_DISPLAY=""
    X11_XAUTHORITY=""
    GNOME_PID=""

    # Find GNOME Shell process.
    GNOME_PID=$(pgrep -xo gnome-shell 2>/dev/null || true)

    echo "GNOME Shell PID: ${GNOME_PID:-NOT FOUND}"

    if [ -n "$GNOME_PID" ]; then

        # Determine owner of GNOME Shell.
        X11_USER=$(ps -o user= -p "$GNOME_PID" 2>/dev/null | xargs)
        X11_UID=$(ps -o uid= -p "$GNOME_PID" 2>/dev/null | xargs)

        echo "GNOME Shell user: ${X11_USER:-UNKNOWN}"
        echo "GNOME Shell UID : ${X11_UID:-UNKNOWN}"

        # Extract environment from GNOME Shell.
        if [ -r "/proc/$GNOME_PID/environ" ]; then

            GNOME_ENV=$(tr '\0' '\n' < "/proc/$GNOME_PID/environ")

            X11_DISPLAY=$(echo "$GNOME_ENV" |
                grep '^DISPLAY=' |
                head -1 |
                cut -d= -f2-)

            X11_XAUTHORITY=$(echo "$GNOME_ENV" |
                grep '^XAUTHORITY=' |
                head -1 |
                cut -d= -f2-)

            echo "DISPLAY from GNOME Shell:"
            echo "${X11_DISPLAY:-NOT SET}"

            echo
            echo "XAUTHORITY from GNOME Shell:"
            echo "${X11_XAUTHORITY:-NOT SET}"

            echo
            echo "XDG_SESSION_TYPE:"
            echo "$GNOME_ENV" |
                grep '^XDG_SESSION_TYPE=' |
                cut -d= -f2-

            echo
            echo "WAYLAND_DISPLAY:"
            echo "$GNOME_ENV" |
                grep '^WAYLAND_DISPLAY=' |
                cut -d= -f2-

            echo
            echo "XDG_CURRENT_DESKTOP:"
            echo "$GNOME_ENV" |
                grep '^XDG_CURRENT_DESKTOP=' |
                cut -d= -f2-

        fi
    fi


# ------------------------------------------------------------
# X11 COMMANDS
# ------------------------------------------------------------

if [ -n "$X11_DISPLAY" ] && [ -n "$X11_USER" ]; then

    echo
    echo "X11 session detected."
    echo "Running X11 queries as user: $X11_USER"
    echo "DISPLAY: $X11_DISPLAY"

    # Use XAUTHORITY if GNOME Shell supplied one.
    if [ -n "$X11_XAUTHORITY" ]; then
        X11_ENV=(
            "DISPLAY=$X11_DISPLAY"
            "XAUTHORITY=$X11_XAUTHORITY"
        )
    else
        X11_ENV=(
            "DISPLAY=$X11_DISPLAY"
        )
    fi

    # --------------------------------------------------------
    # xrandr
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "xrandr --query"
    echo "------------------------------------------------------------"

    sudo -u "$X11_USER" \
        env "${X11_ENV[@]}" \
        xrandr --query 2>&1 || true


    echo
    echo "------------------------------------------------------------"
    echo "xrandr --listproviders"
    echo "------------------------------------------------------------"

    sudo -u "$X11_USER" \
        env "${X11_ENV[@]}" \
        xrandr --listproviders 2>&1 || true


    echo
    echo "------------------------------------------------------------"
    echo "xrandr --verbose"
    echo "------------------------------------------------------------"

    sudo -u "$X11_USER" \
        env "${X11_ENV[@]}" \
        xrandr --verbose 2>&1 || true


    # --------------------------------------------------------
    # xdpyinfo
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "xdpyinfo"
    echo "------------------------------------------------------------"

    if command -v xdpyinfo >/dev/null 2>&1; then
        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            xdpyinfo 2>&1 || true
    else
        echo "xdpyinfo is not installed."
    fi


    # --------------------------------------------------------
    # X11 root window properties
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "xprop -root"
    echo "------------------------------------------------------------"

    if command -v xprop >/dev/null 2>&1; then
        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            xprop -root 2>&1 || true
    else
        echo "xprop is not installed."
    fi


    # --------------------------------------------------------
    # Active window
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "Active X11 Window"
    echo "------------------------------------------------------------"

    sudo -u "$X11_USER" \
        env "${X11_ENV[@]}" \
        xprop -root _NET_ACTIVE_WINDOW 2>&1 || true


    # --------------------------------------------------------
    # X11 screen information
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "X11 Screen Information"
    echo "------------------------------------------------------------"

    sudo -u "$X11_USER" \
        env "${X11_ENV[@]}" \
        xdpyinfo 2>/dev/null |
        grep -E \
        'name of display|version number|vendor string|vendor release|dimensions|resolution|depth of root window' \
        || true


    # --------------------------------------------------------
    # X11 DPMS
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "X11 DPMS"
    echo "------------------------------------------------------------"

    if command -v xset >/dev/null 2>&1; then
        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            xset q 2>&1 || true
    fi


    # --------------------------------------------------------
    # X11 input devices
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "X11 Input Devices"
    echo "------------------------------------------------------------"

    if command -v xinput >/dev/null 2>&1; then
        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            xinput list 2>&1 || true
    fi


    # --------------------------------------------------------
    # OpenGL / GLX
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "OpenGL / GLX"
    echo "------------------------------------------------------------"

    if command -v glxinfo >/dev/null 2>&1; then

        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            glxinfo -B 2>&1 || true

    else
        echo "glxinfo is not installed."
    fi


    # --------------------------------------------------------
    # NVIDIA X11 extensions
    # --------------------------------------------------------

    echo
    echo "------------------------------------------------------------"
    echo "NVIDIA X11 GLX Extensions"
    echo "------------------------------------------------------------"

    if command -v glxinfo >/dev/null 2>&1; then

        sudo -u "$X11_USER" \
            env "${X11_ENV[@]}" \
            glxinfo -extensions 2>&1 |
            grep -Ei 'GLX|NVIDIA|NV-' ||
            true

    fi

else

    echo
    echo "No active X11 GNOME Shell session detected."
    echo "X11 queries skipped."

fi

        # --------------------------------------------------------
        # NVIDIA PCI information
        # --------------------------------------------------------

        log_section "NVIDIA PCI INFORMATION"

        lspci -nnk | grep -A5 -B2 -Ei 'NVIDIA|VGA|3D|Display' 2>&1 || true

        # --------------------------------------------------------
        # Kernel NVIDIA / DRM messages - last 5 minutes
        # --------------------------------------------------------

        log_section "JOURNALCTL NVIDIA / DRM / GPU MESSAGES - LAST 5 MINUTES"

        journalctl \
            --since "5 minutes ago" \
            --no-pager \
            -o short-precise \
            2>/dev/null |
            grep -Ei \
            'nvrm|nvidia|xid|drm|gpu|nouveau|modeset|display|hdmi|dp-|displayport|edid|mutter|gnome-shell' \
            || echo "No matching NVIDIA/display messages in the last 5 minutes."

        # --------------------------------------------------------
        # NVIDIA-specific journal messages
        # --------------------------------------------------------

        log_section "JOURNALCTL NVIDIA / NVRM / XID - LAST 5 MINUTES"

        journalctl \
            --since "5 minutes ago" \
            --no-pager \
            -o short-precise \
            2>/dev/null |
            grep -Ei 'nvrm|nvidia|xid' \
            || echo "No NVIDIA/NVRM/Xid messages in the last 5 minutes."

        # --------------------------------------------------------
        # Kernel messages
        # --------------------------------------------------------

        log_section "KERNEL MESSAGES - LAST 5 MINUTES"

        journalctl \
            -k \
            --since "5 minutes ago" \
            --no-pager \
            -o short-precise \
            2>/dev/null |
            grep -Ei \
            'nvrm|nvidia|xid|drm|gpu|nouveau|modeset|display|hdmi|dp-|displayport|edid' \
            || echo "No matching kernel GPU/display messages."

        # --------------------------------------------------------
        # NVIDIA device files
        # --------------------------------------------------------

        log_section "NVIDIA DEVICE FILES"

        ls -l /dev/nvidia* 2>&1 || true

        # --------------------------------------------------------
        # End of snapshot
        # --------------------------------------------------------

        echo
        echo "################################################################"
        echo "# END OF SNAPSHOT"
        echo "# $TIMESTAMP"
        echo "################################################################"

    } >> "$LOG_FILE" 2>&1

    # ------------------------------------------------------------
    # Prevent the log from becoming enormous.
    #
    # Keep approximately the last 10 MB.
    # ------------------------------------------------------------

    if [ -f "$LOG_FILE" ]
    then
        FILE_SIZE=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)

        if [ "$FILE_SIZE" -gt 10485760 ]
        then
            tail -c 5242880 "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi

    sleep "$INTERVAL"

done
