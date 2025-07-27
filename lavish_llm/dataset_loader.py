from datasets import load_dataset

def load_offline_knowledge():
    knowledge_chunks = []

    # General knowledge (Wikipedia)
    wiki = load_dataset("wikitext", "wikitext-2-raw-v1", split="train[:1%]")
    knowledge_chunks.extend([x["text"] for x in wiki if x["text"].strip()])

    # Dialogue dataset
    dialog = load_dataset("daily_dialog", split="train[:1%]")
    for d in dialog:
        knowledge_chunks.append("Dialog: " + d["dialog"])

    # Common sense QA
    commonsense = load_dataset("commonsense_qa", split="train[:1%]")
    for cs in commonsense:
        q = cs["question"]
        a = cs["answerKey"]
        knowledge_chunks.append(f"Q: {q} A: {a}")

    # Code understanding
    try:
        code = load_dataset("codeparrot/github-jupyter-code-to-text", split="train[:1%]")
        for c in code:
            knowledge_chunks.append(c["code"][:500])
    except:
        pass  # Skip if dataset fails

    # Emotional awareness (go_emotions)
    try:
        emotions = load_dataset("go_emotions", split="train[:1%]")
        for e in emotions:
            if e["labels"]:
                knowledge_chunks.append(f"Text: {e['text']} | Emotions: {e['labels']}")
    except:
        pass  # Skip if unavailable

    return knowledge_chunks[:500]
