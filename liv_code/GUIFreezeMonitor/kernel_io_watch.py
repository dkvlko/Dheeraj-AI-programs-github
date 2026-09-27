#!/usr/bin/env python3
import os
import re
import time
import subprocess
from collections import deque
from datetime import datetime


# ============================================================
# Kernel I/O Rolling-History Diagnostic Monitor
#
# Designed for long-term investigation of Ubuntu freezes.
#
# Sampling:
#   Every 60 seconds
#
# Rolling history:
#   10 minutes
#
# The program normally keeps information in RAM.
# Disk logging occurs only when a significant/calculated
# symptom is detected.
#
# Run with:
#   sudo python3 ~/kernel_io_watch.py
# ============================================================


INTERVAL = 60
HISTORY_MINUTES = 10
MAX_HISTORY = HISTORY_MINUTES

IOWAIT_SIGNIFICANT = 40.0
IOWAIT_SUSTAINED = 20.0

DISK_UTIL_SIGNIFICANT = 95.0
DISK_AWAIT_SIGNIFICANT = 100.0

SUSTAINED_MINUTES = 3

LOG_DIR = os.path.expanduser("~/kernel_io_watch")
os.makedirs(LOG_DIR, exist_ok=True)

START_TIME = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(
    LOG_DIR,
    f"kernel_io_{START_TIME}.log"
)


# ------------------------------------------------------------
# Rolling history
# ------------------------------------------------------------

history = deque(maxlen=MAX_HISTORY)


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

def log(text=""):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def section(title):
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


# ------------------------------------------------------------
# Command helper
# ------------------------------------------------------------

def run_command(command, timeout=10):

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return result.stdout.strip()

    except Exception as e:
        return f"COMMAND ERROR: {e}"


# ------------------------------------------------------------
# CPU iowait
# ------------------------------------------------------------

def get_iowait():

    def read_cpu():

        with open("/proc/stat", "r") as f:

            for line in f:

                if line.startswith("cpu "):

                    values = line.split()[1:]

                    values = list(map(int, values))

                    # user nice system idle iowait irq softirq steal
                    total = sum(values[:8])
                    iowait = values[4]

                    return total, iowait

        return 0, 0

    total1, wait1 = read_cpu()

    time.sleep(1)

    total2, wait2 = read_cpu()

    total_delta = total2 - total1
    wait_delta = wait2 - wait1

    if total_delta <= 0:
        return 0.0

    return (wait_delta / total_delta) * 100.0


# ------------------------------------------------------------
# iostat /dev/sda
# ------------------------------------------------------------

def get_disk_stats():

    output = run_command(
        "iostat -dxk 1 2",
        timeout=8
    )

    lines = output.splitlines()

    header = None
    data = None

    for i, line in enumerate(lines):

        if line.strip().startswith("Device"):
            header = line.strip()

        if re.match(r"^\s*sda\s+", line):
            data = line.split()

    if not data:
        return {
            "raw": "sda data unavailable",
            "util": 0.0,
            "r_await": 0.0,
            "w_await": 0.0,
            "await": 0.0
        }

    # Find columns dynamically from iostat header.
    try:

        headers = header.split()

        values = dict(zip(headers, data))

        util = float(values.get("%util", 0))
        r_await = float(values.get("r_await", 0))
        w_await = float(values.get("w_await", 0))

        # Overall await if available.
        await_value = float(
            values.get("await",
            max(r_await, w_await))
        )

    except Exception:

        util = 0.0
        r_await = 0.0
        w_await = 0.0
        await_value = 0.0

    return {
        "raw": " ".join(data),
        "util": util,
        "r_await": r_await,
        "w_await": w_await,
        "await": await_value
    }


# ------------------------------------------------------------
# D-state processes
# ------------------------------------------------------------

