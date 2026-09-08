#!/bin/bash

BATTERY="/sys/class/power_supply/BAT0"
THRESHOLD=20
STATE_FILE="$HOME/.battery_alarm_triggered"

# Battery must exist
[ -f "$BATTERY/capacity" ] || exit 0

LEVEL=$(cat "$BATTERY/capacity" 2>/dev/null) || exit 0
STATUS=$(cat "$BATTERY/status" 2>/dev/null)

# If charging/full, reset the alarm state
if [ "$STATUS" = "Charging" ] || [ "$STATUS" = "Full" ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

# Battery <= 20%
if [ "$LEVEL" -le "$THRESHOLD" ]; then

    # Alarm only once
    if [ ! -f "$STATE_FILE" ]; then
        touch "$STATE_FILE"

        SOUND="/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"

        if command -v pw-play >/dev/null 2>&1; then
            pw-play "$SOUND" >/dev/null 2>&1
        elif command -v paplay >/dev/null 2>&1; then
            paplay "$SOUND" >/dev/null 2>&1
        fi
    fi
else
    # Battery went above 20%, so re-arm the alarm
    rm -f "$STATE_FILE"
fi
