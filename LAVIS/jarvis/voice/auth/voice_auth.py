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
def is_authenticated(audio_path, threshold=0.1):
    try:
        if not os.path.exists(audio_path):
            print(f"❌ Audio not found: {audio_path}")
            return False

        enrolled_embedding = load_embedding()

        signal, fs = torchaudio.load(audio_path)

        # Check for very short audio
        if signal.shape[1] < fs:
            print("⏳ Input audio too short for authentication.")
            return False

        test_embedding = auth_model.encode_batch(signal).squeeze(1)

        # Cosine similarity
        score = torch.nn.functional.cosine_similarity(
            enrolled_embedding, test_embedding
        ).item()

        print(f"🔐 Voice match score: {score:.4f}")
        return score >= threshold

    except Exception:
        print("🚨 Error during authentication:")
        traceback.print_exc()
        return False
