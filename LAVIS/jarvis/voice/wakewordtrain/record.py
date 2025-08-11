import os
import sounddevice as sd
import soundfile as sf

# Ensure folder exists
os.makedirs("samples/lavish", exist_ok=True)

def record_wakeword(filename, duration=2, samplerate=16000):
    print(f"Recording: {filename}...")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    sf.write(filename, audio, samplerate)
    print("✅ Done!")

# Record 10 samples
for i in range(1, 11):
    record_wakeword(f"samples/lavish/hello_lavish_{i}.wav")