def get_dstate():

    output = run_command(
        "ps -eo pid=,ppid=,user=,state=,wchan:40=,etime=,args="
    )

    processes = []

    for line in output.splitlines():

        parts = line.strip().split(None, 6)

        if len(parts) < 6:
            continue

        pid = parts[0]
        ppid = parts[1]
        user = parts[2]
        state = parts[3]
        wchan = parts[4]
        etime = parts[5]
        command = parts[6] if len(parts) >= 7 else ""

        if state.startswith("D"):

            processes.append({
                "pid": pid,
                "ppid": ppid,
                "user": user,
                "state": state,
                "wchan": wchan,
                "etime": etime,
                "command": command
            })

    return processes


# ------------------------------------------------------------
# PSI I/O
# ------------------------------------------------------------

def get_psi():

    try:

        with open("/proc/pressure/io", "r") as f:
            return f.read().strip()

    except Exception as e:

        return f"PSI unavailable: {e}"


# ------------------------------------------------------------
# Process I/O
# ------------------------------------------------------------

def get_process_io():

    return run_command(
        "pidstat -d -p ALL 1 1",
        timeout=8
    )


# ------------------------------------------------------------
# Kernel messages
# ------------------------------------------------------------

def get_kernel_messages():

    return run_command(
        "journalctl -k --since '2 minutes ago' "
        "--no-pager -o short-precise",
        timeout=10
    )


# ------------------------------------------------------------
# Storage-related kernel messages
# ------------------------------------------------------------

def get_storage_kernel_messages():

    output = get_kernel_messages()

    lines = []

    patterns = [
        r"ata",
        r"ahci",
        r"sata",
        r"scsi",
        r"\bsda\b",
        r"ext4",
        r"jbd2",
        r"I/O error",
        r"error",
        r"timeout",
        r"reset",
        r"failed",
        r"blk",
        r"buffer"
    ]

    regex = re.compile(
        "|".join(patterns),
        re.IGNORECASE
    )

    for line in output.splitlines():

        if regex.search(line):
            lines.append(line)

    if not lines:
        return "No storage-related kernel messages."

    return "\n".join(lines)


# ------------------------------------------------------------
# Kernel D-state threads
# ------------------------------------------------------------

def get_kernel_dstate():

    output = run_command(
        "ps -eo pid=,ppid=,user=,state=,wchan:40=,etime=,args="
    )

    result = []

    for line in output.splitlines():

        if not re.search(r"\[[^]]+\]", line):
            continue

        parts = line.strip().split(None, 6)

        if len(parts) < 6:
            continue

        state = parts[3]

        if state.startswith("D"):
            result.append(line)

    if not result:
        return "None"

    return "\n".join(result)


# ------------------------------------------------------------
# Calculate statistics
# ------------------------------------------------------------

def calculate_statistics():

    if not history:
        return {}

    iowait = [x["iowait"] for x in history]

    util = [x["util"] for x in history]

    await_values = [x["await"] for x in history]

    dcounts = [x["dcount"] for x in history]

    result = {}

    result["samples"] = len(history)

    result["iowait_avg"] = sum(iowait) / len(iowait)
    result["iowait_max"] = max(iowait)

    result["util_avg"] = sum(util) / len(util)
    result["util_max"] = max(util)

    result["await_avg"] = sum(await_values) / len(await_values)
    result["await_max"] = max(await_values)

    result["dstate_max"] = max(dcounts)

    # --------------------------------------------------------
    # Sustained iowait
    # --------------------------------------------------------

    sustained = 0

    for value in reversed(iowait):

        if value >= IOWAIT_SUSTAINED:
            sustained += 1
        else:
            break

    result["sustained_iowait"] = sustained

    # --------------------------------------------------------
    # Sustained high disk utilization
    # --------------------------------------------------------

    disk_sustained = 0

    for value in reversed(util):

        if value >= DISK_UTIL_SIGNIFICANT:
            disk_sustained += 1
        else:
            break

    result["sustained_disk"] = disk_sustained

    # --------------------------------------------------------
    # Sustained D-state
    # --------------------------------------------------------

    d_sustained = 0

    for value in reversed(dcounts):

        if value > 0:
            d_sustained += 1
        else:
            break

    result["sustained_dstate"] = d_sustained

    # --------------------------------------------------------
    # I/O wait trend
    #
    # Difference between oldest and newest sample.
    # --------------------------------------------------------

    if len(iowait) >= 3:

        result["iowait_change"] = (
            iowait[-1] - iowait[0]
        )

    else:

        result["iowait_change"] = 0.0

    # --------------------------------------------------------
    # Rising trend
    # --------------------------------------------------------

    rising = False

    if len(iowait) >= 4:

        first = iowait[0]
        last = iowait[-1]

        if last - first >= 15:

            rising = True

    result["rising_iowait"] = rising

    return result


