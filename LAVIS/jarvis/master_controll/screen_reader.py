import pytesseract
from PIL import ImageGrab

def find_text_on_screen(target_text):
    image = ImageGrab.grab()
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data["text"]):
        if target_text.lower() in text.lower():
            x = data["left"][i]
            y = data["top"][i]
            return x + 10, y + 10
    return None
