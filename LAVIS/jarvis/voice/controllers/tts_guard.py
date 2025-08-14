# ✅ tts_guard no longer pauses the mic — we keep listening for barge-in.
from functools import wraps
from LAVIS.jarvis.voice.recognizer import set_last_spoken_text

def guard_microphone(tts_func):
    """
    Previously paused/resumed listening around TTS. For barge-in, we *do not* pause.
    We still record last_spoken_text to avoid echo-matching.
    """
    @wraps(tts_func)
    def wrapper(text, *args, **kwargs):
        set_last_spoken_text(text)
        # No pause_listening() / resume_listening() here
        return tts_func(text, *args, **kwargs)
    return wrapper
