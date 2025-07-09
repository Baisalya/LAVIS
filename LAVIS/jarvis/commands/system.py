import datetime
import os
from LAVIS.jarvis.voice.speaker import speak

def handle_system(command: str) -> bool:
    command = command.lower()

    if any(x in command for x in ["exit", "shutdown", "quit", "stop"]):
        speak("Goodbye!")
        exit()

    elif "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {now}.")
        return True

    elif "date" in command:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        speak(f"Today is {today}.")
        return True

    return False
