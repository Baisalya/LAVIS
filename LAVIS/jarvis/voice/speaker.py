# ✅ Fully-duplex speaker.py with barge-in (interrupt-on-speech) + offline fallback
import asyncio
import threading
import io
import edge_tts
from pydub import AudioSegment
import pyttsx3
import pyaudio
import random
import time

from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import set_last_spoken_text, resume_listening  # keep API
# NOTE: we intentionally DO NOT pause listening during TTS anymore for barge-in
# from LAVIS.jarvis.voice.recognizer import pause_listening  # <- not used

try:
    from jarvis_hud.main import append_hud_console
except ImportError:
    def append_hud_console(msg): print(msg)

# === Global speaking state for barge-in ===
stop_speaking = False
speaking = False  # <- recognizer reads this to detect barge-in
voice_name = "en-US-AriaNeural"

# === Offline TTS engine ===
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
try:
    voices = engine.getProperty('voices')
    if len(voices) > 1:
        engine.setProperty('voice', voices[1].id)
except Exception as e:
    print(f"[TTS] Voice setup error: {e}")

def _mark_speaking(active: bool):
    global speaking
    speaking = active

def speak_offline(text: str):
    """Offline TTS without pausing the mic (barge-in capable)."""
    global stop_speaking
    _mark_speaking(True)
    stop_speaking = False
    try:
        print("🗣️ (offline)", text)
        append_hud_console(f"🗣️ (offline) {text}")
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        import traceback
        print("🔇 Offline TTS error:", e)
        traceback.print_exc()
        try:
            engine.stop()
        except Exception:
            pass
    finally:
        _mark_speaking(False)
        # we keep recognizer running throughout; just ensure normal state
        resume_listening()

def play_interruptible(audio_segment: AudioSegment):
    """Play audio and allow mid-stream interruption via stop_speaking flag."""
    global stop_speaking
    p = pyaudio.PyAudio()
    stream = p.open(
        format=p.get_format_from_width(audio_segment.sample_width),
        channels=audio_segment.channels,
        rate=audio_segment.frame_rate,
        output=True,
    )
    chunk_size = 2048
    data = audio_segment.raw_data
    try:
        for i in range(0, len(data), chunk_size):
            if stop_speaking:
                break
            stream.write(data[i:i+chunk_size])
    finally:
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        p.terminate()

def play_with_bargein(audio_segment: AudioSegment):
    """No mic pausing here — recognizer keeps running and can interrupt."""
    play_interruptible(audio_segment)
    # small cushion to avoid clipping end
    time.sleep(0.05)

def speak(text: str):
    """
    Network TTS with offline fallback.
    Barge-in enabled: recognizer runs; on user speech -> stop_speech() is called.
    """
    global stop_speaking
    stop_speaking = False
    _mark_speaking(True)
    set_last_spoken_text(text)

    if not is_connected():
        speak_offline(text)
        return

    async def run_tts():
        global stop_speaking
        try:
            communicate = edge_tts.Communicate(text, voice_name)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if stop_speaking:
                    print("🚩 Interrupted during streaming.")
                    return
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])

            if buffer.tell() == 0:
                print("❌ TTS audio buffer is empty.")
                speak_offline(text)
                return

            try:
                buffer.seek(0)
                audio = AudioSegment.from_file(buffer, format="mp3")
            except Exception as decode_error:
                print("❌ Error decoding MP3 from TTS buffer:", decode_error)
                speak_offline(text)
                return

            if not stop_speaking:
                try:
                    play_with_bargein(audio)
                except Exception as playback_error:
                    print("🔊 Playback error:", playback_error)
                    speak_offline(text)

        except Exception as tts_error:
            print("⚠️ edge-tts failed, using offline fallback:", tts_error)
            speak_offline(text)
        finally:
            _mark_speaking(False)

    def run_async():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tts())
        except Exception as e:
            import traceback
            print(f"[TTS Thread Error] {e}")
            traceback.print_exc()
            speak_offline(text)
        finally:
            _mark_speaking(False)

    try:
        threading.Thread(target=run_async, daemon=True).start()
    except Exception as e:
        print("[TTS Startup Error]", e)
        _mark_speaking(False)
        speak_offline(text)

def stop_speech():
    """External interrupt for barge-in or voice 'stop' command."""
    global stop_speaking
    stop_speaking = True
    try:
        engine.stop()
    except Exception as e:
        print("⚠️ engine.stop() failed:", e)
    print("⛔ Speech stopped")

def human_speak(answer: str):
    """
    Optional helper: speak a quick filler then the final answer.
    Both are barge-in capable.
    """
    filler = random.choice([
        "Got it...",
        "Let me respond...",
        "One second...",
        "Alright...",
        "Okay, here's what I found..."
    ])

    def run_human_speak():
        global stop_speaking
        try:
            # Filler
            stop_speaking = False
            try:
                speak(filler)
                time.sleep(1.0)
            except Exception as filler_error:
                print("⚠️ Filler speak failed:", filler_error)
                speak_offline(filler)

            # Final
            stop_speaking = False
            final = answer.strip() if answer else "Sorry, I don't have anything useful."
            try:
                speak(final)
            except Exception as final_error:
                print("❌ Final response failed:", final_error)
                speak_offline(final)

        except Exception:
            import traceback
            print("❌ human_speak crashed:")
            traceback.print_exc()
            speak_offline("Sorry, something went wrong.")

    try:
        threading.Thread(target=run_human_speak, daemon=True).start()
    except Exception as e:
        print("[human_speak Thread Error]", e)
        speak_offline(answer or "Sorry, something went wrong.")
