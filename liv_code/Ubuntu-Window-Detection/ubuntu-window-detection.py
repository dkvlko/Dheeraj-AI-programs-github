from ewmhlib import EwmhRoot, EwmhWindow
import subprocess

def is_firefox(win):
    prop = win.getProperty("WM_CLASS")

    if not prop or not hasattr(prop, "value"):
        return False

    val = prop.value

    try:
        if isinstance(val, tuple):
            val = val[1]

        if isinstance(val, (list, tuple)):
            val = bytes(val).decode(errors="ignore")

        if isinstance(val, bytes):
            val = val.decode(errors="ignore")

        return "firefox" in val.lower()

    except Exception:
        return False




def focus_firefox():
    root = EwmhRoot()

    for win_id in root.getClientList():
        try:
            win = EwmhWindow(win_id)

            if is_firefox(win):
                title_prop = win.getProperty("_NET_WM_NAME")
                title = title_prop.value[1] if title_prop else "Unknown"

                print(f"Focusing: {title}")
                #focus_window(win_id)
                print("Win id : ",win_id)
                subprocess.run(["wmctrl", "-i", "-a", hex(win_id)])
                return True

        except Exception:
            continue

    print("Firefox window not found.")
    return False


if __name__ == "__main__":
    focus_firefox()
