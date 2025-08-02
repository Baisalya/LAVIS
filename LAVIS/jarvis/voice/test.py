from vosk import Model, KaldiRecognizer
import sounddevice as sd
import queue
import json
import os

MODEL_PATH = r"D:\Lavis ai\LAVIS\vosk-model-en-in-0.5\vosk-model-small-en-us-0.15"

if not os.path.exists(MODEL_PATH):
    print("Model path is incorrect or missing")
    exit()

model = Model(MODEL_PATH)  # <-- This was failing due to wrong path

recognizer = KaldiRecognizer(model, 16000)
recognizer.SetWords(True)

q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):
    print("🎤 Speak anything... Press Ctrl+C to stop")
    try:
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                print("Recognized:", result.get("text", ""))
            else:
                partial = json.loads(recognizer.PartialResult())
                print("Partial:", partial.get("partial", ""), end='\r')
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
