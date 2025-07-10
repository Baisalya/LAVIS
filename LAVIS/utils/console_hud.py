class ConsoleHUDController:
    def update(self, text, category="info", typing=False):
        print(f"[{category.upper()}] {text}")

    def speak(self, text, category="info", typing=False):
        self.update(text, category, typing)

    def type_live_text(self, partial_text: str):
        print(f"[LIVE INPUT] {partial_text}")

    def raw(self, text: str, replace_last=False):
        print(f"[RAW] {text}")

    def highlight(self, text: str):
        print(f"[HIGHLIGHT] {text}")
