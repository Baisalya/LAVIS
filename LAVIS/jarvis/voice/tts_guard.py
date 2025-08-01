# tts_guard.py

from functools import wraps
from LAVIS.jarvis.voice.recognizer import pause_listening, resume_listening, set_last_spoken_text

def guard_microphone(tts_func):
    @wraps(tts_func)
    def wrapper(text, *args, **kwargs):
        set_last_spoken_text(text)
        pause_listening()
        try:
            return tts_func(text, *args, **kwargs)
        finally:
            resume_listening()
    return wrapper
