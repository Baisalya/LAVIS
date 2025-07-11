import os
import torch
import torchaudio
from speechbrain.inference import SpeakerRecognition
import traceback

# 🔁 Load model once
auth_model = SpeakerRecognition.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb", savedir="tmp_spkrec"
)

# 📁 Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDING_FILE = os.path.join(BASE_DIR, "enrolled_embedding.pt")
ENROLLED_WAV = os.path.join(BASE_DIR, "enrolled.wav")

# 🔐 Save embedding from a reference WAV
def save_embedding():
    try:
        if not os.path.exists(ENROLLED_WAV):
            print(f"⚠️ Enrollment WAV not found: {ENROLLED_WAV}")
            return

        signal, fs = torchaudio.load(ENROLLED_WAV)
        if signal.shape[1] < fs:
            print("⚠️ Enrolled audio too short. Use at least 1 second.")
            return

        embedding = auth_model.encode_batch(signal).squeeze(1)
        torch.save(embedding, EMBEDDING_FILE)
        print("✅ Voice embedding saved.")
    except Exception:
        print("🚫 Error while saving voice embedding:")
        traceback.print_exc()

# 🔄 Load stored embedding
def load_embedding():
    if not os.path.exists(EMBEDDING_FILE):
        raise FileNotFoundError("❌ Enrolled embedding file missing.")
    return torch.load(EMBEDDING_FILE, map_location=torch.device("cpu"))

# ✅ Check if input voice matches enrolled voice
import io

import torch
import torchaudio
import traceback

def is_authenticated_from_bytes(pcm_bytes: bytes, threshold=0.01):
    try:
        enrolled_embedding = load_embedding()

        waveform = torch.frombuffer(pcm_bytes, dtype=torch.int16).float() / 32768.0
        waveform = waveform.unsqueeze(0)

        # Truncate or pad to 1 sec (16000 samples)
        if waveform.shape[1] < 16000:
            print("⏳ Audio too short for authentication.")
            return False
        elif waveform.shape[1] > 16000:
            waveform = waveform[:, :16000]

        test_embedding = auth_model.encode_batch(waveform).squeeze(1)
        score = torch.nn.functional.cosine_similarity(enrolled_embedding, test_embedding).item()
        print(f"🔐 Voice match score: {score:.4f}")
        return score >= threshold

    except Exception:
        print("🚨 Error during in-memory authentication:")
        traceback.print_exc()
        return False
