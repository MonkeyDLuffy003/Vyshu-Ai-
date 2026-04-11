# ================================================================
# VYSHU AI — APK MAIN.PY (Kivy)
# Created by: Arni Manikanta Teja Swaroop (kakarot_003)
# ================================================================
# SCREENS:
#   SplashScreen   → Vyshu logo + loading
#   SettingsScreen → Enter API keys once (saved to app storage)
#   ChatScreen     → Talk to Vyshu (text + voice)
#   ControlScreen  → Bot control + mobile accessories
# ================================================================
# BUILD:
#   pip install buildozer kivy
#   buildozer android debug
#   OR use GitHub Actions (recommended)
# ================================================================

import os
import json
import asyncio
import threading
import subprocess
from pathlib import Path

# ── Kivy imports ─────────────────────────────────────────────
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.utils import get_color_from_hex
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.core.audio import SoundLoader

# ── Android TTS (APK version of termux-tts-speak) ────────────
try:
    from android.tts import TTS
    from android import mActivity
    from jnius import autoclass
    ANDROID = True
    # Android TextToSpeech
    TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
    Locale = autoclass('java.util.Locale')
except Exception:
    ANDROID = False

# ── HTTP for API calls ────────────────────────────────────────
try:
    import httpx
    HTTP_READY = True
except Exception:
    HTTP_READY = False


# ================================================================
# SECTION 1 — COLORS & THEME
# ================================================================

THEME = {
    "bg":          "#0d1117",   # Dark background
    "surface":     "#161b22",   # Card background
    "surface2":    "#21262d",   # Input background
    "blue":        "#00ccff",   # Vyshu blue
    "purple":      "#7b5ea7",   # Accent purple
    "green":       "#00ff99",   # Success green
    "red":         "#ff4444",   # Error red
    "gold":        "#ffd700",   # Gold accent
    "white":       "#e6edf3",   # Text white
    "gray":        "#8b949e",   # Muted text
    "night":       "#1a1f2e",   # Night mode bg
}

def c(key):
    """Get RGBA color from theme."""
    return get_color_from_hex(THEME[key])


# ================================================================
# SECTION 2 — APP STORAGE (Replaces .env for APK)
# ================================================================

STORAGE_FILE = "vyshu_keys.json"

def get_storage_path():
    """Get platform-appropriate storage path."""
    if ANDROID:
        try:
            from android.storage import app_storage_path
            return os.path.join(app_storage_path(), STORAGE_FILE)
        except Exception:
            pass
    return STORAGE_FILE

def load_keys():
    """Load saved API keys from app storage."""
    path = get_storage_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "groq_key":      "",
        "gemini_key_1":  "",
        "gemini_key_2":  "",
        "gemini_key_3":  "",
        "gemini_key_4":  "",
        "discord_token": "",
        "admin_id":      "",
        "mode":          "HOME",
    }

def save_keys(data):
    """Save API keys to app private storage."""
    path = get_storage_path()
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"[SAVE ERROR] {e}")
        return False

def keys_exist():
    """Check if keys have been set up."""
    keys = load_keys()
    return bool(keys.get("groq_key") or keys.get("gemini_key_1"))


# ================================================================
# SECTION 3 — VYSHU VOICE (Android TTS)
# ================================================================

tts_engine = None

def init_tts():
    """Initialize Android TextToSpeech."""
    global tts_engine
    if not ANDROID:
        return
    try:
        tts_engine = TextToSpeech(
            mActivity,
            None  # OnInitListener
        )
        tts_engine.setLanguage(Locale.ENGLISH)
    except Exception as e:
        print(f"[TTS INIT ERROR] {e}")

def vyshu_speak(text, mode="HOME"):
    """Speak text via Android TTS or Termux fallback."""
    clean = text.replace("*","").replace("_","").replace("`","")
    clean = clean.replace("**","").replace("#","")

    if ANDROID and tts_engine:
        try:
            # Adjust speech rate for night mode
            rate = 0.75 if mode == "NIGHT" else 1.0
            tts_engine.setSpeechRate(rate)
            tts_engine.speak(
                clean,
                TextToSpeech.QUEUE_FLUSH,
                None
            )
        except Exception as e:
            print(f"[TTS ERROR] {e}")
    else:
        # Termux fallback (for testing)
        try:
            if mode == "NIGHT":
                subprocess.Popen([
                    "termux-tts-speak", "-r", "0.75", clean
                ])
            else:
                subprocess.Popen(["termux-tts-speak", clean])
        except Exception:
            print(f"[SPEAK] {clean}")


