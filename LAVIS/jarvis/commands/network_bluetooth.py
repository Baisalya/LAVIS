# network_bluetooth.py
import subprocess
import asyncio
import re

from LAVIS.hud_display import show_hud_reply
from LAVIS.jarvis.voice.speaker import speak
from fuzzywuzzy import fuzz
from bleak import BleakScanner

last_scanned_wifi = []
last_scanned_bluetooth = []

def handle_network_bluetooth(command: str) -> bool:
    global last_scanned_wifi, last_scanned_bluetooth
    cmd = command.lower().strip()

    if "scan bluetooth" in cmd:
        show_hud_reply("Scanning Bluetooth devices...")
        speak("Scanning nearby Bluetooth devices.")
        try:
            # 🔄 Async scan wrapped inside sync function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            devices = loop.run_until_complete(BleakScanner.discover(timeout=5.0))

            last_scanned_bluetooth = [d.name for d in devices if d.name]
            if not last_scanned_bluetooth:
                show_hud_reply("No Bluetooth devices found.")
                speak("No Bluetooth devices found.")
            else:
                speak(f"{len(last_scanned_bluetooth)} devices found.")
                show_hud_reply("Found: " + ", ".join(last_scanned_bluetooth))
        except Exception as e:
            show_hud_reply("Bluetooth scan failed.")
            speak("Bluetooth scan failed.")
            print("❌ Bleak error:", e)
        return True

    elif "scan network" in cmd:
        show_hud_reply("Scanning Wi-Fi networks...")
        speak("Scanning for nearby Wi-Fi.")
        try:
            result = subprocess.check_output(["netsh", "wlan", "show", "network", "mode=Bssid"], shell=True, text=True)
            last_scanned_wifi = list({re.search(r"SSID \d+ : (.+)", line).group(1).strip()
                                      for line in result.splitlines() if "SSID" in line})
            speak(f"{len(last_scanned_wifi)} Wi-Fi networks found.")
            show_hud_reply("Found: " + ", ".join(last_scanned_wifi))
        except:
            show_hud_reply("Failed to scan networks.")
            speak("Network scan failed.")
        return True

    elif "connect network" in cmd:
        speak("Trying to connect to best known network.")
        try:
            output = subprocess.check_output("netsh wlan show profiles", shell=True, text=True)
            profiles = re.findall(r"All User Profile\s*:\s*(.+)", output)
            strongest = next((ssid for ssid in last_scanned_wifi if ssid in profiles), None)
            if strongest:
                subprocess.call(f"netsh wlan connect name=\"{strongest}\"", shell=True)
                show_hud_reply(f"Connected to {strongest}")
                speak(f"Connected to {strongest}")
            else:
                speak("No known Wi-Fi found in scan.")
                show_hud_reply("No saved Wi-Fi from scan matched.")
        except:
            show_hud_reply("Could not connect to network.")
            speak("Connection failed.")
        return True

    elif cmd.startswith("connect to "):
        name = cmd.replace("connect to ", "").strip()
        all_devices = last_scanned_wifi + last_scanned_bluetooth
        if not all_devices:
            speak("No recent scan data found.")
            show_hud_reply("No scanned device found.")
            return True

        best_match = max(all_devices, key=lambda dev: fuzz.ratio(dev.lower(), name.lower()))
        if fuzz.ratio(best_match.lower(), name.lower()) > 60:
            show_hud_reply(f"Connecting to {best_match}...")
            speak(f"Trying to connect to {best_match}.")

            if best_match in last_scanned_wifi:
                subprocess.call(f"netsh wlan connect name=\"{best_match}\"", shell=True)
                show_hud_reply(f"Connected to {best_match}")
                speak(f"Connected to {best_match}")
            elif best_match in last_scanned_bluetooth:
                show_hud_reply(f"Bluetooth connection to {best_match} not supported yet.")
                speak(f"Identified {best_match}, but connecting to BLE devices is not implemented.")
            else:
                show_hud_reply(f"Device {name} not in scan list.")
                speak("Could not connect.")
        else:
            speak("No close match found for that name.")
            show_hud_reply("No similar scanned device found.")
        return True

    return False
