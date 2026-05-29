import time
from LAVIS.jarvis.voice.speaker import speak
from LAVIS.jarvis.voice.recognizer import set_session_mode, resume_listening, command_queue

def chatting_listening(timeout=30):
    from LAVIS.jarvis.commands.commands import handle_command
    from LAVIS.jarvis.web.fallback import handle_fallback

    print("\n🟣 Entering Chat Session")
    set_session_mode(True)  # ✅ Just use session lock (not pause)
    speak("I'm listening. You can ask me anything or say 'skip' to cancel.")

    start_time = time.time()

    while time.time() - start_time < timeout:
        if not command_queue.empty():
            query = command_queue.get().strip().lower()
            print("🎧 Chat heard:", query)

            if query in ["skip", "stop", "cancel"]:
                speak("Okay, skipping this conversation.")
                break

            if handle_command(query):
                continue

            if handle_fallback(query):
                continue

            speak("Sorry, I couldn't understand that.")
        else:
            time.sleep(0.2)

    else:
        speak("No response received. Returning to background listening.")

    resume_listening()
    set_session_mode(False)
    print("🟢 Resuming background listening...")
