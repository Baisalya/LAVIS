# convert_mp3_to_wav.py
# 📦 Converts your recorded .mp3 voice file (e.g., from phone) into a compatible WAV format

from pydub import AudioSegment

mp3_path = "myvoice.mp3"
wav_path = wav_path = "enrolled.wav"       # This is the filename your voice_auth system expects

# Load and convert
audio = AudioSegment.from_mp3(mp3_path)
audio = audio.set_channels(1).set_frame_rate(16000)  # Mono + 16kHz = Required format
audio.export(wav_path, format="wav")

print("✅ Converted 'myvoice.mp3' to 'enrolled.wav' (mono, 16kHz)")
