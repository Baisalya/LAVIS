from jarvis_hud.main import update_hud_text

def show_fallback_in_hud(content: str, typing: bool = True):
    if not content or len(content.strip()) < 5:
        return
    try:
        trimmed = content.strip()
        update_hud_text("📄 " + trimmed, category="reply", typing=typing)
    except Exception as e:
        print(f"[HUD Display Error] {e}")

def show_hud_reply(message: str, emoji: str = "", typing: bool = True):
    try:
        formatted = f"{emoji} {message}".strip()
        update_hud_text(formatted, category="reply", typing=typing)
    except Exception as e:
        print(f"[HUD Text Error] {e}")

def show_hud_command(text: str, typing: bool = True):
    try:
        update_hud_text(text, category="command", typing=typing)
    except Exception as e:
        print(f"[HUD Command Error] {e}")

def show_hud_error(message: str, typing: bool = True):
    try:
        update_hud_text(message, category="error", typing=typing)
    except Exception as e:
        print(f"[HUD Error Display Failed] {e}")
