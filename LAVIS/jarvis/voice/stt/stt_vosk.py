# stt_vosk.py
import os
import json
from vosk import Model, KaldiRecognizer
from .stt_base import STTBase


def _default_command_model_path():
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "vosk-model-en-in-0.5", "vosk-model-en-us-daanzu-20200905"
    ))


def _default_freeform_model_path():
    return os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "vosk-model-en-in-0.5", "vosk-model-small-en-us-0.15"
    ))


def _load_command_grammar():
    path = os.path.join(os.path.dirname(__file__), "commands.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[VoskSTT] ⚠️ Failed to load grammar from {path}: {e}")
        return []


class VoskSTT(STTBase):
    def __init__(self, mode: str = "freeform", sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._init_model(mode)
        self.commands = _load_command_grammar()  # for classification
        self._last_partial = ""
        self._last_text = ""
        self._last_category = "freeform"

    def _init_model(self, mode: str):
        if mode == "command":
            model_path = _default_command_model_path()
            grammar = _load_command_grammar()
        else:
            model_path = _default_freeform_model_path()
            grammar = None

        print(f"[VoskSTT] Mode={mode} → trying model path: {model_path}")

        if not os.path.isdir(model_path):
            parent = os.path.dirname(model_path)
            print(f"[VoskSTT] ❌ Model path not found: {model_path}")
            print(f"[VoskSTT] Parent exists: {os.path.isdir(parent)} → {parent}")
            raise FileNotFoundError(f"❌ Model path not found: {model_path}")

        # Load model
        self.model = Model(model_path)
        print(f"[VoskSTT] ✅ Model loaded successfully for mode '{mode}'")

        grammar_json = json.dumps(grammar) if grammar else None
        if grammar_json:
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate, grammar_json)
        else:
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)

        self.recognizer.SetWords(True)
        self.mode = mode

    # --- classification ---
    def _classify(self, text: str) -> str:
        if not text:
            return "freeform"
        if text in self.commands:
            return "command"
        if len(text.split()) <= 3:
            return "command"
        if text in ("stop", "cancel", "abort"):
            return "stop"
        return "freeform"

    # --- STTBase methods ---
    def accept_waveform(self, audio_data: bytes) -> bool:
        return self.recognizer.AcceptWaveform(audio_data)

    def get_result(self):
        try:
            res = json.loads(self.recognizer.Result())
            text = (res.get("text") or "").strip().lower()
            category = self._classify(text)
            self._last_text = text
            self._last_category = category
            return text, category
        except Exception:
            return "", "freeform"

    def get_partial(self) -> str:
        try:
            res = json.loads(self.recognizer.PartialResult())
            partial = (res.get("partial") or "").strip().lower()
            self._last_partial = partial
            return partial
        except Exception:
            return ""

    def reset(self) -> None:
        self.recognizer.Reset()
        self._last_text = ""
        self._last_category = "freeform"
        self._last_partial = ""