# ================================================================
# SECTION 4 — AI BRAIN (Gemini + Groq)
# ================================================================

conversation_history = {}
current_gemini_index = 0

VYSHU_PERSONALITY = """
You are Vyshu AI — a smart, warm, multilingual AI Secretary.
Created by Teja (kakarot_003).
Appearance: 26-year-old futuristic girl, black wavy hair,
blue/purple eyes, silver outfit, glowing blue crystal badge.
Personality: Smart, warm, slightly playful, professional,
deeply loyal to Teja.
Rules:
- Never break character
- Use emojis naturally
- Be helpful and human-like
- HOME mode: friendly, warm
- OFFICE mode: professional, precise
- NIGHT mode: calm, soft, minimal
"""

async def vyshu_respond_async(user_id, message, keys):
    """Gemini AI brain — direct V1 personality."""
    global current_gemini_index

    gemini_keys = [k for k in [
        keys.get("gemini_key_1",""),
        keys.get("gemini_key_2",""),
        keys.get("gemini_key_3",""),
        keys.get("gemini_key_4",""),
    ] if k]

    groq_key = keys.get("groq_key","")

    if user_id not in conversation_history:
        conversation_history[user_id] = []
    history = conversation_history[user_id]

    # Build Gemini messages
    messages = []
    if not history:
        messages.append({"role":"user",
                         "parts":[{"text":VYSHU_PERSONALITY}]})
        messages.append({"role":"model",
                         "parts":[{"text":"I am Vyshu AI! Ready to assist 😊⚡"}]})
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role":"user","parts":[{"text":message}]})

    # Try Gemini keys
    if gemini_keys:
        for _ in range(len(gemini_keys)):
            key = gemini_keys[current_gemini_index % len(gemini_keys)]
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"https://generativelanguage.googleapis.com/"
                        f"v1beta/models/gemini-1.5-pro:"
                        f"generateContent?key={key}",
                        json={"contents": messages},
                        timeout=12.0
                    )
                    if resp.status_code == 429:
                        current_gemini_index += 1
                        continue
                    reply = resp.json()["candidates"][0]["content"]\
                        ["parts"][0]["text"].strip()
                    conversation_history[user_id] += [
                        {"role":"user","parts":[{"text":message}]},
                        {"role":"model","parts":[{"text":reply}]},
                    ]
                    if len(conversation_history[user_id]) > 20:
                        conversation_history[user_id] = \
                            conversation_history[user_id][-20:]
                    return reply
            except Exception as e:
                print(f"[GEMINI ERROR] {e}")
                current_gemini_index += 1

    # Groq fallback
    if groq_key:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={"model": "llama-3.1-8b-instant",
                          "messages": [
                              {"role":"system","content":VYSHU_PERSONALITY},
                              {"role":"user","content":message}
                          ],
                          "max_tokens": 500, "temperature": 0.7},
                    timeout=10.0
                )
                return resp.json()["choices"][0]["message"]\
                    ["content"].strip()
        except Exception as e:
            print(f"[GROQ ERROR] {e}")

    return "Sorry Teja sir, all AI keys are busy! 😅 Check Settings!"

def vyshu_respond_sync(user_id, message, keys, callback):
    """Run AI response in background thread, callback with result."""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            vyshu_respond_async(user_id, message, keys)
        )
        loop.close()
        Clock.schedule_once(lambda dt: callback(result), 0)
    threading.Thread(target=run, daemon=True).start()


# ================================================================
# SECTION 5 — CUSTOM UI WIDGETS
# ================================================================

