# === Knowledge Loader ===
import os
import sys
import datetime
import webbrowser
from datasets import load_dataset, load_from_disk

class KnowledgeLoader:
    def __init__(self, cache_dir="datasets"):
        self.knowledge_chunks = []
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _load_or_cache_dataset(self, dataset_name, split, local_name=None, config_name=None, **kwargs):
        local_path = os.path.join(self.cache_dir, local_name or dataset_name.replace("/", "_"))
        if os.path.exists(local_path):
            print(f"📂 Loading from cache: {local_path}")
            return load_from_disk(local_path)
        print(f"⬇️ Downloading {dataset_name} from Hugging Face...")
        dataset = load_dataset(dataset_name, name=config_name, split=split, **kwargs)
        dataset.save_to_disk(local_path)
        print(f"✅ Saved to: {local_path}")
        return dataset

    def load_general_knowledge(self):
        wiki = self._load_or_cache_dataset(
            dataset_name="wikitext",
            split="train[:1%]",
            config_name="wikitext-2-raw-v1",
            local_name="wikitext-2-raw-v1"
        )
        self.knowledge_chunks.extend([x["text"] for x in wiki if x["text"].strip()])

    def load_dialogue(self):
        try:
            dataset = self._load_or_cache_dataset("Cynaptics/persona-chat", split="train[:1%]")
            for entry in dataset:
                persona = entry.get("persona", [])
                dialog = entry.get("utterances", [])
                persona_text = " | ".join(persona)
                for turn in dialog:
                    history = " ".join(turn.get("history", []))
                    candidate = turn.get("candidates", [""])[0]
                    self.knowledge_chunks.append(
                        f"Persona: {persona_text} | Dialog: {history} → {candidate}"
                    )
        except Exception as e:
            print("⚠️ Dialogue dataset could not be loaded:", e)

    def load_commonsense(self):
        commonsense = self._load_or_cache_dataset("commonsense_qa", split="train[:1%]")
        for cs in commonsense:
            q = cs["question"]
            a = cs["answerKey"]
            self.knowledge_chunks.append(f"Q: {q} A: {a}")

    def load_code_knowledge(self):
        try:
            code = self._load_or_cache_dataset("codeparrot/github-jupyter-code-to-text", split="train[:1%]")
            for c in code:
                self.knowledge_chunks.append(c["code"][:500])
        except Exception as e:
            print("⚠️ Error loading code knowledge:", e)

    def load_emotional_knowledge(self):
        try:
            emotions = self._load_or_cache_dataset("go_emotions", split="train[:1%]")
            for e in emotions:
                if e["labels"]:
                    self.knowledge_chunks.append(
                        f"Text: {e['text']} | Emotions: {e['labels']}"
                    )
        except Exception as e:
            print("⚠️ Error loading emotional knowledge:", e)

    def load_all(self):
        self.load_general_knowledge()
        self.load_dialogue()
        self.load_commonsense()
        self.load_code_knowledge()
        self.load_emotional_knowledge()
        return self.knowledge_chunks[:100]  # ⬅️ Reduce for token safety
