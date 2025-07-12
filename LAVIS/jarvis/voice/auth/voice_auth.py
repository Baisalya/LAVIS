import os
import torch
import torchaudio
import traceback
from speechbrain.inference import SpeakerRecognition

# === Load speaker model once ===
auth_model = SpeakerRecognition.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="tmp_spkrec"
)

# === Path settings ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDING_FILE = os.path.join(BASE_DIR, "enrolled_embedding.pt")
ENROLLED_WAV = os.path.join(BASE_DIR, "enrolled.wav")

# === Save embedding from a long audio file ===
def save_embedding_from_long_file(wav_path=ENROLLED_WAV, duration_per_chunk=3, stride=1.5):
    try:
        signal, fs = torchaudio.load(wav_path)

        chunk_samples = int(duration_per_chunk * fs)        # e.g., 3 sec
        stride_samples = int(stride * fs)                   # e.g., 1.5 sec overlap

        total_samples = signal.shape[1]
        if total_samples < chunk_samples:
            print("⚠️ Audio too short for chunked enrollment.")
            return

        print(f"🔍 Total duration: {total_samples / fs:.2f}s. Extracting chunks...")

        embeddings = []
        for start in range(0, total_samples - chunk_samples + 1, stride_samples):
            chunk = signal[:, start:start + chunk_samples]
            embedding = auth_model.encode_batch(chunk).squeeze(1)
            embeddings.append(embedding)

        if not embeddings:
            print("❌ No chunks extracted.")
            return

        avg_embedding = torch.mean(torch.stack(embeddings), dim=0)
        torch.save(avg_embedding, EMBEDDING_FILE)
        print(f"✅ Enrolled from long audio ({len(embeddings)} chunks)")

    except Exception:
        print("🚨 Error during long audio enrollment:")
        traceback.print_exc()


# === Save embedding from a short reference WAV ===
def save_embedding(wav_path=ENROLLED_WAV):
    try:
        if not os.path.exists(wav_path):
            print(f"⚠️ Enrollment WAV not found: {wav_path}")
            return

        signal, fs = torchaudio.load(wav_path)
        if signal.shape[1] < fs:
            print("⚠️ Enrolled audio too short. Use at least 1 second.")
            return

        embedding = auth_model.encode_batch(signal).squeeze(1)
        torch.save(embedding, EMBEDDING_FILE)
        print("✅ Voice embedding saved.")
    except Exception:
        print("🚫 Error while saving voice embedding:")
        traceback.print_exc()


# === Load stored embedding ===
def load_embedding():
    if not os.path.exists(EMBEDDING_FILE):
        raise FileNotFoundError("❌ Enrolled embedding file missing.")
    return torch.load(EMBEDDING_FILE, map_location=torch.device("cpu"))


# === Basic short audio authentication ===
def is_authenticated_from_bytes(pcm_bytes: bytes, threshold=0.65):
    try:
        enrolled_embedding = load_embedding()

        waveform = torch.frombuffer(pcm_bytes, dtype=torch.int16).float() / 32768.0
        waveform = waveform.unsqueeze(0)

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
        print("🚨 Error during simple authentication:")
        traceback.print_exc()
        return False


# === Long audio authentication: search for match in any chunk ===
def check_long_audio_for_match(pcm_bytes: bytes, threshold=0.65, chunk_size=16000, stride=8000):
    try:
        enrolled_embedding = load_embedding()

        waveform = torch.frombuffer(pcm_bytes, dtype=torch.int16).float() / 32768.0
        waveform = waveform.unsqueeze(0)  # [1, N]
        total_samples = waveform.shape[1]

        if total_samples < chunk_size:
            print("⏳ Audio too short for matching.")
            return False

        print(f"🎧 Total audio length: {total_samples / 16000:.2f} seconds")

        match_scores = []

        for start in range(0, total_samples - chunk_size + 1, stride):
            chunk = waveform[:, start:start + chunk_size]
            test_embedding = auth_model.encode_batch(chunk).squeeze(1)
            score = torch.nn.functional.cosine_similarity(enrolled_embedding, test_embedding).item()
            match_scores.append(score)

            seconds = start / 16000
            print(f"🔍 [{seconds:.2f}s] Score: {score:.4f}")

            if score >= threshold:
                print(f"✅ Match found at {seconds:.2f} seconds (Score: {score:.4f})")
                return True

        print(f"❌ No match found. Max score: {max(match_scores):.4f}")
        return False

    except Exception:
        print("🚨 Error in long audio checking:")
        traceback.print_exc()
        return False
