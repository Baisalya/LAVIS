import os
import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import get_peft_model, LoraConfig, TaskType

# === Load Custom Knowledge ===
from KnowledgeLoader import KnowledgeLoader
loader = KnowledgeLoader()
chunks = loader.load_all()

# === Format as Chat-style Prompt ===
def convert_to_chat_format(text):
    return f"### Instruction:\n{text.strip()}\n\n### Response:\n"

formatted_data = [{"text": convert_to_chat_format(chunk)} for chunk in chunks]
raw_dataset = Dataset.from_list(formatted_data)

# === Tokenize ===
MODEL_NAME = "microsoft/phi-1_5"  # if this is what you meant
MAX_LEN = 128

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token

def tokenize(example):
    return tokenizer(example["text"], padding="max_length", truncation=True, max_length=MAX_LEN)

tokenized_dataset = raw_dataset.map(tokenize, batched=True)

# === Load Model with 4-bit Quantization ===
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32,
    device_map="auto"
)


# === Add LoRA Adaptation ===
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# === Training Arguments ===
training_args = TrainingArguments(
    output_dir="tiny_mistral_chat_finetune",
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    save_steps=50,
    save_total_limit=2,
    logging_steps=10,
    learning_rate=2e-4,
    fp16=True,
    report_to="none",
    resume_from_checkpoint=True  # ← Resume if checkpoint exists
)

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    tokenizer=tokenizer,
    data_collator=data_collator
)

# === Train (resume if checkpoint exists) ===
trainer.train(resume_from_checkpoint=True)

# === Save Final Model ===
model.save_pretrained("tiny_mistral_chat_finetune")
tokenizer.save_pretrained("tiny_mistral_chat_finetune")

print("✅ Model trained and saved to 'tiny_mistral_chat_finetune'")
