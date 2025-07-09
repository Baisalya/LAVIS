from TTS.api import TTS

print("📥 Downloading English model...")
TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")

print("📥 Downloading Hindi model...")
TTS(model_name="tts_models/hi/cv_vits")

print("✅ Done. Ready to use offline!")
