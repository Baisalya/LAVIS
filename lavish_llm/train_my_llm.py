# ✅ Train your own small LLM from scratch using HuggingFace

import os
os.environ["TRANSFORMERS_NO_TF"] = "1"
from datasets import load_dataset, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments
)

# === STEP 1: Config ===
MODEL_NAME = "sshleifer/tiny-gpt2"  # Very small GPT-2 (6M parameters)
OUTPUT_DIR = "my_trained_llm"
EPOCHS = 5
MAX_LEN = 64

# === STEP 2: Load or make simple dataset ===
def get_dataset():
    # You can replace this with your own .txt file later
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split="train[:1%]")
    dataset = dataset.filter(lambda x: len(x["text"]) > 10)
    return dataset

dataset = get_dataset()

# === STEP 3: Tokenizer and Tokenize ===
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token  # Required for GPT-style models

def tokenize(batch):
    return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=MAX_LEN)

tokenized_dataset = dataset.map(tokenize, batched=True)

# === STEP 4: Load Model ===
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# === STEP 5: Training Setup ===
training_args = TrainingArguments(
    output_dir="./my_trained_llm",
    overwrite_output_dir=True,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    save_steps=500,
    save_total_limit=2,
    #evaluation_strategy="epoch",  # ❌ remove this line or ensure you're using PyTorch
    logging_dir="./logs",
)


data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False  # GPT = causal, not masked
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    eval_dataset=tokenized_dataset,
    tokenizer=tokenizer,
    data_collator=data_collator
)

# === STEP 6: Train ===
trainer.train()

# === STEP 7: Save Model ===
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"\n✅ Training complete! Model saved to: {OUTPUT_DIR}")
