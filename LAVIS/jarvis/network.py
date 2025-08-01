# ✅ Patched network.py with network change detection support
import socket
import threading
import time

from LAVIS.jarvis.voice.recognizer import resume_listening

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

_last_connected = None


def is_connected():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


def check_and_handle_network_change():
    global _last_connected
    current = is_connected()
    if _last_connected is None:
        _last_connected = current
        return

    if current != _last_connected:
        if current:
            append_hud_console("🌐 Reconnected — resuming full features.")
            resume_listening()
        else:
            append_hud_console("📴 Offline — fallback to offline mode.")
    _last_connected = current


def start_network_watcher():
    def loop():
        while True:
            try:
                check_and_handle_network_change()
            except Exception as e:
                append_hud_console(f"⚠️ Network watcher error: {e}")
            time.sleep(10)

    threading.Thread(target=loop, daemon=True).start()
