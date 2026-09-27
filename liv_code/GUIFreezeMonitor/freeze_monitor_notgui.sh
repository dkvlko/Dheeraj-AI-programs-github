#!/usr/bin/env bash

# ============================================================
# Linux System Performance / Freeze Monitor
# Ubuntu 24.04 LTS / Noble
#
# Purpose:
#   Detect and record CPU, memory, swap, I/O, D-state processes,
#   disk/USB problems, NVIDIA/GPU state, systemd failures,
#   user services, kernel warnings and other conditions that
#   can make terminals/applications appear "clogged".
#
# Logs are stored in the SAME DIRECTORY as this script.
#
# Run:
#   chmod +x linux_system_monitor.sh
#   ./linux_system_monitor.sh
#
# Stop:
#   Ctrl+C
#
# Recommended:
#   Run from a terminal before doing normal work.
# ============================================================

set -u
set -o pipefail

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/system_monitor_logs"

INTERVAL=60

# Number of lines retained in continuously sampled process lists
TOP_N=30

# Number of lines retained for journal snapshots
JOURNAL_LINES=200

# ------------------------------------------------------------
# Files
# ------------------------------------------------------------

START_TIME="$(date '+%Y-%m-%d_%H-%M-%S')"

LOG_FILE="$LOG_DIR/system_monitor_${START_TIME}.log"
EVENT_LOG="$LOG_DIR/events_${START_TIME}.log"
PROCESS_LOG="$LOG_DIR/processes_${START_TIME}.log"
IO_LOG="$LOG_DIR/io_${START_TIME}.log"
MEMORY_LOG="$LOG_DIR/memory_${START_TIME}.log"
KERNEL_LOG="$LOG_DIR/kernel_${START_TIME}.log"

LATEST_LINK="$LOG_DIR/latest"

mkdir -p "$LOG_DIR"

# ------------------------------------------------------------
# Privilege handling
# ------------------------------------------------------------

if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

timestamp()
{
    date '+%Y-%m-%d %H:%M:%S %z'
}

log()
{
    local msg="$1"

    printf '[%s] %s\n' "$(timestamp)" "$msg" | tee -a "$LOG_FILE"
}

event()
{
    local msg="$1"

    printf '[%s] EVENT: %s\n' "$(timestamp)" "$msg" \
        | tee -a "$LOG_FILE" "$EVENT_LOG"
}

section()
{
    local title="$1"

    {
        echo
        echo
        echo "================================================================"
        echo "$title"
        echo "================================================================"
        echo "TIME: $(timestamp)"
    } >> "$LOG_FILE"
}

command_exists()
{
    command -v "$1" >/dev/null 2>&1
}

run()
{
    "$@" 2>&1
}

# ------------------------------------------------------------
# Latest log symlink
# ------------------------------------------------------------

ln -sfn "$(basename "$LOG_FILE")" "$LATEST_LINK"

# ------------------------------------------------------------
# Header
# ------------------------------------------------------------

log "=============================================================="
log "Linux System Performance Monitor"
log "=============================================================="
log "Script directory : $SCRIPT_DIR"
log "Log directory    : $LOG_DIR"
log "Main log         : $LOG_FILE"
log "Interval         : ${INTERVAL}s"
log "Hostname         : $(hostname)"
log "Kernel           : $(uname -a)"
log "Started          : $(timestamp)"
log "=============================================================="

# ------------------------------------------------------------
# Initial system information
# ------------------------------------------------------------

section "SYSTEM INFORMATION"

{
    echo "DATE:"
    date

    echo
    echo "UPTIME:"
    uptime

    echo
    echo "KERNEL:"
    uname -a

    echo
    echo "OS:"
    cat /etc/os-release

    echo
    echo "CPU:"
    lscpu

    echo
    echo "MEMORY:"
    free -h

    echo
    echo "BLOCK DEVICES:"
    lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS

    echo
    echo "FILESYSTEMS:"
    df -hT

    echo
    echo "MOUNTS:"
    mount

    echo
    echo "PCI DEVICES:"
    lspci -nnk

    echo
    echo "USB DEVICES:"
    lsusb

    echo
    echo "NETWORK:"
    ip addr

    echo
    ip route

    echo
    echo "SYSTEMD FAILED UNITS:"
    systemctl --failed --no-pager

    echo
    echo "USER SYSTEMD FAILED UNITS:"
    systemctl --user --failed --no-pager 2>&1

} >> "$LOG_FILE" 2>&1