# ------------------------------------------------------------
# Determine whether significant
# ------------------------------------------------------------

def detect_event(disk, dstate, stats):

    reasons = []

    immediate = False
    calculated = False

    # --------------------------------------------------------
    # Immediate conditions
    # --------------------------------------------------------

    if current_iowait >= IOWAIT_SIGNIFICANT:

        immediate = True
        reasons.append(
            f"CPU iowait {current_iowait:.2f}% >= "
            f"{IOWAIT_SIGNIFICANT:.0f}%"
        )

    if len(dstate) > 0:

        immediate = True
        reasons.append(
            f"D-state process count = {len(dstate)}"
        )

    if disk["util"] >= DISK_UTIL_SIGNIFICANT:

        immediate = True
        reasons.append(
            f"/dev/sda utilization {disk['util']:.2f}% >= "
            f"{DISK_UTIL_SIGNIFICANT:.0f}%"
        )

    if disk["await"] >= DISK_AWAIT_SIGNIFICANT:

        immediate = True
        reasons.append(
            f"/dev/sda await {disk['await']:.2f} ms >= "
            f"{DISK_AWAIT_SIGNIFICANT:.0f} ms"
        )

    # --------------------------------------------------------
    # Calculated conditions
    # --------------------------------------------------------

    if stats.get("sustained_iowait", 0) >= SUSTAINED_MINUTES:

        calculated = True

        reasons.append(
            f"iowait >= {IOWAIT_SUSTAINED:.0f}% for "
            f"{stats['sustained_iowait']} consecutive minutes"
        )

    if stats.get("sustained_disk", 0) >= SUSTAINED_MINUTES:

        calculated = True

        reasons.append(
            f"/dev/sda utilization >= "
            f"{DISK_UTIL_SIGNIFICANT:.0f}% for "
            f"{stats['sustained_disk']} consecutive minutes"
        )

    if stats.get("sustained_dstate", 0) >= 2:

        calculated = True

        reasons.append(
            f"D-state persisted for "
            f"{stats['sustained_dstate']} samples"
        )

    if stats.get("rising_iowait"):

        calculated = True

        reasons.append(
            f"iowait rising by "
            f"{stats['iowait_change']:.2f} percentage points "
            f"over rolling window"
        )

    # --------------------------------------------------------
    # Correlated storage symptom
    # --------------------------------------------------------

    if (
        stats.get("iowait_avg", 0) >= 20
        and stats.get("util_avg", 0) >= 80
        and stats.get("await_avg", 0) >= 30
    ):

        calculated = True

        reasons.append(
            "Correlated storage pressure: "
            f"average iowait={stats['iowait_avg']:.2f}%, "
            f"average sda utilization={stats['util_avg']:.2f}%, "
            f"average await={stats['await_avg']:.2f} ms"
        )

    return immediate, calculated, reasons


# ============================================================
# Start
# ============================================================

section("MONITOR START")

log(
    f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}"
)

log(f"Kernel: {os.uname().release}")

