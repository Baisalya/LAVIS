import pyautogui
import time
import subprocess

def open_browser_and_search(query):
    subprocess.Popen(['start', '', 'chrome'], shell=True)
    time.sleep(3)
    pyautogui.hotkey('ctrl', 'l')
    pyautogui.write(query)
    pyautogui.press('enter')