# ------------------------------------------------------------
# NVIDIA initial state
# ------------------------------------------------------------

section "NVIDIA INITIAL STATE"

{
    echo "nvidia-smi:"
    if command_exists nvidia-smi; then
        nvidia-smi
    else
        echo "nvidia-smi not available"
    fi

    echo
    echo "NVIDIA MODULE:"
    lsmod | grep -i nvidia || true

    echo
    echo "NVIDIA DRIVER:"
    modinfo nvidia 2>/dev/null | grep -E \
        '^(filename|version|license|srcversion):' || true

    echo
    echo "PRIME:"
    if command_exists prime-select; then
        prime-select query
    fi

    echo
    echo "DRM DEVICES:"
    ls -l /dev/dri 2>/dev/null || true

} >> "$LOG_FILE" 2>&1

# ------------------------------------------------------------
# Continuous journal baseline
# ------------------------------------------------------------

LAST_JOURNAL_TIME="$(date --iso-8601=seconds)"

# ------------------------------------------------------------
# Counters
# ------------------------------------------------------------

CHECK=0
LAST_D_STATE_COUNT=0
LAST_SWAP_IN=0
LAST_SWAP_OUT=0
LAST_IOWAIT=0

# ------------------------------------------------------------
# Trap
# ------------------------------------------------------------

