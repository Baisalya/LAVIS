# convert_t5_to_onnx.py

from transformers import T5Tokenizer
from optimum.exporters.onnx import main_export

# Output directory
onnx_path = "./LAVIS/t5-small-onnx"

# Export the model
main_export(
    model_name_or_path="t5-small",
    output=onnx_path,
    task="text2text-generation",
    framework="pt"
)

print("✅ t5-small model successfully exported to ONNX format at:", onnx_path)
#   