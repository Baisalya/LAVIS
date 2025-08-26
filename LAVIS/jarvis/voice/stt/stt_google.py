# LAVIS/jarvis/voice/stt/stt_google.py
import io
import queue
import time
import speech_recognition as sr

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)


class GoogleSTT:
    def __init__(self, language="en-IN", multi_language=False, languages=None, min_buffer_sec=2.0):
        self.recognizer = sr.Recognizer()
        self.language = language
        self.multi_language = multi_language
        self.languages = languages or ["en-IN"]

        # Audio buffering
        self.buffer = bytearray()
        self.sample_rate = 16000
        self.sample_width = 2  # paInt16 → 2 bytes per sample
        self.min_buffer_sec = min_buffer_sec
        self.min_buffer_bytes = int(self.sample_rate * self.sample_width * self.min_buffer_sec)

        append_hud_console(
            f"🌐 Online: Using GoogleSTT "
            f"({'multi-language' if multi_language else language})."
        )

    def accept_waveform(self, data: bytes) -> bool:
        """Buffer audio chunks until enough is collected"""
        self.buffer.extend(data)
        if len(self.buffer) >= self.min_buffer_bytes:
            return True
        return False

    def get_result(self) -> str:
        """Send buffered audio to Google and return recognized text"""
        if not self.buffer:
            return ""

        audio_data = sr.AudioData(bytes(self.buffer), self.sample_rate, self.sample_width)

        # Clear buffer for next utterance
        self.buffer.clear()

        langs_to_try = self.languages if self.multi_language else [self.language]
        for lang in langs_to_try:
            try:
                result = self.recognizer.recognize_google(audio_data, language=lang)
                if result:
                    append_hud_console(f"[GoogleSTT] ✅ Heard in {lang}: {result}")
                    return result
            except sr.UnknownValueError:
                append_hud_console(f"[GoogleSTT] 🤔 Could not understand audio in {lang}")
            except sr.RequestError as e:
                append_hud_console(f"[GoogleSTT] ❌ API error for {lang}: {e}")
                break  # network error → stop trying others

        append_hud_console("[GoogleSTT] 🤔 Could not understand audio in any language")
        return ""

    def get_partial(self) -> str:
        """Google API doesn’t support streaming partials"""
        return ""

    def reset(self):
        self.buffer.clear()
        append_hud_console("[GoogleSTT] 🔄 Buffer reset")
