#!/usr/bin/env bash

# ============================================================
# GUI / X11 / NVIDIA Freeze Monitor
# Ubuntu 24.04 / GNOME / X11
#
# Creates:
#   ~/gui_freeze_monitor/
#
# A reference snapshot is taken at startup.
# Every 60 seconds the GUI is tested.
# A diagnostic snapshot is taken whenever the GUI test fails.
# ============================================================

set -u

BASE_DIR="$HOME/gui_freeze_monitor"
mkdir -p "$BASE_DIR"

START_TIME="$(date '+%Y-%m-%d_%H-%M-%S')"
REFERENCE_DIR="$BASE_DIR/reference_$START_TIME"

mkdir -p "$REFERENCE_DIR"

LOG_FILE="$BASE_DIR/monitor.log"

# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

timestamp()
{
    date '+%Y-%m-%d %H:%M:%S %Z'
}

run_cmd()
{
    local outfile="$1"
    shift

    {
        echo "============================================================"
        echo "Command: $*"
        echo "Time: $(timestamp)"
        echo "============================================================"
        timeout 10s "$@"
        local rc=$?
        echo
        echo "Exit status: $rc"
    } > "$outfile" 2>&1
}

log()
{
    echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"
}

# ------------------------------------------------------------
# Complete diagnostic snapshot
# ------------------------------------------------------------

take_snapshot()
{
    local DIR="$1"
    local REASON="$2"

    mkdir -p "$DIR"

    echo "$REASON" > "$DIR/REASON.txt"
    timestamp > "$DIR/TIMESTAMP.txt"

    # Basic system/session information
    date '+%Y-%m-%d %H:%M:%S %Z' > "$DIR/date.txt"
    uptime > "$DIR/uptime.txt"
    uname -a > "$DIR/uname.txt"
    who > "$DIR/who.txt"
    loginctl session-status > "$DIR/loginctl-session-status.txt" 2>&1

    # Environment relevant to X11/GUI
    {
        echo "DISPLAY=$DISPLAY"
        echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY-}"
        echo "XAUTHORITY=${XAUTHORITY-}"
        echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE-}"
        echo "XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP-}"
        echo "DESKTOP_SESSION=${DESKTOP_SESSION-}"
    } > "$DIR/gui-environment.txt"

    # --------------------------------------------------------
    # X11 tests
    # --------------------------------------------------------

    run_cmd "$DIR/xrandr-current.txt" xrandr --current
    run_cmd "$DIR/xrandr-providers.txt" xrandr --listproviders
    run_cmd "$DIR/xrandr-query.txt" xrandr --query
    run_cmd "$DIR/xdpyinfo.txt" xdpyinfo
    run_cmd "$DIR/xset-q.txt" xset -q
    run_cmd "$DIR/xprop-root.txt" xprop -root

    # --------------------------------------------------------
    # NVIDIA
    # --------------------------------------------------------

    run_cmd "$DIR/nvidia-smi.txt" nvidia-smi
    run_cmd "$DIR/nvidia-settings-current-metamode.txt" \
        nvidia-settings -q CurrentMetaMode

    run_cmd "$DIR/nvidia-settings-gpus.txt" \
        nvidia-settings -q gpus

    run_cmd "$DIR/nvidia-settings-dpys.txt" \
        nvidia-settings -q dpys

    run_cmd "$DIR/glxinfo.txt" glxinfo -B

    run_cmd "$DIR/prime-select.txt" prime-select query

    run_cmd "$DIR/lspci-gpu.txt" \
        lspci -nnk

    # --------------------------------------------------------
    # NVIDIA / X11 configuration
    # --------------------------------------------------------

    {
        echo "===== /usr/share/X11/xorg.conf.d/10-nvidia.conf ====="
        cat /usr/share/X11/xorg.conf.d/10-nvidia.conf 2>&1

        echo
        echo "===== /usr/share/X11/xorg.conf.d/11-nvidia-prime.conf ====="
        cat /usr/share/X11/xorg.conf.d/11-nvidia-prime.conf 2>&1

        echo
        echo "===== /etc/X11/xorg.conf ====="
        cat /etc/X11/xorg.conf 2>&1 || true

        echo
        echo "===== /etc/X11/xorg.conf.d ====="
        ls -la /etc/X11/xorg.conf.d/ 2>&1

        echo
        echo "===== 90-touchpad.conf ====="
        cat /etc/X11/xorg.conf.d/90-touchpad.conf 2>&1 || true
    } > "$DIR/xorg-nvidia-configuration.txt"

    # GNOME monitor configuration
    cp "$HOME/.config/monitors.xml" \
       "$DIR/monitors.xml" 2>/dev/null || true

    # NVIDIA user configuration
    cp "$HOME/.nvidia-settings-rc" \
       "$DIR/nvidia-settings-rc" 2>/dev/null || true

    # --------------------------------------------------------
    # Processes related to GUI
    # --------------------------------------------------------

    {
        echo "===== GNOME / X / NVIDIA processes ====="
        ps -eo user,pid,ppid,stat,pcpu,pmem,etime,args --sort=-pcpu |
            grep -Ei 'gnome-shell|Xorg|gdm|nvidia|mutter|Xwayland|gnome-session|modesetting' |
            grep -v grep

        echo
        echo "===== Top CPU processes ====="
        ps -eo user,pid,ppid,stat,pcpu,pmem,etime,args --sort=-pcpu | head -40

        echo
        echo "===== NVIDIA processes ====="
        pgrep -a nvidia || true
    } > "$DIR/gui-processes.txt"

    # --------------------------------------------------------
    # Kernel / NVIDIA kernel state
    # --------------------------------------------------------

    lsmod | grep -Ei 'nvidia|nouveau|i915' > "$DIR/gpu-modules.txt"

    {
        echo "===== NVIDIA kernel messages ====="
        journalctl -k --no-pager --since "-10 minutes" |
            grep -Ei 'nvidia|NVRM|drm|i915|gpu|xid' || true

        echo
        echo "===== Kernel errors/warnings ====="
        journalctl -k -p warning..alert --no-pager --since "-10 minutes"
    } > "$DIR/kernel-gpu-journal.txt"

    # --------------------------------------------------------
    # User GUI journal
    # --------------------------------------------------------

    {
        echo "===== User journal - last 10 minutes ====="
        journalctl --user --no-pager --since "-10 minutes"

        echo
        echo "===== GNOME / X / NVIDIA / Tracker warnings ====="
        journalctl --user --no-pager --since "-10 minutes" |
            grep -Ei \
            'gnome|mutter|Xorg|nvidia|tracker|nautilus|display|xrandr|gpu|drm|freeze|hang|error|warning' \
            || true
    } > "$DIR/user-gui-journal.txt"

    # System journal relevant to GUI
    journalctl --no-pager --since "-10 minutes" |
        grep -Ei \
        'gdm|Xorg|nvidia|NVRM|drm|i915|gnome|mutter|gpu|display' \
        > "$DIR/system-gui-journal.txt" 2>&1 || true

    # --------------------------------------------------------
    # GPU / DRM information
    # --------------------------------------------------------

    {
        echo "===== DRM devices ====="
        ls -la /dev/dri/

        echo
        echo "===== DRM sysfs ====="
        for x in /sys/class/drm/*/status; do
            echo "--- $x ---"
            cat "$x" 2>/dev/null || true
        done

        echo
        echo "===== DRM connector modes ====="
        for x in /sys/class/drm/*/modes; do
            echo "--- $x ---"
            cat "$x" 2>/dev/null || true
        done
    } > "$DIR/drm-state.txt"

    log "Diagnostic snapshot created: $DIR"
}