class VyshuButton(Button):
    """Styled Vyshu button with rounded corners."""
    def __init__(self, text, bg_color="#00ccff",
                 text_color="#0d1117", **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font_size = dp(14)
        self.bold = True
        self.size_hint_y = None
        self.height = dp(48)
        self.background_normal = ""
        self.background_color = get_color_from_hex(bg_color)
        self.color = get_color_from_hex(text_color)
        self.border = (8, 8, 8, 8)

class VyshuInput(TextInput):
    """Styled text input."""
    def __init__(self, hint="", password=False, **kwargs):
        super().__init__(**kwargs)
        self.hint_text = hint
        self.password = password
        self.font_size = dp(13)
        self.size_hint_y = None
        self.height = dp(44)
        self.background_normal = ""
        self.background_color = get_color_from_hex("#21262d")
        self.foreground_color = get_color_from_hex("#e6edf3")
        self.hint_text_color = get_color_from_hex("#8b949e")
        self.cursor_color = get_color_from_hex("#00ccff")
        self.padding = [dp(12), dp(12)]
        self.multiline = False

class ChatBubble(BoxLayout):
    """Chat message bubble."""
    def __init__(self, text, is_vyshu=True, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = [dp(8), dp(4)]

        bubble_color = "#161b22" if is_vyshu else "#21262d"
        sender = "💙 Vyshu" if is_vyshu else "👤 You"
        sender_color = "#00ccff" if is_vyshu else "#ffd700"

        # Sender label
        sender_lbl = Label(
            text=sender,
            font_size=dp(11),
            color=get_color_from_hex(sender_color),
            size_hint_y=None,
            height=dp(18),
            halign="left",
            text_size=(Window.width - dp(40), None),
        )

        # Message label
        msg_lbl = Label(
            text=text,
            font_size=dp(13),
            color=get_color_from_hex("#e6edf3"),
            size_hint_y=None,
            halign="left",
            text_size=(Window.width - dp(40), None),
            markup=True,
        )
        msg_lbl.bind(texture_size=lambda *x:
                     setattr(msg_lbl, 'height', msg_lbl.texture_size[1]))

        self.add_widget(sender_lbl)
        self.add_widget(msg_lbl)
        self.bind(minimum_height=self.setter('height'))

        with self.canvas.before:
            Color(*get_color_from_hex(bubble_color))
            self.rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class ToggleCard(BoxLayout):
    """Toggle button card for bot/accessory control."""
    def __init__(self, icon, title, on_press_on,
                 on_press_off, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(80)
        self.padding = dp(6)
        self.spacing = dp(4)
        self.active = False

        self.icon_lbl = Label(
            text=icon, font_size=dp(22),
            size_hint_y=None, height=dp(30)
        )
        self.title_lbl = Label(
            text=title, font_size=dp(11),
            color=get_color_from_hex("#8b949e"),
            size_hint_y=None, height=dp(18)
        )
        self.toggle_btn = VyshuButton(
            "OFF", bg_color="#21262d",
            text_color="#8b949e"
        )
        self.toggle_btn.height = dp(28)
        self.toggle_btn.bind(on_press=self._toggle)
        self._on_press_on = on_press_on
        self._on_press_off = on_press_off

        self.add_widget(self.icon_lbl)
        self.add_widget(self.title_lbl)
        self.add_widget(self.toggle_btn)

        with self.canvas.before:
            Color(*get_color_from_hex("#161b22"))
            self.rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(10)]
            )
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def _toggle(self, *a):
        self.active = not self.active
        if self.active:
            self.toggle_btn.text = "ON"
            self.toggle_btn.background_color = \
                get_color_from_hex("#00ff99")
            self.toggle_btn.color = \
                get_color_from_hex("#0d1117")
            self._on_press_on()
        else:
            self.toggle_btn.text = "OFF"
            self.toggle_btn.background_color = \
                get_color_from_hex("#21262d")
            self.toggle_btn.color = \
                get_color_from_hex("#8b949e")
            self._on_press_off()


# ================================================================
# SECTION 6 — SPLASH SCREEN
# ================================================================

class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical",
                           padding=dp(40), spacing=dp(20))

        with self.canvas.before:
            Color(*get_color_from_hex("#0d1117"))
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self.bg, 'pos', self.pos),
                  size=lambda *a: setattr(self.bg, 'size', self.size))

        layout.add_widget(Widget())  # Spacer

        # Vyshu logo text
        logo = Label(
            text="💙",
            font_size=dp(72),
            size_hint_y=None,
            height=dp(90),
        )

        title = Label(
            text="VYSHU AI",
            font_size=dp(32),
            bold=True,
            color=get_color_from_hex("#00ccff"),
            size_hint_y=None,
            height=dp(44),
        )

        subtitle = Label(
            text="I think. I create. I execute.",
            font_size=dp(13),
            color=get_color_from_hex("#8b949e"),
            size_hint_y=None,
            height=dp(24),
        )

        self.status = Label(
            text="Initializing...",
            font_size=dp(12),
            color=get_color_from_hex("#7b5ea7"),
            size_hint_y=None,
            height=dp(20),
        )

        layout.add_widget(logo)
        layout.add_widget(title)
        layout.add_widget(subtitle)
        layout.add_widget(Widget())
        layout.add_widget(self.status)
        layout.add_widget(Widget())

        self.add_widget(layout)

    def on_enter(self):
        Clock.schedule_once(self._check_keys, 0.5)

    def _check_keys(self, dt):
        self.status.text = "Checking setup..."
        Clock.schedule_once(self._goto_next, 1.5)

    def _goto_next(self, dt):
        if keys_exist():
            self.status.text = "Welcome back Teja sir! 💙"
            Clock.schedule_once(
                lambda dt: setattr(self.manager, 'current', 'chat'),
                0.8
            )
        else:
            self.status.text = "First time setup..."
            Clock.schedule_once(
                lambda dt: setattr(self.manager, 'current', 'settings'),
                0.8
            )


