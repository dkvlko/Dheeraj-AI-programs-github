#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

OnMessage(0x218, WM_POWERBROADCAST)

global WakeHandled := false

WM_POWERBROADCAST(wParam, lParam, msg, hwnd) {
    global WakeHandled

    ; Optional logging (remove if not needed)
    FileAppend("Wake detected: " wParam "`n", "D:\wake_log.txt")

    ; Resume events
    if (wParam = 0x7 || wParam = 0x12) {

        ; Prevent duplicate triggers
        if (!WakeHandled) {
            WakeHandled := true

            ; 10-second delay (10000 ms)
            SetTimer(PressCapsTwice, -10000)

            ; Reset flag after 30 sec (next sleep cycle ready)
            SetTimer(ResetWakeFlag, -30000)
        }
    }
}

PressCapsTwice() {
    Send("{CapsLock}")
    Sleep(400)
    Send("{CapsLock}")
}

ResetWakeFlag() {
    global WakeHandled := false
}