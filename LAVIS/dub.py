from pydub import AudioSegment

mp3_path = "kaku.mp3"
wav_path = "pythonkaku.wav"

audio = AudioSegment.from_mp3(mp3_path)
audio = audio.set_frame_rate(16000).set_channels(1)
audio.export(wav_path, format="wav")

print("✅ Converted to WAV:", wav_path)
