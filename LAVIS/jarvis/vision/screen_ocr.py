import pytesseract
import pyautogui
from PIL import Image
    
# Update this path if Tesseract is in a different location
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def get_screen_text():
    screenshot = pyautogui.screenshot()
    return pytesseract.image_to_string(screenshot)

def click_on_text(target_text):
    screenshot = pyautogui.screenshot()
    boxes = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

    for i in range(len(boxes['text'])):
        if target_text.lower() in boxes['text'][i].lower():
            x, y = boxes['left'][i], boxes['top'][i]
            pyautogui.moveTo(x + 10, y + 10)
            pyautogui.click()
            return True
    return False
