#explorer.py
import os
import subprocess
from LAVIS.jarvis.voice.speaker import speak

def handle_explorer(command: str) -> bool:
    command = command.lower()

    if "this pc" in command:
        drive = command.split("drive")[-1].strip().upper()
        if len(drive) == 1 and drive.isalpha():
            path = f"{drive}:\\"
            speak(f"Opening drive {drive}")
            subprocess.Popen(f'explorer "{path}"')
            return True
        else:
            speak("Please specify a valid drive letter.")
            return True

    elif "open folder" in command:
        folder = command.split("open folder")[-1].strip()
        user_dir = os.path.expanduser("~")
        target_path = os.path.join(user_dir, folder)
        if os.path.exists(target_path):
            speak(f"Opening folder {folder}")
            subprocess.Popen(f'explorer "{target_path}"')
        else:
            speak("Folder not found.")
        return True

    elif "open file" in command:
        file_name = command.split("open file")[-1].strip()
        for root, _, files in os.walk(os.path.expanduser("~")):
            for file in files:
                if file_name.lower() in file.lower():
                    speak(f"Opening file {file}")
                    subprocess.Popen(os.path.join(root, file), shell=True)
                    return True
        speak("File not found.")
        return True

    elif "list drives" in command:
        drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        speak("Available drives are: " + ", ".join(drives))
        return True

    elif "shutdown" in command:
        speak("Shutting down the system")
        os.system("shutdown /s /t 1")
        return True

    elif "restart" in command:
        speak("Restarting the system")
        os.system("shutdown /r /t 1")
        return True

    elif "log out" in command or "sign out" in command:
        speak("Signing out")
        os.system("shutdown /l")
        return True

    return False