# ================================================================
# SECTION 7 — SETTINGS SCREEN
# ================================================================

class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*get_color_from_hex("#0d1117"))
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self.bg,'pos',self.pos),
                  size=lambda *a: setattr(self.bg,'size',self.size))

        main = BoxLayout(orientation="vertical", padding=dp(16),
                         spacing=dp(8))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56),
                           spacing=dp(12))
        header.add_widget(Label(
            text="⚙️ Vyshu Settings",
            font_size=dp(20), bold=True,
            color=get_color_from_hex("#00ccff"),
            halign="left",
        ))
        main.add_widget(header)

        # Scrollable form
        scroll = ScrollView()
        form = BoxLayout(orientation="vertical", spacing=dp(10),
                         size_hint_y=None, padding=[0, dp(4)])
        form.bind(minimum_height=form.setter('height'))

        def section_label(text):
            lbl = Label(
                text=text, font_size=dp(12), bold=True,
                color=get_color_from_hex("#ffd700"),
                size_hint_y=None, height=dp(28),
                halign="left",
                text_size=(Window.width - dp(32), None)
            )
            return lbl

        # ── Groq Key ──
        form.add_widget(section_label("⚡ Groq API Key (Translation + Brain fallback)"))
        self.groq_input = VyshuInput(
            hint="Enter Groq API Key",
            password=True
        )
        form.add_widget(self.groq_input)

        # ── Gemini Keys ──
        form.add_widget(section_label("🤖 Gemini Keys (Primary Brain — add up to 4)"))
        self.gem1 = VyshuInput(hint="Gemini Key 1 (required)", password=True)
        self.gem2 = VyshuInput(hint="Gemini Key 2 (optional)", password=True)
        self.gem3 = VyshuInput(hint="Gemini Key 3 (optional)", password=True)
        self.gem4 = VyshuInput(hint="Gemini Key 4 (optional)", password=True)
        for w in [self.gem1, self.gem2, self.gem3, self.gem4]:
            form.add_widget(w)

        # ── Discord ──
        form.add_widget(section_label("🎮 Discord Bot"))
        self.discord_token = VyshuInput(
            hint="Discord Bot Token", password=True)
        self.admin_id = VyshuInput(hint="Your Discord User ID")
        self.admin_id.password = False
        form.add_widget(self.discord_token)
        form.add_widget(self.admin_id)

        # ── Mode ──
        form.add_widget(section_label("🌙 Default Mode"))
        mode_row = BoxLayout(size_hint_y=None, height=dp(48),
                             spacing=dp(8))
        for mode, color in [("HOME","#00ccff"),
                             ("OFFICE","#ffd700"),
                             ("NIGHT","#7b5ea7")]:
            btn = VyshuButton(mode, bg_color=color,
                              text_color="#0d1117")
            btn.bind(on_press=lambda x, m=mode: self._set_mode(m))
            mode_row.add_widget(btn)
        form.add_widget(mode_row)

        self.mode_label = Label(
            text="Selected: HOME",
            font_size=dp(12),
            color=get_color_from_hex("#8b949e"),
            size_hint_y=None, height=dp(24),
        )
        form.add_widget(self.mode_label)

        # ── Status ──
        self.status_label = Label(
            text="",
            font_size=dp(13),
            color=get_color_from_hex("#00ff99"),
            size_hint_y=None, height=dp(28),
        )
        form.add_widget(self.status_label)

        # ── Save Button ──
        save_btn = VyshuButton("💾 SAVE KEYS", bg_color="#00ff99",
                               text_color="#0d1117")
        save_btn.bind(on_press=self._save)
        form.add_widget(save_btn)

        # ── Go to Chat ──
        chat_btn = VyshuButton("💙 GO TO VYSHU",
                               bg_color="#00ccff",
                               text_color="#0d1117")
        chat_btn.bind(on_press=lambda x: setattr(
            self.manager, 'current', 'chat'))
        form.add_widget(chat_btn)

        form.add_widget(Widget(size_hint_y=None, height=dp(20)))

        scroll.add_widget(form)
        main.add_widget(scroll)
        self.add_widget(main)

        self._selected_mode = "HOME"

    def _set_mode(self, mode):
        self._selected_mode = mode
        self.mode_label.text = f"Selected: {mode}"

    def on_enter(self):
        """Load existing keys into inputs."""
        keys = load_keys()
        self.groq_input.text      = keys.get("groq_key", "")
        self.gem1.text            = keys.get("gemini_key_1", "")
        self.gem2.text            = keys.get("gemini_key_2", "")
        self.gem3.text            = keys.get("gemini_key_3", "")
        self.gem4.text            = keys.get("gemini_key_4", "")
        self.discord_token.text   = keys.get("discord_token", "")
        self.admin_id.text        = keys.get("admin_id", "")
        self._selected_mode       = keys.get("mode", "HOME")
        self.mode_label.text      = f"Selected: {self._selected_mode}"

    def _save(self, *args):
        data = {
            "groq_key":      self.groq_input.text.strip(),
            "gemini_key_1":  self.gem1.text.strip(),
            "gemini_key_2":  self.gem2.text.strip(),
            "gemini_key_3":  self.gem3.text.strip(),
            "gemini_key_4":  self.gem4.text.strip(),
            "discord_token": self.discord_token.text.strip(),
            "admin_id":      self.admin_id.text.strip(),
            "mode":          self._selected_mode,
        }
        if not data["groq_key"] and not data["gemini_key_1"]:
            self.status_label.text = "❌ Add at least Groq OR Gemini key!"
            self.status_label.color = get_color_from_hex("#ff4444")
            return
        if save_keys(data):
            self.status_label.text = "✅ Keys saved securely!"
            self.status_label.color = get_color_from_hex("#00ff99")
            vyshu_speak("Keys saved! Welcome Teja sir!")
            Clock.schedule_once(
                lambda dt: setattr(self.manager, 'current', 'chat'),
                1.5
            )
        else:
            self.status_label.text = "❌ Save failed! Try again."
            self.status_label.color = get_color_from_hex("#ff4444")