# ------------------------------------------------------------
# GUI health check
# ------------------------------------------------------------

gui_health_check()
{
    local TMP
    TMP="$(mktemp -d)"

    # X11 connection test
    if ! timeout 5s xdpyinfo >/dev/null 2>&1; then
        echo "X11 connection failed"
        rm -rf "$TMP"
        return 1
    fi

    # Xrandr test
    if ! timeout 5s xrandr --current > "$TMP/xrandr" 2>&1; then
        echo "xrandr failed"
        rm -rf "$TMP"
        return 1
    fi

    # We expect these two physical outputs in your present setup.
    if ! grep -q '^eDP-1-1 connected' "$TMP/xrandr"; then
        echo "eDP-1-1 disappeared"
        rm -rf "$TMP"
        return 1
    fi

    if ! grep -q '^HDMI-1-1 connected' "$TMP/xrandr"; then
        echo "HDMI-1-1 disappeared"
        rm -rf "$TMP"
        return 1
    fi

    # Provider test
    if ! timeout 5s xrandr --listproviders > "$TMP/providers" 2>&1; then
        echo "xrandr provider query failed"
        rm -rf "$TMP"
        return 1
    fi

    # Check that both GPUs/providers are still visible.
    if ! grep -q 'NVIDIA-0' "$TMP/providers"; then
        echo "NVIDIA provider disappeared"
        rm -rf "$TMP"
        return 1
    fi

    if ! grep -q 'modesetting' "$TMP/providers"; then
        echo "modesetting provider disappeared"
        rm -rf "$TMP"
        return 1
    fi

    rm -rf "$TMP"
    return 0
}

# ------------------------------------------------------------
# Initial reference snapshot
# ------------------------------------------------------------

log "============================================================"
log "GUI FREEZE MONITOR STARTING"
log "Reference snapshot: $REFERENCE_DIR"
log "============================================================"

take_snapshot "$REFERENCE_DIR" \
    "REFERENCE SNAPSHOT - GUI state when monitor started"

# ------------------------------------------------------------
# Main monitoring loop
# ------------------------------------------------------------

FAILURES=0
CHECK_NUMBER=0

while true
do
    CHECK_NUMBER=$((CHECK_NUMBER + 1))

    if REASON="$(gui_health_check 2>&1)"; then
        FAILURES=0
        log "GUI check #$CHECK_NUMBER: OK"
    else
        FAILURES=$((FAILURES + 1))

        log "GUI check #$CHECK_NUMBER: FAILED"
        log "Reason: $REASON"

        # Require two consecutive failures to avoid dumping
        # because of a momentary X11 query failure.
        if [ "$FAILURES" -ge 2 ]; then

            EVENT_TIME="$(date '+%Y-%m-%d_%H-%M-%S')"
            EVENT_DIR="$BASE_DIR/FREEZE_$EVENT_TIME"

            log "GUI appears unhealthy for two consecutive checks."
            log "Taking diagnostic snapshot..."

            take_snapshot "$EVENT_DIR" \
                "GUI FAILURE detected at $(timestamp)
Reason:
$REASON

This was the second consecutive failed GUI health check."

            FAILURES=0
        fi
    fi

    sleep 60
done
