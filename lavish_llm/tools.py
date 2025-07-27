import datetime
import webbrowser

def get_time():
    return f"The current time is {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."

def open_website(url):
    webbrowser.open(url)
    return f"Opening {url}"