log(
    "Thresholds: "
    f"immediate_iowait={IOWAIT_SIGNIFICANT}%, "
    f"sustained_iowait={IOWAIT_SUSTAINED}%, "
    f"disk_util={DISK_UTIL_SIGNIFICANT}%, "
    f"disk_await={DISK_AWAIT_SIGNIFICANT}ms"
)

print()
print("============================================================")
print(" Kernel I/O Rolling-History Monitor")
print("============================================================")
print(f" Log: {LOG_FILE}")
print(f" Interval: {INTERVAL} seconds")
print(f" Rolling history: {HISTORY_MINUTES} minutes")
print()
print("Significant event thresholds:")
print(f"  iowait >= {IOWAIT_SIGNIFICANT}%")
print(f"  D-state >= 1")
print(f"  /dev/sda utilization >= {DISK_UTIL_SIGNIFICANT}%")
print(f"  /dev/sda await >= {DISK_AWAIT_SIGNIFICANT} ms")
print()
print("Normal activity will NOT be written to the log.")
print("Press Ctrl+C to stop.")
print("============================================================")
print()


try:

    while True:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )

        # ----------------------------------------------------
        # Current measurements
        # ----------------------------------------------------

        current_iowait = get_iowait()

        disk = get_disk_stats()

        dstate = get_dstate()

        psi = get_psi()

        # ----------------------------------------------------
        # Add to rolling history
        # ----------------------------------------------------

        history.append({
            "time": timestamp,
            "iowait": current_iowait,
            "util": disk["util"],
            "await": disk["await"],
            "r_await": disk["r_await"],
            "w_await": disk["w_await"],
            "dcount": len(dstate)
        })

        # ----------------------------------------------------
        # Calculate rolling statistics
        # ----------------------------------------------------

        stats = calculate_statistics()

        # ----------------------------------------------------
        # Detect significant/calculated event
        # ----------------------------------------------------

        immediate, calculated, reasons = detect_event(
            disk,
            dstate,
            stats
        )

        # ----------------------------------------------------
        # Nothing significant
        # ----------------------------------------------------

        if not immediate and not calculated:

            print(
                f"{timestamp} "
                f"iowait={current_iowait:.1f}% "
                f"sda={disk['util']:.1f}% "
                f"D={len(dstate)}"
            )

            time.sleep(INTERVAL)

            continue

        # ====================================================
        # SIGNIFICANT EVENT
        # ====================================================

        section(
            "SIGNIFICANT / CALCULATED I/O EVENT"
        )

        log(f"Time: {timestamp}")

        if immediate:
            log("Event type: IMMEDIATE")
        else:
            log("Event type: CALCULATED")

        log("")
        log("SYMPTOMS:")

        for reason in reasons:
            log(f"  - {reason}")

        # ----------------------------------------------------
        # Current state
        # ----------------------------------------------------

        section("CURRENT STATE")

        log(f"CPU iowait: {current_iowait:.2f}%")

        log(
            f"/dev/sda utilization: "
            f"{disk['util']:.2f}%"
        )

        log(
            f"/dev/sda read await: "
            f"{disk['r_await']:.2f} ms"
        )

        log(
            f"/dev/sda write await: "
            f"{disk['w_await']:.2f} ms"
        )

        log(
            f"/dev/sda await: "
            f"{disk['await']:.2f} ms"
        )

        log(
            f"D-state count: "
            f"{len(dstate)}"
        )

        # ----------------------------------------------------
        # Rolling calculations
        # ----------------------------------------------------

        section("ROLLING 10-MINUTE CALCULATIONS")

        log(
            f"Samples: {stats.get('samples', 0)}"
        )

        log(
            f"Average iowait: "
            f"{stats.get('iowait_avg', 0):.2f}%"
        )

        log(
            f"Maximum iowait: "
            f"{stats.get('iowait_max', 0):.2f}%"
        )

        log(
            f"Average /dev/sda utilization: "
            f"{stats.get('util_avg', 0):.2f}%"
        )

        log(
            f"Maximum /dev/sda utilization: "
            f"{stats.get('util_max', 0):.2f}%"
        )

        log(
            f"Average /dev/sda await: "
            f"{stats.get('await_avg', 0):.2f} ms"
        )

        log(
            f"Maximum /dev/sda await: "
            f"{stats.get('await_max', 0):.2f} ms"
        )

        log(
            f"Maximum D-state count: "
            f"{stats.get('dstate_max', 0)}"
        )

        log(
            f"Sustained iowait >= "
            f"{IOWAIT_SUSTAINED}%: "
            f"{stats.get('sustained_iowait', 0)} minutes"
        )

        log(
            f"Sustained sda >= "
            f"{DISK_UTIL_SIGNIFICANT}%: "
            f"{stats.get('sustained_disk', 0)} minutes"
        )

        log(
            f"Sustained D-state: "
            f"{stats.get('sustained_dstate', 0)} samples"
        )

        log(
            f"Iowait change across rolling window: "
            f"{stats.get('iowait_change', 0):.2f} percentage points"
        )

        log(
            f"Rising iowait trend: "
            f"{stats.get('rising_iowait', False)}"
        )

        # ----------------------------------------------------
        # Complete rolling history
        # ----------------------------------------------------

        section("ROLLING HISTORY")

        log(
            "TIME | IOWAIT | SDA_UTIL | SDA_AWAIT | DSTATE"
        )

        for item in history:

            log(
                f"{item['time']} | "
                f"{item['iowait']:.2f}% | "
                f"{item['util']:.2f}% | "
                f"{item['await']:.2f} ms | "
                f"{item['dcount']}"
            )

        # ----------------------------------------------------
        # D-state processes
        # ----------------------------------------------------

        section("D-STATE PROCESSES")

        if dstate:

            for p in dstate:

                log(
                    f"PID={p['pid']} "
                    f"PPID={p['ppid']} "
                    f"USER={p['user']} "
                    f"STATE={p['state']} "
                    f"WCHAN={p['wchan']} "
                    f"ETIME={p['etime']}"
                )

                log(
                    f"COMMAND: {p['command']}"
                )

        else:

            log("None")

        # ----------------------------------------------------
        # Process I/O
        # ----------------------------------------------------

        section("PROCESS I/O")

        log(get_process_io())

        # ----------------------------------------------------
        # Kernel D-state threads
        # ----------------------------------------------------

        section("KERNEL THREADS IN D-STATE")

        log(get_kernel_dstate())

        # ----------------------------------------------------
        # PSI
        # ----------------------------------------------------

        section("I/O PRESSURE")

        log(psi)

        # ----------------------------------------------------
        # Disk
        # ----------------------------------------------------

        section("DETAILED DISK STATISTICS")

        log(
            run_command(
                "iostat -dxk 1 2",
                timeout=8
            )
        )

        # ----------------------------------------------------
        # Kernel messages
        # ----------------------------------------------------

        section("RECENT KERNEL MESSAGES")

        log(get_kernel_messages())

        # ----------------------------------------------------
        # Storage-specific kernel messages
        # ----------------------------------------------------

        section(
            "STORAGE-RELATED KERNEL MESSAGES"
        )

        log(
            get_storage_kernel_messages()
        )

        section(
            "END SIGNIFICANT EVENT"
        )

        print(
            f"{timestamp} *** SIGNIFICANT EVENT *** "
            f"iowait={current_iowait:.1f}% "
            f"sda={disk['util']:.1f}% "
            f"D={len(dstate)}"
        )

        # ----------------------------------------------------
        # Wait until next sample
        # ----------------------------------------------------

        time.sleep(INTERVAL)


except KeyboardInterrupt:

    section("MONITOR STOPPED")

    log(
        f"Stopped: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    print()
    print("Monitor stopped.")
    print(f"Log: {LOG_FILE}")