cleanup()
{
    log "Monitor stopped by user."

    section "FINAL SYSTEM STATE"

    {
        echo "UPTIME:"
        uptime

        echo
        echo "MEMORY:"
        free -h

        echo
        echo "SYSTEMD FAILED:"
        systemctl --failed --no-pager

        echo
        echo "USER SYSTEMD FAILED:"
        systemctl --user --failed --no-pager 2>&1

        echo
        echo "D-STATE PROCESSES:"
        ps -eo pid,ppid,user,stat,wchan:40,%cpu,%mem,etime,comm,args \
            | awk '$4 ~ /^D/ || NR==1'

        echo
        echo "NVIDIA:"
        nvidia-smi 2>&1 || true

    } >> "$LOG_FILE" 2>&1

    log "Log directory: $LOG_DIR"
    log "Main log: $LOG_FILE"

    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================================
# MAIN LOOP
# ============================================================

while true
do

    CHECK=$((CHECK + 1))

    NOW="$(timestamp)"

    # --------------------------------------------------------
    # Basic system statistics
    # --------------------------------------------------------

    UPTIME_SECONDS="$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)"

    LOAD="$(cat /proc/loadavg 2>/dev/null || echo unknown)"

    MEMORY_LINE="$(free -m | awk '/^Mem:/ {
        printf "total=%sMB used=%sMB free=%sMB available=%sMB",
        $2,$3,$4,$7
    }')"

    SWAP_LINE="$(free -m | awk '/^Swap:/ {
        printf "total=%sMB used=%sMB free=%sMB",
        $2,$3,$4
    }')"

    # --------------------------------------------------------
    # CPU statistics
    # --------------------------------------------------------

    CPU_LINE="$(awk '/^cpu / {
        total=$2+$3+$4+$5+$6+$7+$8+$9+$10
        idle=$5+$6
        printf "user=%s system=%s idle=%s iowait=%s irq=%s softirq=%s steal=%s total=%s",
        $2,$4,idle,$6,$7,$8,$9,total
    }' /proc/stat)"

    IOWAIT="$(awk '/^cpu / {
        total=$2+$3+$4+$5+$6+$7+$8+$9+$10
        if(total>0)
            printf "%.2f", (($6)/total)*100
    }' /proc/stat)"

    # --------------------------------------------------------
    # Process counts
    # --------------------------------------------------------

    RUNNING="$(ps -eo stat= | grep -c '^R' || true)"
    SLEEPING="$(ps -eo stat= | grep -c '^S' || true)"
    DSTATE="$(ps -eo stat= | grep -c '^D' || true)"
    ZOMBIE="$(ps -eo stat= | grep -c '^Z' || true)"

    # --------------------------------------------------------
    # Write basic sample
    # --------------------------------------------------------

    printf '%s CHECK=%s LOAD="%s" CPU_IOWAIT=%s%% MEM="%s" SWAP="%s" RUN=%s SLEEP=%s D=%s ZOMBIE=%s\n' \
        "$NOW" \
        "$CHECK" \
        "$LOAD" \
        "$IOWAIT" \
        "$MEMORY_LINE" \
        "$SWAP_LINE" \
        "$RUNNING" \
        "$SLEEPING" \
        "$DSTATE" \
        "$ZOMBIE" \
        >> "$LOG_FILE"

    # --------------------------------------------------------
    # Record memory statistics
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] CHECK=$CHECK"

        free -h

        echo
        echo "/proc/meminfo:"
        cat /proc/meminfo

        echo
        echo "VMSTAT:"
        vmstat 1 2
    } >> "$MEMORY_LOG" 2>&1

    # --------------------------------------------------------
    # CPU / process information
    # --------------------------------------------------------

    {
        echo
        echo "=============================================================="
        echo "$NOW CHECK=$CHECK"
        echo "=============================================================="

        echo
        echo "LOAD:"
        cat /proc/loadavg

        echo
        echo "TOP CPU PROCESSES:"
        ps -eo pid,ppid,user,stat,psr,%cpu,%mem,etime,wchan:30,comm,args \
            --sort=-%cpu | head -n "$((TOP_N + 1))"

        echo
        echo "TOP MEMORY PROCESSES:"
        ps -eo pid,ppid,user,stat,psr,%cpu,%mem,rss,vsz,etime,wchan:30,comm,args \
            --sort=-%mem | head -n "$((TOP_N + 1))"

        echo
        echo "ALL D-STATE PROCESSES:"
        ps -eo pid,ppid,user,stat,psr,%cpu,%mem,etime,wchan:40,comm,args \
            | awk '$4 ~ /^D/ || NR==1'

        echo
        echo "ZOMBIES:"
        ps -eo pid,ppid,user,stat,comm,args \
            | awk '$4 ~ /^Z/ || NR==1'

    } >> "$PROCESS_LOG" 2>&1

    # --------------------------------------------------------
    # Disk / I/O information
    # --------------------------------------------------------

    {
        echo
        echo "=============================================================="
        echo "$NOW CHECK=$CHECK"
        echo "=============================================================="

        echo
        echo "VMSTAT:"
        vmstat 1 2

        echo
        echo "DISK STATISTICS:"
        cat /proc/diskstats

        echo
        echo "MOUNTED FILESYSTEMS:"
        df -hT

        echo
        echo "BLOCK DEVICES:"
        lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS

        echo
        echo "PROCESS I/O:"
        if command_exists pidstat; then
            pidstat -d 1 1
        fi

        echo
        echo "IOSTAT:"
        if command_exists iostat; then
            iostat -xz 1 1
        fi

    } >> "$IO_LOG" 2>&1

    # --------------------------------------------------------
    # Detect D-state processes
    # --------------------------------------------------------

    if (( DSTATE > 0 )); then

        if (( LAST_D_STATE_COUNT == 0 )); then
            event "D-state process detected: count=$DSTATE"

            ps -eo pid,ppid,user,stat,wchan:40,%cpu,%mem,etime,comm,args \
                | awk '$4 ~ /^D/ || NR==1' \
                >> "$EVENT_LOG" 2>&1
        fi

    elif (( LAST_D_STATE_COUNT > 0 )); then

        event "D-state processes cleared"

    fi

    LAST_D_STATE_COUNT="$DSTATE"

    # --------------------------------------------------------
    # Detect high I/O wait
    # --------------------------------------------------------

    if awk "BEGIN {exit !($IOWAIT >= 20)}"; then

        event "HIGH I/O WAIT detected: ${IOWAIT}%"

        {
            echo "[$NOW]"
            ps -eo pid,ppid,user,stat,wchan:40,%cpu,%mem,etime,comm,args \
                | awk '$4 ~ /^D/ || NR==1'

            echo
            iostat -xz 1 2 2>&1 || true

        } >> "$EVENT_LOG"

    fi

    # --------------------------------------------------------
    # Detect swap activity
    # --------------------------------------------------------

    SWAP_IN="$(awk '/^pswpin / {print $2}' /proc/vmstat 2>/dev/null || echo 0)"
    SWAP_OUT="$(awk '/^pswpout / {print $2}' /proc/vmstat 2>/dev/null || echo 0)"

    if (( CHECK > 1 )); then

        if (( SWAP_IN > LAST_SWAP_IN || SWAP_OUT > LAST_SWAP_OUT )); then

            event "SWAP ACTIVITY detected: pswpin=$SWAP_IN pswpout=$SWAP_OUT"

        fi

    fi

    LAST_SWAP_IN="$SWAP_IN"
    LAST_SWAP_OUT="$SWAP_OUT"

    # --------------------------------------------------------
    # Kernel messages
    # --------------------------------------------------------

    {
        echo
        echo "=============================================================="
        echo "$NOW CHECK=$CHECK"
        echo "=============================================================="

        journalctl -k \
            --since "$LAST_JOURNAL_TIME" \
            --no-pager \
            2>/dev/null

    } >> "$KERNEL_LOG" 2>&1

    LAST_JOURNAL_TIME="$(date --iso-8601=seconds)"

    # --------------------------------------------------------
    # Kernel errors/warnings
    # --------------------------------------------------------

    KERNEL_WARNINGS="$(
        journalctl -k \
            --since "-10 seconds" \
            -p warning..alert \
            --no-pager 2>/dev/null
    )"

    if [[ -n "$KERNEL_WARNINGS" ]]; then

        event "Kernel warning/error detected"

        printf '%s\n' "$KERNEL_WARNINGS" >> "$EVENT_LOG"

    fi

    # --------------------------------------------------------
    # USB state
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW]"
        lsusb
    } >> "$LOG_FILE" 2>&1

    # --------------------------------------------------------
    # NVIDIA/GPU monitoring
    # --------------------------------------------------------

    if command_exists nvidia-smi; then

        {
            echo
            echo "[$NOW] NVIDIA"

            nvidia-smi \
                --query-gpu=timestamp,name,driver_version,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used,memory.free,power.draw,power.limit,clocks.gr \
                --format=csv,noheader

        } >> "$LOG_FILE" 2>&1

    fi

    # --------------------------------------------------------
    # DRM state
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] DRM DEVICES"

        for card in /sys/class/drm/card*-*/status
        do
            [[ -f "$card" ]] || continue

            printf '%s = ' "$card"
            cat "$card"
        done

    } >> "$LOG_FILE" 2>&1

    # --------------------------------------------------------
    # Filesystem usage
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] FILESYSTEM USAGE"

        df -hT

        echo
        echo "INODES"

        df -ih

    } >> "$LOG_FILE" 2>&1

    # --------------------------------------------------------
    # Systemd failures
    # --------------------------------------------------------

    FAILED_SYSTEMD="$(systemctl --failed --no-legend --no-pager 2>/dev/null || true)"

    if [[ -n "$FAILED_SYSTEMD" ]]; then

        event "Systemd failed units detected"

        printf '%s\n' "$FAILED_SYSTEMD" >> "$EVENT_LOG"

    fi

    FAILED_USER_SYSTEMD="$(
        systemctl --user --failed --no-legend --no-pager 2>/dev/null || true
    )"

    if [[ -n "$FAILED_USER_SYSTEMD" ]]; then

        event "User systemd failed units detected"

        printf '%s\n' "$FAILED_USER_SYSTEMD" >> "$EVENT_LOG"

    fi

    # --------------------------------------------------------
    # Network state
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] NETWORK"

        ip -brief addr

        echo
        ip route

        echo
        ss -s

    } >> "$LOG_FILE" 2>&1

    # --------------------------------------------------------
    # File descriptor usage
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] FILE DESCRIPTORS"

        cat /proc/sys/fs/file-nr
        cat /proc/sys/fs/file-max

    } >> "$LOG_FILE" 2>&1

    # --------------------------------------------------------
    # User services
    # --------------------------------------------------------

    {
        echo
        echo "[$NOW] USER SERVICES"

        systemctl --user list-units \
            --type=service \
            --state=running \
            --no-pager \
            2>&1

    } >> "$LOG_FILE"

    # --------------------------------------------------------
    # Important process count
    # --------------------------------------------------------

    if (( DSTATE > 3 )); then
        event "UNUSUALLY MANY D-STATE PROCESSES: $DSTATE"
    fi

    if (( ZOMBIE > 5 )); then
        event "UNUSUALLY MANY ZOMBIE PROCESSES: $ZOMBIE"
    fi

    # --------------------------------------------------------
    # Progress message
    # --------------------------------------------------------

    printf '\r[%s] Check %-8s | Load %-20s | I/O wait %6s%% | D-state %3s | RAM %s      ' \
        "$NOW" \
        "$CHECK" \
        "$LOAD" \
        "$IOWAIT" \
        "$DSTATE" \
        "$MEMORY_LINE"

    sleep "$INTERVAL"

done
