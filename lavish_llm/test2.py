import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Load model and tokenizer
MODEL_NAME = "microsoft/phi-1_5"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# Set the model to evaluation mode (faster inference)
model.eval()

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Function to ask a question
def ask_question(question, max_tokens=200):
    prompt = f"Question: {question}\nAnswer:"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_length=inputs.input_ids.shape[1] + max_tokens,
            temperature=0.7,
            do_sample=True,
            top_k=50,
            top_p=0.95,
            pad_token_id=tokenizer.eos_token_id
        )

    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return answer[len(prompt):].strip()  # remove prompt from output

# Example usage
question = "What is the capital of France?"
answer = ask_question(question)
print("Answer:", answer)
