# train_wakeword.py

from openwakeword.model_trainer import train_wakeword
import os

samples_path = "samples/lavish"
output_dir = "wakeword_models"
wakeword_name = "lavish"

os.makedirs(output_dir, exist_ok=True)

audio_files = [os.path.join(samples_path, f) for f in os.listdir(samples_path) if f.endswith(".wav")]

assert len(audio_files) >= 5, "Please provide at least 5 training samples."

train_wakeword(
    wakeword_name=wakeword_name,
    audio_paths=audio_files,
    output_directory=output_dir
)

print("✅ Wake word training complete. Model saved to:", os.path.join(output_dir, f"{wakeword_name}.onnx"))
