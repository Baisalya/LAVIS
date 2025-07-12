import pyautogui

def scroll_down():
    pyautogui.scroll(-500)

def type_text(text):
    pyautogui.write(text)

def click_position(x, y):
    pyautogui.click(x, y)