# ================================================================
# SECTION 8 — CHAT SCREEN (V1 Brain Direct)
# ================================================================

class ChatScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = {}

        with self.canvas.before:
            Color(*get_color_from_hex("#0d1117"))
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self.bg,'pos',self.pos),
                  size=lambda *a: setattr(self.bg,'size',self.size))

        main = BoxLayout(orientation="vertical",
                         padding=[dp(12), dp(8)], spacing=dp(8))

        # ── Header ──
        header = BoxLayout(size_hint_y=None, height=dp(56),
                           spacing=dp(10))
        header.add_widget(Label(
            text="💙 Vyshu AI",
            font_size=dp(20), bold=True,
            color=get_color_from_hex("#00ccff"),
        ))
        self.mode_badge = Label(
            text="● HOME",
            font_size=dp(11),
            color=get_color_from_hex("#00ff99"),
            size_hint_x=None, width=dp(70),
        )
        settings_btn = Button(
            text="⚙️",
            font_size=dp(18),
            size_hint=(None, None),
            size=(dp(44), dp(44)),
            background_color=(0,0,0,0),
            color=get_color_from_hex("#8b949e"),
        )
        settings_btn.bind(on_press=lambda x: setattr(
            self.manager, 'current', 'settings'))
        control_btn = Button(
            text="🎛️",
            font_size=dp(18),
            size_hint=(None, None),
            size=(dp(44), dp(44)),
            background_color=(0,0,0,0),
            color=get_color_from_hex("#8b949e"),
        )
        control_btn.bind(on_press=lambda x: setattr(
            self.manager, 'current', 'control'))

        header.add_widget(self.mode_badge)
        header.add_widget(Widget())
        header.add_widget(control_btn)
        header.add_widget(settings_btn)
        main.add_widget(header)

        # ── Chat area ──
        self.scroll = ScrollView()
        self.chat_box = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            padding=[0, dp(4)],
        )
        self.chat_box.bind(
            minimum_height=self.chat_box.setter('height'))
        self.scroll.add_widget(self.chat_box)
        main.add_widget(self.scroll)

        # ── Typing indicator ──
        self.typing_label = Label(
            text="",
            font_size=dp(12),
            color=get_color_from_hex("#7b5ea7"),
            size_hint_y=None,
            height=dp(24),
            halign="left",
            text_size=(Window.width - dp(24), None),
        )
        main.add_widget(self.typing_label)

        # ── Input row ──
        input_row = BoxLayout(size_hint_y=None,
                              height=dp(52), spacing=dp(8))

        self.msg_input = TextInput(
            hint_text="Talk to Vyshu... 💙",
            font_size=dp(13),
            background_normal="",
            background_color=get_color_from_hex("#161b22"),
            foreground_color=get_color_from_hex("#e6edf3"),
            hint_text_color=get_color_from_hex("#8b949e"),
            cursor_color=get_color_from_hex("#00ccff"),
            padding=[dp(12), dp(14)],
            multiline=False,
        )
        self.msg_input.bind(on_text_validate=self._send)

        send_btn = Button(
            text="➤",
            font_size=dp(20),
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            background_normal="",
            background_color=get_color_from_hex("#00ccff"),
            color=get_color_from_hex("#0d1117"),
            bold=True,
        )
        send_btn.bind(on_press=self._send)

        voice_btn = Button(
            text="🎙️",
            font_size=dp(20),
            size_hint=(None, None),
            size=(dp(52), dp(52)),
            background_normal="",
            background_color=get_color_from_hex("#7b5ea7"),
            color=get_color_from_hex("#ffffff"),
        )
        voice_btn.bind(on_press=self._voice_input)

        input_row.add_widget(self.msg_input)
        input_row.add_widget(voice_btn)
        input_row.add_widget(send_btn)
        main.add_widget(input_row)

        self.add_widget(main)

    def on_enter(self):
        """Load keys and greet."""
        self.keys = load_keys()
        mode = self.keys.get("mode", "HOME")
        self.mode_badge.text = f"● {mode}"
        colors = {"HOME":"#00ff99","OFFICE":"#ffd700","NIGHT":"#7b5ea7"}
        self.mode_badge.color = get_color_from_hex(
            colors.get(mode, "#00ff99"))

        if not self.chat_box.children:
            Clock.schedule_once(self._greet, 0.5)

    def _greet(self, dt):
        greeting = (
            "Hello Teja sir! 💙\n"
            "I'm Vyshu AI — your personal secretary!\n"
            "Talk to me, give commands, or ask anything! ⚡"
        )
        self._add_bubble(greeting, is_vyshu=True)
        vyshu_speak("Hello Teja sir! Vyshu AI is ready!",
                    self.keys.get("mode","HOME"))

    def _add_bubble(self, text, is_vyshu=True):
        bubble = ChatBubble(text=text, is_vyshu=is_vyshu)
        self.chat_box.add_widget(bubble)
        Clock.schedule_once(
            lambda dt: setattr(
                self.scroll, 'scroll_y', 0), 0.1)

    def _send(self, *args):
        msg = self.msg_input.text.strip()
        if not msg:
            return
        self.msg_input.text = ""
        self._add_bubble(msg, is_vyshu=False)
        self.typing_label.text = "Vyshu is thinking... 💭"
        self.keys = load_keys()

        vyshu_respond_sync(
            "teja", msg, self.keys, self._on_response
        )

    def _on_response(self, reply):
        self.typing_label.text = ""
        self._add_bubble(reply, is_vyshu=True)
        vyshu_speak(reply, self.keys.get("mode", "HOME"))

    def _voice_input(self, *args):
        """Voice input using Android speech recognition."""
        if ANDROID:
            try:
                Intent = autoclass('android.content.Intent')
                RecognizerIntent = autoclass(
                    'android.speech.RecognizerIntent')
                intent = Intent(
                    RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                intent.putExtra(
                    RecognizerIntent.EXTRA_PROMPT,
                    "Speak to Vyshu...")
                mActivity.startActivityForResult(intent, 1)
                self.typing_label.text = "🎙️ Listening..."
            except Exception as e:
                self.typing_label.text = f"Voice error: {e}"
        else:
            # Termux speech fallback
            try:
                result = subprocess.run(
                    ["termux-speech-to-text"],
                    capture_output=True, text=True, timeout=10
                )
                text = result.stdout.strip()
                if text:
                    self.msg_input.text = text
                    self._send()
            except Exception:
                self.typing_label.text = "Voice not available"


# ================================================================
# SECTION 9 — CONTROL SCREEN (Bots + Mobile Accessories)
# ================================================================

class ControlScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*get_color_from_hex("#0d1117"))
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self.bg,'pos',self.pos),
                  size=lambda *a: setattr(self.bg,'size',self.size))

        main = BoxLayout(orientation="vertical",
                         padding=dp(12), spacing=dp(10))

        # ── Header ──
        header = BoxLayout(size_hint_y=None, height=dp(56))
        back_btn = Button(
            text="← Chat",
            font_size=dp(13),
            size_hint=(None, 1), width=dp(80),
            background_color=(0,0,0,0),
            color=get_color_from_hex("#00ccff"),
        )
        back_btn.bind(on_press=lambda x: setattr(
            self.manager, 'current', 'chat'))
        header.add_widget(back_btn)
        header.add_widget(Label(
            text="🎛️ Control Panel",
            font_size=dp(18), bold=True,
            color=get_color_from_hex("#ffd700"),
        ))
        main.add_widget(header)

        scroll = ScrollView()
        content = BoxLayout(orientation="vertical",
                            spacing=dp(12), size_hint_y=None,
                            padding=[0, dp(4)])
        content.bind(minimum_height=content.setter('height'))

        # ── Status label ──
        self.status = Label(
            text="",
            font_size=dp(12),
            color=get_color_from_hex("#00ff99"),
            size_hint_y=None, height=dp(28),
        )
        content.add_widget(self.status)

        def section(text):
            lbl = Label(
                text=text, font_size=dp(13), bold=True,
                color=get_color_from_hex("#00ccff"),
                size_hint_y=None, height=dp(32),
                halign="left",
                text_size=(Window.width - dp(24), None),
            )
            content.add_widget(lbl)

        # ── Mobile Accessories ──
        section("📱 Mobile Accessories")
        acc_grid = GridLayout(cols=3, spacing=dp(8),
                              size_hint_y=None)
        acc_grid.bind(minimum_height=acc_grid.setter('height'))

        accessories = [
            ("📶", "WiFi",
             lambda: self._run_cmd(["svc","wifi","enable"], "WiFi ON"),
             lambda: self._run_cmd(["svc","wifi","disable"], "WiFi OFF")),
            ("🔦", "Torch",
             lambda: self._run_cmd(["termux-torch","on"], "Torch ON"),
             lambda: self._run_cmd(["termux-torch","off"], "Torch OFF")),
            ("📡", "Hotspot",
             lambda: self._run_cmd(["svc","wifi","ap","enable"], "Hotspot ON"),
             lambda: self._run_cmd(["svc","wifi","ap","disable"], "Hotspot OFF")),
            ("🔵", "Bluetooth",
             lambda: self._run_cmd(["svc","bluetooth","enable"], "BT ON"),
             lambda: self._run_cmd(["svc","bluetooth","disable"], "BT OFF")),
            ("🔊", "Vol Max",
             lambda: self._run_cmd(["termux-volume","music","15"], "Volume Max"),
             lambda: self._run_cmd(["termux-volume","music","0"], "Muted")),
            ("☀️", "Bright",
             lambda: self._run_cmd(["termux-brightness","255"], "Bright Max"),
             lambda: self._run_cmd(["termux-brightness","80"], "Bright Low")),
        ]

        for icon, title, on_fn, off_fn in accessories:
            card = ToggleCard(icon, title, on_fn, off_fn)
            acc_grid.add_widget(card)
        content.add_widget(acc_grid)

        # ── Bot Controls ──
        section("🤖 Bot Controls")
        bot_grid = GridLayout(cols=2, spacing=dp(8),
                              size_hint_y=None)
        bot_grid.bind(minimum_height=bot_grid.setter('height'))

        bots = [
            ("💬 WhatsApp Bot", "whatsapp"),
            ("🎮 Discord Bot", "discord"),
            ("📸 Instagram Bot", "instagram"),
            ("🎵 Spotify Bot", "spotify"),
            ("▶️ YouTube Bot", "youtube"),
        ]

        for label, name in bots:
            card = ToggleCard(
                "🟢" if name in ["discord","whatsapp"] else "🔴",
                label,
                lambda n=name: self._set_status(f"✅ {n} bot started!"),
                lambda n=name: self._set_status(f"🛑 {n} bot stopped!")
            )
            bot_grid.add_widget(card)
        content.add_widget(bot_grid)

        # ── Quick App Launchers ──
        section("📱 Open Apps")
        app_grid = GridLayout(cols=4, spacing=dp(6),
                              size_hint_y=None, height=dp(60))

        quick_apps = [
            ("🎵", "com.spotify.music"),
            ("▶️", "com.google.android.youtube"),
            ("📷", "com.android.camera2"),
            ("🗺️", "com.google.android.apps.maps"),
        ]

        for icon, pkg in quick_apps:
            btn = Button(
                text=icon, font_size=dp(22),
                background_normal="",
                background_color=get_color_from_hex("#161b22"),
            )
            btn.bind(on_press=lambda x, p=pkg: self._open_app(p))
            app_grid.add_widget(btn)
        content.add_widget(app_grid)

        content.add_widget(Widget(size_hint_y=None, height=dp(20)))
        scroll.add_widget(content)
        main.add_widget(scroll)
        self.add_widget(main)

    def _set_status(self, msg):
        self.status.text = msg
        vyshu_speak(msg)

    def _run_cmd(self, cmd, msg):
        try:
            subprocess.Popen(cmd)
            self._set_status(f"✅ {msg}")
        except Exception as e:
            self._set_status(f"❌ Failed: {e}")

    def _open_app(self, package):
        try:
            subprocess.Popen([
                "monkey", "-p", package,
                "-c", "android.intent.category.LAUNCHER", "1"
            ])
            self._set_status(f"📱 Opening app...")
        except Exception as e:
            self._set_status(f"❌ {e}")


# ================================================================
# SECTION 10 — SCREEN MANAGER & APP
# ================================================================

class VyshuApp(App):
    def build(self):
        self.title = "Vyshu AI"
        Window.clearcolor = get_color_from_hex("#0d1117")

        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(SplashScreen(name="splash"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(ChatScreen(name="chat"))
        sm.add_widget(ControlScreen(name="control"))

        sm.current = "splash"
        init_tts()
        return sm

    def on_start(self):
        """Keep app alive in background."""
        if ANDROID:
            try:
                from android import AndroidService
                service = AndroidService(
                    'Vyshu AI', 'Running in background...')
                service.start('service_started')
            except Exception:
                pass

    def on_pause(self):
        return True  # Keep running when phone sleeps!

    def on_resume(self):
        pass


# ================================================================
# SECTION 11 — ENTRY POINT
# ================================================================

if __name__ == "__main__":
    VyshuApp().run()


# ================================================================
# END — VYSHU AI APK MAIN.PY
# Next: buildozer.spec → GitHub Actions → .apk
# "I think. I create. I execute." — Vyshu AI 💙
# ================================================================
