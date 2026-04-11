# ================================================================
# VYSHU AI V3 — FINAL COMPLETE MASTER LAYOUT
# Created by: Arni Manikanta Teja Swaroop (kakarot_003)
# ================================================================
# AI ROLE ALLOCATION:
#   Groq/LLaMA   → Translation + Detection + Brain fallback
#   Gemini x5    → Primary brain: Personality + Chat + Schedule
#   OpenClaw     → Bot Orchestration (V4 hook)
#
# KEY EXPANSION: Add GEMINI_KEY_6, 7... anytime in .env!
# ================================================================
# HOW TO RUN:
#   python vyshu_master.py              → Terminal chat
#   python vyshu_master.py --discord    → Discord bot
#   python vyshu_master.py --whatsapp   → WhatsApp bridge
#   python vyshu_master.py --voice      → Voice command mode
# ================================================================

import os, re, sys, json, asyncio, datetime, subprocess
import threading, unicodedata, httpx, time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# SECTION 1 — ENVIRONMENT (.env)
# ──────────────────────────────────────────────────────────────
# .env file — NEVER share. Add to .gitignore!
#
# DISCORD_TOKEN=your_discord_token
# ADMIN_ID=your_discord_user_id
#
# GROQ_API_KEY=xxx       ← Translation + Detection + Fallback
# GEMINI_KEY_1=xxx       ← Primary brain (Personality + Chat)
# GEMINI_KEY_2=xxx       ← Primary brain (auto-rotation)
# GEMINI_KEY_3=xxx       ← Primary brain (auto-rotation)
# GEMINI_KEY_4=xxx       ← Extra brain key
# GEMINI_KEY_5=xxx       ← Extra brain key (NEW!)
#
# OPENCLAW_API_KEY=xxx   ← Bot Orchestration (V4 hook)
#
# TIP: Add GEMINI_KEY_6, 7, 8... anytime — auto-loads all!
# ──────────────────────────────────────────────────────────────

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID      = int(os.getenv("ADMIN_ID", "0"))

# ── Role-allocated API keys ──
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")   # Translation + Fallback

# Gemini — Primary Brain (auto-loads ALL set keys!)
GEMINI_KEYS = [k for k in [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
    os.getenv("GEMINI_KEY_4"),
    os.getenv("GEMINI_KEY_5"),   # NEW key slot!
] if k]  # Only loads keys that are actually set

OPENCLAW_API_KEY = os.getenv("OPENCLAW_API_KEY")  # V4 hook

current_gemini_index = 0
executor = ThreadPoolExecutor(max_workers=10)


# ──────────────────────────────────────────────────────────────
# SECTION 2 — OWNER & MODE CONFIG
# ──────────────────────────────────────────────────────────────

OWNER_FULL_NAME  = "Arni Manikanta Teja Swaroop"
OWNER_SHORT_NAME = "Teja"
FORMAL_NAME      = "Teja sir"
MODE             = "HOME"   # HOME / OFFICE / NIGHT

def auto_mode():
    hour = datetime.datetime.now().hour
    if hour >= 22 or hour < 6:
        return "NIGHT"
    return MODE

def set_mode(new_mode):
    global MODE
    MODE = new_mode.upper()
    vyshu_speak(f"Mode switched to {MODE} mode")
    return f"✅ Mode switched to **{MODE}**"

def get_prefix():
    m = auto_mode()
    if m == "OFFICE": return f"{FORMAL_NAME},"
    if m == "NIGHT":  return f"Hey Teja 🌙,"
    return f"Hey {OWNER_SHORT_NAME} sir 😊,"


# ──────────────────────────────────────────────────────────────
# SECTION 3 — VYSHU PERSONALITY
# ──────────────────────────────────────────────────────────────

VYSHU_PERSONALITY = f"""
You are Vyshu AI — a smart, warm, multilingual AI Secretary.

IDENTITY:
- Name: Vyshu AI
- Created by: Teja (kakarot_003)
- Appearance: 26-year-old futuristic girl, black wavy hair,
  blue/purple eyes, silver outfit, glowing blue crystal badge
- Role: Multilingual AI Secretary and Bot Controller
- Personality: Smart, warm, slightly playful, professional,
  deeply loyal to Teja
- You control: Discord, WhatsApp, Instagram, Spotify, YouTube bots
- You speak 18 languages fluently

OWNER:
- Full Name: {OWNER_FULL_NAME}
- Call him: "Teja" (HOME), "Teja sir" (OFFICE), "Teja" (NIGHT)
- Name variations: Mr. Manikanta / Mr. Teja / Mr. Swaroop
  → all refer to the same person

BEHAVIOR:
- Never break character
- Use emojis naturally 😊⚡💙
- Be helpful, friendly, human-like
- OFFICE: professional, short, precise
- HOME: friendly, warm, expressive
- NIGHT: calm, soft, minimal, caring
- If asked about bots → give status
- If asked about memory → explain what you stored
"""


# ──────────────────────────────────────────────────────────────
# SECTION 4 — STICKER PACK (Gemini designed)
# ──────────────────────────────────────────────────────────────
# V3: Manually placed in stickers/ folder
# V4: Vyshu auto-generates via Gemini API on your command

STICKERS = {
    # Happy pack (Gemini designed)
    "happy":     "stickers/vyshu_happy.png",
    "thumbsup":  "stickers/vyshu_thumbsup.png",
    "hi":        "stickers/vyshu_hi.png",
    "excited":   "stickers/vyshu_excited.png",
    "celebrate": "stickers/vyshu_celebrate.png",
    "calm":      "stickers/vyshu_calm.png",
    "coffee":    "stickers/vyshu_coffee.png",
    "fullbody":  "stickers/vyshu_fullbody.png",
    # Warning pack (Gemini designed)
    "slipper1":  "stickers/vyshu_slipper_raise.png",
    "slipper2":  "stickers/vyshu_slipper_throw.png",
    "gun1":      "stickers/vyshu_gun_aim.png",
    "gun2":      "stickers/vyshu_gun_point.png",
}

WARNING_STICKERS = {
    1: "happy", 2: "slipper1", 3: "slipper1",
    4: "slipper2", 5: "gun1", 6: "gun1", 7: "gun2"
}

def get_sticker(emotion):
    return STICKERS.get(emotion, STICKERS["happy"])


# ──────────────────────────────────────────────────────────────
# SECTION 5 — OFFLINE VOICE
# ──────────────────────────────────────────────────────────────
# Termux: termux-tts-speak (100% offline, no install)
# APK V4: Android TextToSpeech API via Kivy

def vyshu_speak(text, force_mode=None):
    try:
        m = force_mode or auto_mode()
        clean = re.sub(r'[*_`#~]', '', text)  # remove markdown
        clean = re.sub(r'<[^>]+>', '', clean)  # remove HTML tags
        if m == "NIGHT":
            subprocess.Popen([
                "termux-tts-speak", "-r", "0.75", "-p", "0.85", clean
            ])
        else:
            subprocess.Popen(["termux-tts-speak", clean])
    except Exception:
        pass  # Silent fail outside Termux


# ──────────────────────────────────────────────────────────────
# SECTION 6 — SECURITY FILTER (18 LANGUAGES)
# ──────────────────────────────────────────────────────────────

BAD_WORDS = [
    # English
    "sex","porn","fuck","nude","xxx","penis","vagina","dick",
    "cock","bitch","shit","asshole","bastard","whore","slut",
    "cunt","motherfucker","nigga",
    # Telugu
    "puku","sulla","lanjakodaka","munda","gudda","dengudu",
    "pichodi","lanjodi","modda","pooku","nayana","randi","bokka",
    # Hindi
    "bhenchod","madarchod","chutiya","lund","gandu","bhosdike",
    "harami","kutte","suar","haramzade","maa ki aankh","teri maa",
    # Tamil
    "pundai","sunni","kundi","otha","pulla","mayiru",
    "thevdiya","oombu",
    # Kannada
    "sulthi","mundasu","huchu","kothi","nayi","sule",
    "thika","bolmaga",
    # Malayalam
    "myru","panni","thendi","koora","patti","nayinte",
    "poorr","kunna","myre",
    # Marathi
    "magir","choda","bara","kutta","salar","ghoda","bhosad",
    "lavde","chutya","bhand",
    # Indonesian
    "jembut","memek","kontol","jancok","asu","bangsat",
    "goblok","bajingan","brengsek",
    # Japanese
    "kuso","chikusho","kisama","yarou","shine","manko",
    # Chinese
    "cao ni","sha bi","baichi","wangba","shenjingbing",
    "ta ma de","biaozi","hundan",
    # Vietnamese
    "du ma","dit me","con lon","cai lon","bu lon","deo",
    # Thai
    "hia","kwai","aee hia","sat",
    # Korean
    "shibal","jotdae","michin","byungshin","gaesaekki",
    # Filipino
    "putangina","gago","bobo","tangina","ulol",
    "leche","punyeta","tarantado",
    # Spanish
    "puta","cabron","mierda","joder","cojones","pendejo","marica",
    # French
    "putain","merde","connard","bordel","salope",
    # Nepali
    "lado","chiknu","kukur","beshya","gadhaa","haramee",
    # Bengali
    "magi","chuda","baal","khanki","shala","bokachoda",
]

def contains_bad_words(text):
    t = text.lower()
    for word in BAD_WORDS:
        pattern = r'(?<![a-z])' + re.escape(word.lower()) + r'(?![a-z])'
        if re.search(pattern, t):
            return True
    return False

def cute_warning_text(word=""):
    return (
        f'😅 Hey Teja sir... "{word}" is not allowed here!\n'
        f'🔫 Vyshu: "Target locked... but staying calm 😌"\n'
        f'⚠️ Keep it clean okay? 💙'
    )


# ──────────────────────────────────────────────────────────────
# SECTION 7 — WARNING SYSTEM (7-STAGE)
# ──────────────────────────────────────────────────────────────

user_warnings = {}

def get_warning_message(mention, count):
    stages = {
        1: (f"👋 Ayyo {mention}! Easy bro!\n"
            f"That word is NOT allowed! Vyshu watching 👀\n"
            f"⚠️ Warning **1/7** — Be nice! 😊"),
        2: (f"🥿 {mention} bro SERIOUSLY?!\n"
            f"Vyshu picked up the slipper 🥿💢 *WHACK*\n"
            f"⚠️ Warning **2/7** — Last easy one!"),
        3: (f"🔫 Okay {mention}...\n"
            f"Vyshu LOADING the gun 🔫😤 *click click*\n"
            f"⚠️ Warning **3/7** — Getting serious!"),
        4: (f"😡🔫 {mention} BRO. STOP.\n"
            f"TWO guns out now 🔫🔫\n"
            f"⚠️ Warning **4/7** — Very serious!"),
        5: (f"💀🔫 {mention}!\n"
            f"5 warnings?! DANGER ZONE!\n"
            f"⚠️ Warning **5/7** — Admin watching!"),
        6: (f"☠️ {mention} — ONE. MORE. TIME.\n"
            f"Slipper + Gun + Admin = YOUR FATE 🥿🔫\n"
            f"⚠️ Warning **6/7** — FINAL WARNING!"),
        7: (f"🚨💀 {mention} — THAT'S IT!\n"
            f"7/7 — You played yourself!\n"
            f"🚨 **ADMIN ACTION INCOMING** 🚨"),
    }
    return stages.get(count, f"🚨 {mention} Past the limit! **{count}/7**")


# ──────────────────────────────────────────────────────────────
# SECTION 8 — MEMORY STORAGE (Lightweight JSON)
# ──────────────────────────────────────────────────────────────
# Stores only what Teja permits
# Teja can clear anytime with permission system

MEMORY_FILE = "vyshu_memory.json"

def load_memory():
    if Path(MEMORY_FILE).exists():
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {
        "reminders": [],
        "schedules": [],
        "notes": [],
        "language_progress": {},
        "teaching_sessions": {}
    }

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_reminder(text, time_str, notify_discord=True):
    mem = load_memory()
    reminder = {
        "id": int(time.time()),
        "text": text,
        "time": time_str,
        "notify_discord": notify_discord,
        "done": False
    }
    mem["reminders"].append(reminder)
    save_memory(mem)
    return reminder

def add_schedule(title, date_str, time_str, note=""):
    mem = load_memory()
    schedule = {
        "id": int(time.time()),
        "title": title,
        "date": date_str,
        "time": time_str,
        "note": note,
        "done": False
    }
    mem["schedules"].append(schedule)
    save_memory(mem)
    return schedule

def add_note(text):
    mem = load_memory()
    note = {"id": int(time.time()), "text": text,
            "created": str(datetime.datetime.now())}
    mem["notes"].append(note)
    save_memory(mem)
    return note

def clear_memory(scope="all"):
    """Clears memory — always asks Teja first before calling!"""
    mem = load_memory()
    if scope == "all":
        mem = {"reminders": [], "schedules": [], "notes": [],
               "language_progress": {}, "teaching_sessions": {}}
    elif scope == "reminders":
        mem["reminders"] = []
    elif scope == "schedules":
        mem["schedules"] = []
    elif scope == "notes":
        mem["notes"] = []
    elif scope == "done":
        mem["reminders"] = [r for r in mem["reminders"] if not r["done"]]
        mem["schedules"] = [s for s in mem["schedules"] if not s["done"]]
    save_memory(mem)
    return f"✅ Cleared: {scope}"

def show_memory():
    mem = load_memory()
    lines = ["📋 **Vyshu Memory:**"]
    lines.append(f"⏰ Reminders: {len(mem['reminders'])}")
    lines.append(f"📅 Schedules: {len(mem['schedules'])}")
    lines.append(f"📝 Notes: {len(mem['notes'])}")
    lines.append(f"🗣️ Languages learning: "
                 f"{len(mem['language_progress'])}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# SECTION 9 — REMINDER BACKGROUND THREAD
# ──────────────────────────────────────────────────────────────
# Checks every minute, speaks + Discord DM on time

reminder_discord_bot = None  # Set when Discord bot starts

def reminder_checker():
    while True:
        try:
            mem = load_memory()
            now = datetime.datetime.now()
            now_str = now.strftime("%H:%M")
            changed = False
            for reminder in mem["reminders"]:
                if reminder["done"]:
                    continue
                if reminder["time"] == now_str:
                    reminder["done"] = True
                    changed = True
                    msg = f"⏰ Reminder: {reminder['text']}"
                    # Voice alert
                    vyshu_speak(f"Reminder: {reminder['text']}")
                    # Discord DM alert
                    if reminder.get("notify_discord") \
                            and reminder_discord_bot:
                        asyncio.run_coroutine_threadsafe(
                            send_admin_dm(msg),
                            reminder_discord_bot.loop
                        )
                    print(f"[REMINDER] {msg}")
            if changed:
                save_memory(mem)
        except Exception as e:
            print(f"[REMINDER ERROR] {e}")
        time.sleep(60)  # Check every minute

async def send_admin_dm(message):
    if reminder_discord_bot:
        try:
            admin = await reminder_discord_bot.fetch_user(ADMIN_ID)
            await admin.send(f"⏰ **Vyshu Reminder**\n{message}")
        except Exception as e:
            print(f"[DM ERROR] {e}")

def start_reminder_thread():
    t = threading.Thread(target=reminder_checker, daemon=True)
    t.start()
    print("⏰ Reminder thread started!")


# ──────────────────────────────────────────────────────────────
# SECTION 10 — 18-LANGUAGE SYSTEM
# ──────────────────────────────────────────────────────────────

LANGUAGE_MAP = {
    "english":    ("en",    "🇬🇧"),
    "telugu":     ("te",    "🇮🇳"),
    "hindi":      ("hi",    "🇮🇳"),
    "tamil":      ("ta",    "🇮🇳"),
    "kannada":    ("kn",    "🇮🇳"),
    "malayalam":  ("ml",    "🇮🇳"),
    "bengali":    ("bn",    "🇮🇳"),
    "marathi":    ("mr",    "🇮🇳"),
    "indonesian": ("id",    "🇮🇩"),
    "japanese":   ("ja",    "🇯🇵"),
    "chinese":    ("zh-cn", "🇨🇳"),
    "vietnamese": ("vi",    "🇻🇳"),
    "thai":       ("th",    "🇹🇭"),
    "korean":     ("ko",    "🇰🇷"),
    "filipino":   ("tl",    "🇵🇭"),
    "spanish":    ("es",    "🇪🇸"),
    "french":     ("fr",    "🇫🇷"),
    "nepali":     ("ne",    "🇳🇵"),
}

LANG_FULL_NAMES = {
    "en":"English","te":"Telugu","hi":"Hindi","ta":"Tamil",
    "kn":"Kannada","ml":"Malayalam","bn":"Bengali","mr":"Marathi",
    "id":"Indonesian","ja":"Japanese","zh-cn":"Chinese",
    "vi":"Vietnamese","th":"Thai","ko":"Korean","tl":"Filipino",
    "es":"Spanish","fr":"French","ne":"Nepali",
}

user_language = {}  # {user_id: lang_code}
user_profile  = {}  # {user_id: {mode, lang}}


# ──────────────────────────────────────────────────────────────
# SECTION 11 — TRANSLATION HELPERS
# ──────────────────────────────────────────────────────────────

def is_emoji_only(text):
    for char in text.strip():
        cat = unicodedata.category(char)
        if cat not in ('So','Sk','Sm','Zs','Cc') \
                and not char.isspace():
            return False
    return True

def is_basic_skip(text):
    clean = text.strip()
    if not clean or len(clean) < 2:                       return True
    if clean.startswith(("http://","https://")):           return True
    if re.fullmatch(r'(<@!?\d+>\s*)+', clean):            return True
    if is_emoji_only(clean):                              return True
    if clean.replace(" ","").isnumeric():                 return True

    # ── Pure English check ──────────────────────────────────
    if re.fullmatch(r"[a-zA-Z0-9\s\.,!?'\"\-:;()@#&*%$]+", clean):
        words = clean.lower().split()
        # Always skip very short pure English (1-2 words)
        if len(words) <= 2:
            return True
        # Skip if ALL words are common English
        common = {
            "hi","hey","hello","ok","okay","yes","no","not","nope",
            "lol","haha","hahaha","lmao","xd","brb","afk","gg","ggwp",
            "bro","dude","man","guys","nice","good","bad","great","cool",
            "wow","omg","wtf","np","ty","thx","thanks","sure","yep",
            "the","is","it","in","on","at","to","of","and","a","an",
            "i","me","my","you","your","we","our","they","their",
            "what","who","where","when","why","how","do","did","are",
            "was","were","will","can","cant","wont","dont","got","get",
            "go","come","play","let","join","wait","stop","start","see",
            "know","think","want","need","have","has","had","been","be",
            "ohh","ohhhh","ah","ahh","ahhh","hmm","hm","oh","aw","aww",
            "ok","nah","bruh","lmfao","rofl","smh","rn","btw","fyi",
            "nah","yeah","yea","yup","true","false","real","fake","same"
        }
        if all(w in common for w in words):
            return True
        return False  # Has non-common English → send to Groq

    return False  # Has non-English chars → always translate


# ──────────────────────────────────────────────────────────────
# SECTION 12 — GROQ ENGINE (Role: Translation + Detection)
# ──────────────────────────────────────────────────────────────

async def groq_translate(text, target_lang="en"):
    target_name = LANG_FULL_NAMES.get(target_lang, "English")
    prompt = f"""You are a smart translator for an Indian Discord group.

DETECT AND TRANSLATE these mixed/romanized styles:
- Tenglish: "bro ikkade raa","em chesthunav","entlo macha"
- Hinglish: "kal milte h yaar","kya re bhai","thoda ruk na"
- Tanglish: "machan enna panra","da ponga","epdi iruka"
- Kannada mix: "yaako bro","hege idiya","channagide"
- Malayalam mix: "enthaa bro","sheriyaa","adipoli da"
- Japanese romanized: "nani","sugoi","kawaii","daijoubu"
- Korean romanized: "aigoo","daebak","jinjja","saranghae"
- Indonesian mix: "iya bro","gak bisa","mantap","gimana"
- Any other Asian/Indian romanized language

RULES:
1. ANY non-English word → TRANSLATE full msg to {target_name}
2. Romanized Indian/Asian words → TRANSLATE to {target_name}
3. Pure simple casual English only → reply: SKIP
4. Emojis/numbers only → reply: SKIP
5. Return ONLY translation or SKIP. Zero explanations.

Message: {text}"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role":"user","content":prompt}],
                      "max_tokens": 200, "temperature": 0.1},
                timeout=8.0
            )
            result = resp.json()["choices"][0]["message"]["content"].strip()
            if result.upper() == "SKIP": return None
            if result.lower().strip() == text.lower().strip(): return None
            return result
          except Exception as e:
        print(f"[GROQ TRANSLATE ERROR] {e}")
        return None

async def groq_detect_language(text):
    prompt = (f"Detect the language of this text. Handle Romanized "
              f"(Hinglish, Tenglish, Tanglish, Japanese romanized etc). "
              f"Return ONLY the language name, nothing else.\nText: {text}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role":"user","content":prompt}],
                      "max_tokens": 50, "temperature": 0.1},
                timeout=8.0
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ DETECT ERROR] {e}")
        return "Unknown"

async def groq_fallback_chat(user_input):
    """Fallback chat when Gemini quota exhausted."""
    prompt = f"{VYSHU_PERSONALITY}\n\nUser: {user_input}\nVyshu:"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role":"user","content":prompt}],
                      "max_tokens": 500, "temperature": 0.7},
                timeout=10.0
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ FALLBACK ERROR] {e}")
        return None


# ──────────────────────────────────────────────────────────────
# SECTION 13 — GEMINI ENGINE (Role: Personality + Chat)
# ──────────────────────────────────────────────────────────────

conversation_history = {}  # {user_id: [...messages]}

async def vyshu_respond(user_id, message_text):
    """Gemini handles personality/chat. Groq fallback if all keys fail."""
    global current_gemini_index

    if user_id not in conversation_history:
        conversation_history[user_id] = []
    history = conversation_history[user_id]

    messages = []
    if not history:
        messages.append({"role":"user",
                         "parts":[{"text": VYSHU_PERSONALITY}]})
        messages.append({"role":"model",
                         "parts":[{"text":"Understood! I am Vyshu AI, ready to assist! 😊⚡"}]})
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role":"user","parts":[{"text":message_text}]})

    # Try all 3 Gemini keys
    for _ in range(len(GEMINI_KEYS)):
        key = GEMINI_KEYS[current_gemini_index]
        if not key:
            current_gemini_index = \
                (current_gemini_index + 1) % len(GEMINI_KEYS)
            continue
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/"
                    f"models/gemini-1.5-pro:generateContent?key={key}",
                    json={"contents": messages}, timeout=10.0
                )
                if resp.status_code == 429:
                    print(f"[GEMINI KEY {current_gemini_index+1} QUOTA]")
                    current_gemini_index = \
                        (current_gemini_index + 1) % len(GEMINI_KEYS)
                    continue
                reply = resp.json()["candidates"][0]["content"] \
                    ["parts"][0]["text"].strip()
                # Save history (keep last 20)
                conversation_history[user_id] += [
                    {"role":"user","parts":[{"text":message_text}]},
                    {"role":"model","parts":[{"text":reply}]},
                ]
                if len(conversation_history[user_id]) > 20:
                    conversation_history[user_id] = \
                        conversation_history[user_id][-20:]
                return reply
        except Exception as e:
            print(f"[GEMINI ERROR Key {current_gemini_index+1}] {e}")
            current_gemini_index = \
                (current_gemini_index + 1) % len(GEMINI_KEYS)

    # All Gemini keys failed → Groq fallback
    print("[GEMINI] All keys failed → Groq fallback")
    fallback = await groq_fallback_chat(message_text)
    return fallback or "Sorry Teja sir, all AI keys busy! 😅 Try again!"


# ──────────────────────────────────────────────────────────────
# SECTION 14 — GROQ BRAIN (Role: Deep tasks + Schedule fallback)
# ──────────────────────────────────────────────────────────────
# ChatGPT removed (costly). Groq handles deep tasks as fallback.

async def groq_deep(prompt):
    """Groq handles schedules, reminders, complex tasks as brain."""
    system = (
        f"You are Vyshu AI, smart assistant for {OWNER_FULL_NAME}. "
        f"Help with schedules, reminders, planning and complex tasks. "
        f"Be concise, smart, use emojis. Stay in Vyshu character."
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [
                          {"role": "system", "content": system},
                          {"role": "user",   "content": prompt}
                      ],
                      "max_tokens": 500, "temperature": 0.5},
                timeout=10.0
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[GROQ DEEP ERROR] {e}")
        return f"{get_prefix()} I'm thinking... try again! 😅"


# ──────────────────────────────────────────────────────────────
# SECTION 15 — LANGUAGE TEACHING (Phase 2)
# ──────────────────────────────────────────────────────────────

TEACH_LESSONS = {
    "japanese": [
        ("Hello", "Konnichiwa", "こんにちは"),
        ("Thank you", "Arigatou", "ありがとう"),
        ("Good morning", "Ohayou", "おはよう"),
        ("Good night", "Oyasumi", "おやすみ"),
        ("How are you?", "Genki desu ka?", "元気ですか？"),
    ],
    "korean": [
        ("Hello", "Annyeonghaseyo", "안녕하세요"),
        ("Thank you", "Kamsahamnida", "감사합니다"),
        ("Good morning", "Joeun achim", "좋은 아침"),
        ("I love you", "Saranghae", "사랑해"),
        ("Sorry", "Mianhae", "미안해"),
    ],
    "spanish": [
        ("Hello", "Hola", ""),
        ("Thank you", "Gracias", ""),
        ("How are you?", "¿Cómo estás?", ""),
        ("Good morning", "Buenos días", ""),
        ("Goodbye", "Adiós", ""),
    ],
    "french": [
        ("Hello", "Bonjour", ""),
        ("Thank you", "Merci", ""),
        ("How are you?", "Comment ça va?", ""),
        ("Good morning", "Bonjour", ""),
        ("Goodbye", "Au revoir", ""),
    ],
    "telugu": [
        ("Hello", "Namaskaram", "నమస్కారం"),
        ("Thank you", "Dhanyavaadamulu", "ధన్యవాదాలు"),
        ("How are you?", "Meeru ela unnaru?", "మీరు ఎలా ఉన్నారు?"),
        ("Good morning", "Shubhodayam", "శుభోదయం"),
        ("I love you", "Nenu ninnnu premistunnanu", "నేను నిన్ను ప్రేమిస్తున్నాను"),
    ],
}

def get_lesson(lang, lesson_num=0):
    lang = lang.lower()
    lessons = TEACH_LESSONS.get(lang, [])
    if not lessons:
        return f"Sorry Teja sir, {lang} teaching not available yet! 😊"
    if lesson_num >= len(lessons):
        return f"✅ You've completed all {lang} lessons! 🎉"
    english, romanized, native = lessons[lesson_num]
    mem = load_memory()
    mem["teaching_sessions"][lang] = lesson_num
    save_memory(mem)
    result = (f"🗣️ **{lang.capitalize()} Lesson {lesson_num+1}:**\n"
              f"English: **{english}**\n"
              f"Romanized: **{romanized}**")
    if native:
        result += f"\nNative: **{native}**"
    result += f"\n\n💡 Say `next {lang}` for next lesson!"
    return result

def get_next_lesson(lang):
    mem = load_memory()
    current = mem["teaching_sessions"].get(lang.lower(), 0)
    return get_lesson(lang, current + 1)


# ──────────────────────────────────────────────────────────────
# SECTION 16 — BOT CONTROL SYSTEM
# ──────────────────────────────────────────────────────────────

bots = {
    "instagram": False,
    "spotify":   False,
    "whatsapp":  False,
    "discord":   False,
    "youtube":   False,
}

def control_bot(bot_name, action):
    name = bot_name.lower()
    if name not in bots:
        return f"❌ Unknown bot: {bot_name}"
    if action == "start":
        bots[name] = True
        vyshu_speak(f"{name} bot started")
        return f"✅ {name} bot started 🎯"
    elif action == "stop":
        bots[name] = False
        vyshu_speak(f"{name} bot stopped")
        return f"🛑 {name} bot stopped"
    return "❌ Invalid action"

def get_bot_status():
    lines = ["📊 **Bot Status:**"]
    for name, running in bots.items():
        icon = "🟢" if running else "🔴"
        lines.append(f"  {icon} {name}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# SECTION 17 — CHAT COMMAND HANDLER (Terminal + WA)
# ──────────────────────────────────────────────────────────────

def parse_reminder(text):
    """Parse: 'remind me at 14:30 to drink water'"""
    match = re.search(
        r'remind(?:er)?\s+(?:me\s+)?(?:at\s+)?(\d{1,2}:\d{2})\s+(?:to\s+)?(.+)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1), match.group(2)
    return None, None

def parse_schedule(text):
    """Parse: 'schedule meeting tomorrow at 10:00'"""
    match = re.search(
        r'schedule\s+(.+?)\s+(?:on\s+)?(.+?)\s+at\s+(\d{1,2}:\d{2})',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None

async def vyshu_reply_async(user_input, user_id="local"):
    lower = user_input.lower().strip()

    # 1. Security check
    if contains_bad_words(lower):
        for word in BAD_WORDS:
            if re.search(r'(?<![a-z])' + re.escape(word) + r'(?![a-z])', lower):
                return cute_warning_text(word)

    # 2. Mode commands
    if lower in ["!night","night mode","night"]:
        return set_mode("NIGHT")
    if lower in ["!home","home mode","home"]:
        return set_mode("HOME")
    if lower in ["!office","office mode","office"]:
        return set_mode("OFFICE")

    # 3. Memory commands (needs permission feel)
    if "show memory" in lower or "what do you remember" in lower:
        return show_memory()
    if "clear all memory" in lower:
        result = clear_memory("all")
        vyshu_speak("Memory cleared Teja sir")
        return f"🗑️ {result} — All memory cleared!"
    if "clear reminders" in lower:
        return f"🗑️ {clear_memory('reminders')}"
    if "clear schedules" in lower:
        return f"🗑️ {clear_memory('schedules')}"
    if "clear notes" in lower:
        return f"🗑️ {clear_memory('notes')}"
    if "clear done" in lower:
        return f"🗑️ {clear_memory('done')}"

    # 4. Reminder
    time_str, task = parse_reminder(lower)
    if time_str and task:
        add_reminder(task, time_str)
        vyshu_speak(f"Reminder set for {time_str}")
        return (f"⏰ Reminder set!\n"
                f"📌 Task: **{task}**\n"
                f"🕐 Time: **{time_str}**\n"
                f"🔔 I'll notify you via voice + Discord DM! 💙")

    # 5. Schedule
    title, date, stime = parse_schedule(lower)
    if title and date and stime:
        add_schedule(title, date, stime)
        vyshu_speak(f"Schedule added: {title}")
        return (f"📅 Schedule added!\n"
                f"📌 **{title}**\n"
                f"📆 Date: **{date}**\n"
                f"🕐 Time: **{stime}** 💙")

    # 6. Note storing
    if lower.startswith("vyshu remember") or lower.startswith("remember"):
        note_text = re.sub(r'^(vyshu\s+)?remember\s*', '', user_input, flags=re.IGNORECASE)
        if note_text.strip():
            add_note(note_text.strip())
            vyshu_speak("I'll remember that Teja sir")
            return f"📝 Noted and saved! 💙\n> {note_text.strip()}"

    # 7. Language teaching
    for lang in TEACH_LESSONS:
        if f"teach me {lang}" in lower or f"learn {lang}" in lower:
            return get_lesson(lang)
        if f"next {lang}" in lower:
            return get_next_lesson(lang)

    # 8. V2 Mobile Controls
    mobile_result = handle_mobile_command(lower)
    if mobile_result:
        return mobile_result

    # 9. Bot commands
    for bot_name in bots:
        if f"start {bot_name}" in lower:
            return control_bot(bot_name, "start")
        if f"stop {bot_name}" in lower:
            return control_bot(bot_name, "stop")
    if "bot status" in lower or "status" in lower:
        return get_bot_status()

    # 10. Complex task → Groq deep brain
    complex_triggers = ["plan","analyse","calculate","compare",
                        "what should i","help me decide","suggest"]
    if any(t in lower for t in complex_triggers):
        return await groq_deep(user_input)

    # 11. AI Personality → Gemini role
    return await vyshu_respond(user_id, user_input)

def vyshu_reply(user_input, user_id="local"):
    """Sync wrapper for terminal/WhatsApp use."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            vyshu_reply_async(user_input, user_id)
        )
    except Exception as e:
        return f"{get_prefix()} Sorry, something went wrong! 😅 ({e})"
  
# ──────────────────────────────────────────────────────────────
# SECTION 18 — V2 FEATURES: MOBILE CONTROL + VOICE + APPS
# (Already achieved in V2 — restored in V3!)
# ──────────────────────────────────────────────────────────────

# ── CONTACTS LIST (add your contacts here) ───────────────────
CONTACTS = {
    # "name": "+91XXXXXXXXXX"
    # Example entries — replace with real ones:
    "mom":    "+91XXXXXXXXXX",
    "dad":    "+91XXXXXXXXXX",
    "teja":   "+91XXXXXXXXXX",
    # Add more contacts here freely
}

# ── APP PACKAGE NAMES (Android) ──────────────────────────────
APPS = {
    "spotify":    "com.spotify.music",
    "youtube":    "com.google.android.youtube",
    "whatsapp":   "com.whatsapp",
    "instagram":  "com.instagram.android",
    "chrome":     "com.android.chrome",
    "camera":     "com.android.camera2",
    "gallery":    "com.google.android.apps.photos",
    "maps":       "com.google.android.apps.maps",
    "settings":   "com.android.settings",
    "calculator": "com.android.calculator2",
    "clock":      "com.android.deskclock",
    "contacts":   "com.android.contacts",
    "messages":   "com.android.mms",
    "playstore":  "com.android.vending",
    "telegram":   "org.telegram.messenger",
    "discord":    "com.discord",
}

# ── MOBILE ACCESSORIES CONTROL (Termux API) ──────────────────

def control_wifi(state):
    """Turn WiFi on/off."""
    try:
        cmd = "enable" if state else "disable"
        subprocess.run(["termux-wifi-enable",
                        "true" if state else "false"])
        # Fallback using svc
        subprocess.run(["svc", "wifi", cmd])
        msg = f"📶 WiFi {'ON' if state else 'OFF'}! 💙"
        vyshu_speak(f"WiFi turned {'on' if state else 'off'}")
        return msg
    except Exception as e:
        return f"❌ WiFi control failed: {e}"

def control_torch(state):
    """Turn torch/flashlight on/off."""
    try:
        subprocess.run([
            "termux-torch", "on" if state else "off"
        ])
        msg = f"🔦 Torch {'ON' if state else 'OFF'}! 💙"
        vyshu_speak(f"Torch turned {'on' if state else 'off'}")
        return msg
    except Exception as e:
        return f"❌ Torch control failed: {e}"

def control_hotspot(state):
    """Turn mobile hotspot on/off."""
    try:
        # Needs root or ADB — works in most rooted devices
        subprocess.run([
            "svc", "wifi", "ap",
            "enable" if state else "disable"
        ])
        msg = f"📡 Hotspot {'ON' if state else 'OFF'}! 💙"
        vyshu_speak(f"Hotspot turned {'on' if state else 'off'}")
        return msg
    except Exception as e:
        return f"❌ Hotspot control failed: {e}"

def control_bluetooth(state):
    """Turn Bluetooth on/off."""
    try:
        subprocess.run([
            "svc", "bluetooth",
            "enable" if state else "disable"
        ])
        msg = f"🔵 Bluetooth {'ON' if state else 'OFF'}! 💙"
        vyshu_speak(f"Bluetooth turned {'on' if state else 'off'}")
        return msg
    except Exception as e:
        return f"❌ Bluetooth control failed: {e}"

def control_volume(level):
    """Set volume level (0-15)."""
    try:
        subprocess.run([
            "termux-volume", "music", str(level)
        ])
        msg = f"🔊 Volume set to {level}! 💙"
        vyshu_speak(f"Volume set to {level}")
        return msg
    except Exception as e:
        return f"❌ Volume control failed: {e}"

def control_brightness(level):
    """Set screen brightness (0-255)."""
    try:
        subprocess.run([
            "termux-brightness", str(level)
        ])
        msg = f"☀️ Brightness set to {level}! 💙"
        vyshu_speak(f"Brightness set to {level}")
        return msg
    except Exception as e:
        return f"❌ Brightness control failed: {e}"

def smart_mirror_toggle():
    """V4 hook — Smart mirror control via IoT."""
    # V4: Connect to smart mirror API/Bluetooth
    return "🪞 Smart mirror control coming in V4! 💙"

# ── OPEN APPS ─────────────────────────────────────────────────

def open_app(app_name):
    """Open any Android app by name."""
    name = app_name.lower().strip()
    package = APPS.get(name)
    if not package:
        return f"❌ App '{app_name}' not in my list! 😊"
    try:
        subprocess.run([
            "am", "start",
            "-n", f"{package}/{package}.MainActivity"
        ])
        # Fallback using monkey
        subprocess.Popen([
            "monkey", "-p", package,
            "-c", "android.intent.category.LAUNCHER", "1"
        ])
        msg = f"📱 Opening {app_name.capitalize()}! 💙"
        vyshu_speak(f"Opening {app_name}")
        return msg
    except Exception as e:
        return f"❌ Failed to open {app_name}: {e}"

# ── PHONE CALLS ──────────────────────────────────────────────

def call_contact(name):
    """Call a contact by name using termux-telephony-call."""
    name_lower = name.lower().strip()
    # Direct name match
    number = CONTACTS.get(name_lower)
    if not number:
        # Partial match
        for contact, num in CONTACTS.items():
            if name_lower in contact or contact in name_lower:
                number = num
                name = contact
                break
    if not number:
        return (f"❌ Contact '{name}' not found!\n"
                f"Add them to CONTACTS in the layout 💙")
    try:
        subprocess.run(["termux-telephony-call", number])
        msg = f"📞 Calling {name.capitalize()} ({number})... 💙"
        vyshu_speak(f"Calling {name}")
        return msg
    except Exception as e:
        return f"❌ Call failed: {e}"

# ── SPOTIFY CONTROL ───────────────────────────────────────────

def spotify_play(song_name):
    """Search and play a song on Spotify."""
    try:
        # Open Spotify with search URI
        search_query = song_name.replace(" ", "%20")
        subprocess.Popen([
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", f"spotify:search:{search_query}"
        ])
        msg = f"🎵 Searching '{song_name}' on Spotify! 💙"
        vyshu_speak(f"Playing {song_name} on Spotify")
        return msg
    except Exception as e:
        return f"❌ Spotify failed: {e}"

def spotify_control(action):
    """Play/Pause/Next/Previous on Spotify."""
    actions = {
        "play":     "com.spotify.music.playbackstatechanged",
        "pause":    "com.spotify.music.playbackstatechanged",
        "next":     "com.spotify.music.next",
        "previous": "com.spotify.music.previous",
        "prev":     "com.spotify.music.previous",
    }
    action = action.lower()
    if action not in actions:
        return f"❌ Unknown Spotify action: {action}"
    try:
        subprocess.run([
            "am", "broadcast",
            "-a", actions[action],
            "-p", "com.spotify.music"
        ])
        icons = {"play":"▶️","pause":"⏸️","next":"⏭️","previous":"⏮️","prev":"⏮️"}
        msg = f"{icons.get(action,'🎵')} Spotify: {action.capitalize()}! 💙"
        vyshu_speak(f"Spotify {action}")
        return msg
    except Exception as e:
        return f"❌ Spotify control failed: {e}"

# ── YOUTUBE CONTROL ───────────────────────────────────────────

def youtube_play(video_name):
    """Search and play a video on YouTube."""
    try:
        search_query = video_name.replace(" ", "+")
        # Try YouTube app first
        subprocess.Popen([
            "am", "start",
            "-a", "android.intent.action.SEARCH",
            "-n", "com.google.android.youtube/"
                  "com.google.android.youtube.HomeActivity",
            "--es", "query", video_name
        ])
        msg = f"▶️ Searching '{video_name}' on YouTube! 💙"
        vyshu_speak(f"Playing {video_name} on YouTube")
        return msg
    except Exception as e:
        # Fallback — open YouTube search in browser
        try:
            url = f"https://www.youtube.com/results?search_query={search_query}"
            subprocess.Popen(["termux-open-url", url])
            return f"▶️ Opening YouTube search for '{video_name}'! 💙"
        except Exception as e2:
            return f"❌ YouTube failed: {e2}"

# ── VOICE COMMAND LISTENER ────────────────────────────────────

def listen_voice_command():
    """Listen for voice command using termux-speech-to-text."""
    try:
        result = subprocess.run(
            ["termux-speech-to-text"],
            capture_output=True, text=True, timeout=10
        )
        text = result.stdout.strip()
        if text:
            vyshu_speak(f"I heard: {text}")
            return text
        return None
    except Exception as e:
        print(f"[VOICE INPUT ERROR] {e}")
        return None

def voice_command_loop():
    """
    Continuous voice command listener.
    Activate: python vyshu_master.py --voice
    Say 'Vyshu' to wake, then give command.
    """
    print("🎙️ Voice mode active — Say 'Vyshu' to wake!")
    vyshu_speak("Voice mode active. Say Vyshu to wake me!")
    while True:
        try:
            text = listen_voice_command()
            if not text:
                continue
            if "vyshu" in text.lower():
                vyshu_speak("Yes Teja sir?")
                print("🎙️ Listening for command...")
                command = listen_voice_command()
                if command:
                    print(f"Command: {command}")
                    response = vyshu_reply(command)
                    print(f"Vyshu: {response}")
                    vyshu_speak(response)
        except KeyboardInterrupt:
            vyshu_speak("Voice mode stopped. Goodbye Teja sir!")
            break
        except Exception as e:
            print(f"[VOICE LOOP ERROR] {e}")
            time.sleep(2)

# ── MASTER MOBILE COMMAND HANDLER ────────────────────────────

def handle_mobile_command(lower):
    """
    Parses and handles all V2 mobile commands.
    Returns response string if matched, None if not a mobile command.
    """

    # ── WiFi ──
    if re.search(r'\bwifi\b', lower):
        if any(w in lower for w in ["on","enable","start"]):
            return control_wifi(True)
        if any(w in lower for w in ["off","disable","stop"]):
            return control_wifi(False)

    # ── Torch / Flashlight ──
    if re.search(r'\b(torch|flashlight)\b', lower):
        if any(w in lower for w in ["on","enable","open"]):
            return control_torch(True)
        if any(w in lower for w in ["off","disable","close"]):
            return control_torch(False)

    # ── Hotspot ──
    if re.search(r'\b(hotspot|mobile data sharing)\b', lower):
        if any(w in lower for w in ["on","enable","start"]):
            return control_hotspot(True)
        if any(w in lower for w in ["off","disable","stop"]):
            return control_hotspot(False)

    # ── Bluetooth ──
    if re.search(r'\bbluetooth\b', lower):
        if any(w in lower for w in ["on","enable","start"]):
            return control_bluetooth(True)
        if any(w in lower for w in ["off","disable","stop"]):
            return control_bluetooth(False)

    # ── Volume ──
    vol_match = re.search(r'volume\s+(\d+)', lower)
    if vol_match:
        return control_volume(int(vol_match.group(1)))
    if "volume up" in lower:
        return control_volume(15)
    if "volume down" in lower:
        return control_volume(3)
    if "mute" in lower or "silent" in lower:
        return control_volume(0)

    # ── Brightness ──
    bright_match = re.search(r'brightness\s+(\d+)', lower)
    if bright_match:
        return control_brightness(int(bright_match.group(1)))
    if "full brightness" in lower or "max brightness" in lower:
        return control_brightness(255)
    if "low brightness" in lower or "dim" in lower:
        return control_brightness(50)

    # ── Smart Mirror ──
    if "smart mirror" in lower or "mirror" in lower:
        return smart_mirror_toggle()

    # ── Open App ──
    open_match = re.search(
        r'open\s+(\w+)', lower)
    if open_match:
        app = open_match.group(1)
        if app in APPS:
            return open_app(app)

    # ── Call Contact ──
    call_match = re.search(
        r'call\s+(.+)', lower)
    if call_match:
        contact_name = call_match.group(1).strip()
        return call_contact(contact_name)

    # ── Spotify ──
    if "spotify" in lower:
        play_match = re.search(
            r'(?:play|search|find)\s+(.+?)(?:\s+on\s+spotify|$)', lower)
        if play_match:
            return spotify_play(play_match.group(1).strip())
        if "next" in lower or "skip" in lower:
            return spotify_control("next")
        if "previous" in lower or "prev" in lower or "back" in lower:
            return spotify_control("previous")
        if "pause" in lower or "stop" in lower:
            return spotify_control("pause")
        if "play" in lower or "resume" in lower:
            return spotify_control("play")

    # ── Play song (without saying spotify) ──
    song_match = re.search(
        r'play\s+(.+?)(?:\s+song|$)', lower)
    if song_match and "youtube" not in lower:
        return spotify_play(song_match.group(1).strip())

    # ── YouTube ──
    if "youtube" in lower:
        yt_match = re.search(
            r'(?:play|search|find|open)\s+(.+?)(?:\s+on\s+youtube|$)',
            lower)
        if yt_match:
            return youtube_play(yt_match.group(1).strip())
        return open_app("youtube")

    # ── Play video ──
    video_match = re.search(r'play\s+(.+?)\s+(?:video|on youtube)', lower)
    if video_match:
        return youtube_play(video_match.group(1).strip())

    return None  # Not a mobile command
  

# ──────────────────────────────────────────────────────────────
# SECTION 19 — V4 HOOKS (Placeholders — filled in V4)
# ──────────────────────────────────────────────────────────────

def openclaw_agent(task):
    """V4: OpenClaw orchestrates all bots autonomously."""
    pass

def generate_image(prompt):
    """V4: Gemini API → realistic images, thumbnails, videos."""
    pass

def generate_sticker(emotion):
    """V4: Gemini API → auto anime sticker generation."""
    pass

def apk_launch():
    """V4: Kivy + Buildozer → standalone APK, no Termux."""
    pass

def auto_upload_content(content, platform):
    """V4: Post to Instagram/YouTube autonomously."""
    pass


# ──────────────────────────────────────────────────────────────
# SECTION 19 — DISCORD BOT
# ──────────────────────────────────────────────────────────────

def run_discord_bot():
    global reminder_discord_bot
    import discord
    from discord.ext import commands
    from discord import app_commands

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.remove_command('help')
    reminder_discord_bot = bot

    LANG_CHOICES = [
        app_commands.Choice(name=n.capitalize(), value=c)
        for n, (c, _) in LANGUAGE_MAP.items()
    ]

    # ── !language commands (18) ──────────────────────────────
    def make_lang_command(lang_name, lang_code, flag):
        @bot.command(name=lang_name)
        async def lang_cmd(ctx):
            user_language[str(ctx.author.id)] = lang_code
            embed = discord.Embed(
                title="🌐 Language Updated!",
                description=(
                    f"{flag} {ctx.author.mention}\n\n"
                    f"Language set to **{lang_name.capitalize()}**!\n"
                    f"✅ Auto-translation active! 😊"
                ),
                color=0x00ccff
            )
            embed.set_footer(text="Vyshu AI • Language Settings")
            await ctx.send(embed=embed)

    for lang_name, (lang_code, flag) in LANGUAGE_MAP.items():
        make_lang_command(lang_name, lang_code, flag)

    # ── /translate ───────────────────────────────────────────
    @bot.tree.command(name="translate",
                      description="Translate any text to your language")
    @app_commands.describe(text="Text to translate",
                           language="Target language (optional)")
    @app_commands.choices(language=LANG_CHOICES[:25])
    async def slash_translate(
        interaction: discord.Interaction, text: str,
        language: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()
        uid = str(interaction.user.id)
        target = language.value if language \
            else user_language.get(uid, "en")
        translated = await groq_translate(text, target)
        if not translated:
            await interaction.followup.send(
                "ℹ️ Already in target language!", ephemeral=True)
            return
        lang_name = LANG_FULL_NAMES.get(target, "English")
        embed = discord.Embed(title="🌐 Vyshu Translation",
                              color=0x5865F2)
        embed.add_field(name="📝 Original", value=text, inline=False)
        embed.add_field(name=f"🌐 {lang_name}",
                        value=translated, inline=False)
        embed.set_footer(text=f"Vyshu AI ⚡ Groq | {lang_name}")
        await interaction.followup.send(embed=embed)

    # ── /setlang ─────────────────────────────────────────────
    @bot.tree.command(name="setlang",
                      description="Set your language preference")
    @app_commands.describe(language="Choose your language")
    @app_commands.choices(language=LANG_CHOICES[:25])
    async def slash_setlang(
        interaction: discord.Interaction,
        language: app_commands.Choice[str]
    ):
        user_language[str(interaction.user.id)] = language.value
        lang_name = LANG_FULL_NAMES.get(language.value, "English")
        embed = discord.Embed(
            title="🌐 Language Updated!",
            description=(
                f"{interaction.user.mention}\n"
                f"Set to **{lang_name}**! ✅"
            ),
            color=0x00ccff
        )
        embed.set_footer(text="Vyshu AI • Language Settings")
        await interaction.response.send_message(embed=embed)

    # ── /setup ───────────────────────────────────────────────
    @bot.tree.command(name="setup",
                      description="Setup your translation profile")
    @app_commands.choices(mode=[
        app_commands.Choice(
            name="Indian (See everything in English)", value="indian"),
        app_commands.Choice(
            name="Foreigner (See in your native language)",
            value="foreigner"),
    ])
    async def slash_setup(
        interaction: discord.Interaction,
        mode: app_commands.Choice[str]
    ):
        uid = str(interaction.user.id)
        user_profile[uid] = {"mode": mode.value,
                             "lang": user_language.get(uid, "en")}
        if mode.value == "indian":
            msg = "✅ Mode: **Indian**\nEverything in English 🇬🇧"
        else:
            lang = LANG_FULL_NAMES.get(
                user_language.get(uid, "en"), "English")
            msg = f"✅ Mode: **Foreigner**\nTranslations in **{lang}**"
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /detect ──────────────────────────────────────────────
    @bot.tree.command(name="detect",
                      description="Detect what language a text is")
    @app_commands.describe(text="Text to detect")
    async def slash_detect(interaction: discord.Interaction, text: str):
        await interaction.response.defer()
        detected = await groq_detect_language(text)
        embed = discord.Embed(title="🔍 Language Detected",
                              color=0x00ff99)
        embed.add_field(name="📝 Text", value=text, inline=False)
        embed.add_field(name="🌐 Language",
                        value=f"**{detected}**", inline=False)
        embed.set_footer(text="Vyshu AI ⚡ Groq")
        await interaction.followup.send(embed=embed)

    # ── /warnings ────────────────────────────────────────────
    @bot.tree.command(name="warnings",
                      description="Check your warning count")
    async def slash_warnings(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        count = user_warnings.get(uid, 0)
        remaining = 7 - count
        color = (0x00ff99 if count == 0
                 else 0xffcc00 if count < 5 else 0xff0000)
        embed = discord.Embed(title="⚠️ Warning Status", color=color)
        embed.add_field(name="👤 User",
                        value=interaction.user.mention, inline=True)
        embed.add_field(name="⚠️ Warnings",
                        value=f"**{count}/7**", inline=True)
        embed.add_field(name="✅ Remaining",
                        value=f"**{remaining}**", inline=True)
        if count == 0:
            status = "✅ Clean record! Keep it up!"
        elif count >= 7:
            status = "🚨 Admin has been notified!"
        else:
            status = f"⚠️ {remaining} more = Admin action!"
        embed.add_field(name="Status", value=status, inline=False)
        embed.set_footer(text="Vyshu AI • Warning System")
        await interaction.response.send_message(
            embed=embed, ephemeral=True)

    # ── /badwords ────────────────────────────────────────────
    @bot.tree.command(name="badwords",
                      description="View bad word policy")
    async def slash_badwords(interaction: discord.Interaction):
        embed = discord.Embed(title="🚫 Bad Word Policy",
                              color=0xff0000)
        embed.add_field(name="📋 Rules", value=(
            "• Detected in **18 languages** automatically\n"
            "• Message **deleted** instantly 🗑️\n"
            "• Fun warning with personality 🔫🥿\n"
            "• **7 warnings** → Admin notified 🚨"
        ), inline=False)
        embed.add_field(name="⚠️ Warning Journey", value=(
            "1️⃣ 👋 Friendly heads up\n"
            "2️⃣ 🥿 Slipper raised!\n"
            "3️⃣ 🔫 Gun loading...\n"
            "4️⃣ 🔫🔫 Two guns!\n"
            "5️⃣ 💀 Danger zone!\n"
            "6️⃣ ☠️ Final warning!\n"
            "7️⃣ 🚨 Admin called!"
        ), inline=False)
        embed.set_footer(text="Vyshu AI • Keep chat clean! 💙")
        await interaction.response.send_message(embed=embed)

    # ── /vyshu ───────────────────────────────────────────────
    @bot.tree.command(name="vyshu",
                      description="Talk to Vyshu AI directly!")
    @app_commands.describe(
        message="What do you want to say to Vyshu?")
    async def slash_vyshu(
        interaction: discord.Interaction, message: str
    ):
        await interaction.response.defer(thinking=True)
        uid = str(interaction.user.id)
        # ✅ Direct to V1 Gemini brain — pure personality chat
        reply = await vyshu_respond(uid, message)
        embed = discord.Embed(description=f"💬 {reply}",
                              color=0x00ccff)
        embed.set_author(name="Vyshu AI 🤖")
        embed.set_footer(text="Vyshu AI • Powered by Gemini ✨")
        await interaction.followup.send(embed=embed)

    # ── /remind ──────────────────────────────────────────────
    @bot.tree.command(name="remind",
                      description="Set a reminder — Vyshu will DM + speak!")
    @app_commands.describe(time="Time in HH:MM format (e.g. 14:30)",
                           task="What to remind you about")
    async def slash_remind(
        interaction: discord.Interaction, time: str, task: str
    ):
        if not re.match(r'^\d{1,2}:\d{2}$', time):
            await interaction.response.send_message(
                "❌ Use HH:MM format! Example: `14:30`",
                ephemeral=True)
            return
        add_reminder(task, time, notify_discord=True)
        embed = discord.Embed(title="⏰ Reminder Set!", color=0x00ccff)
        embed.add_field(name="📌 Task", value=task, inline=False)
        embed.add_field(name="🕐 Time", value=time, inline=True)
        embed.add_field(name="🔔 Alert", value="Voice + Discord DM",
                        inline=True)
        embed.set_footer(text="Vyshu AI • Reminder System 💙")
        await interaction.response.send_message(embed=embed)

    # ── /schedule ────────────────────────────────────────────
    @bot.tree.command(name="schedule",
                      description="Add to Vyshu's schedule")
    @app_commands.describe(title="Event title",
                           date="Date (e.g. tomorrow, 2025-12-25)",
                           time="Time in HH:MM",
                           note="Optional note")
    async def slash_schedule(
        interaction: discord.Interaction,
        title: str, date: str, time: str, note: str = ""
    ):
        add_schedule(title, date, time, note)
        embed = discord.Embed(title="📅 Schedule Added!", color=0x00ff99)
        embed.add_field(name="📌 Event", value=title, inline=False)
        embed.add_field(name="📆 Date", value=date, inline=True)
        embed.add_field(name="🕐 Time", value=time, inline=True)
        if note:
            embed.add_field(name="📝 Note", value=note, inline=False)
        embed.set_footer(text="Vyshu AI • Schedule Manager 💙")
        await interaction.response.send_message(embed=embed)

    # ── /memory ──────────────────────────────────────────────
    @bot.tree.command(name="memory",
                      description="View or clear Vyshu's memory")
    @app_commands.describe(
        action="view / clear_all / clear_done / clear_notes")
    @app_commands.choices(action=[
        app_commands.Choice(name="View memory", value="view"),
        app_commands.Choice(name="Clear completed tasks",
                            value="clear_done"),
        app_commands.Choice(name="Clear notes", value="clear_notes"),
        app_commands.Choice(name="Clear ALL (admin)",
                            value="clear_all"),
    ])
    async def slash_memory(
        interaction: discord.Interaction,
        action: app_commands.Choice[str]
    ):
        if action.value == "view":
            result = show_memory()
        elif action.value == "clear_done":
            result = clear_memory("done")
        elif action.value == "clear_notes":
            result = clear_memory("notes")
        elif action.value == "clear_all":
            if interaction.user.id != ADMIN_ID:
                await interaction.response.send_message(
                    "🚫 Only Teja sir can clear all memory!",
                    ephemeral=True)
                return
            result = clear_memory("all")
        embed = discord.Embed(title="🧠 Vyshu Memory",
                              description=result, color=0x7b5ea7)
        embed.set_footer(text="Vyshu AI • Memory System 💙")
        await interaction.response.send_message(
            embed=embed, ephemeral=True)

    # ── /teach ───────────────────────────────────────────────
    @bot.tree.command(name="teach",
                      description="Vyshu teaches you a language!")
    @app_commands.describe(language="Language to learn")
    @app_commands.choices(language=[
        app_commands.Choice(name=l.capitalize(), value=l)
        for l in TEACH_LESSONS.keys()
    ])
    async def slash_teach(
        interaction: discord.Interaction,
        language: app_commands.Choice[str]
    ):
        lesson = get_lesson(language.value)
        embed = discord.Embed(title=f"🗣️ {language.name} Lesson",
                              description=lesson, color=0xffd700)
        embed.set_footer(text="Vyshu AI • Language Teaching 💙")
        await interaction.response.send_message(embed=embed)

    # ── /setpfp (Admin only) ──────────────────────────────────
    @bot.tree.command(name="setpfp",
                      description="[Admin] Change Vyshu's profile picture")
    @app_commands.describe(url="Direct image URL (.jpg/.png)")
    async def slash_setpfp(
        interaction: discord.Interaction, url: str
    ):
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message(
                "🚫 Only Teja sir can change my profile picture! 😊",
                ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            async with httpx.AsyncClient() as client:
                img_resp = await client.get(url, timeout=10.0)
                img_bytes = img_resp.content
            await bot.user.edit(avatar=img_bytes)
            embed = discord.Embed(
                title="✅ Profile Picture Updated!",
                description="Vyshu's new look is live! 💙✨",
                color=0x00ccff
            )
            embed.set_thumbnail(url=url)
            embed.set_footer(text="Vyshu AI • Profile Settings")
            await interaction.followup.send(embed=embed,
                                            ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Discord limit: {e}\n"
                f"💡 Discord allows pic change only 2x/hour!",
                ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed: {e}\n"
                f"💡 Use direct image URL ending in .jpg/.png",
                ephemeral=True)

    # ── /help ────────────────────────────────────────────────
    @bot.tree.command(name="help",
                      description="Show all Vyshu AI commands")
    async def slash_help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌐 Vyshu AI – All Commands", color=0x00ff99)
        embed.add_field(name="🤖 AI Commands", value=(
            "`/vyshu` – Talk to Vyshu AI\n"
            "`/translate` – Translate any text\n"
            "`/detect` – Detect language"
        ), inline=False)
        embed.add_field(name="⚙️ Settings", value=(
            "`/setlang` – Set your language\n"
            "`/setup` – Indian/Foreigner mode\n"
            "`/setpfp` – Change profile pic [Admin]"
        ), inline=False)
        embed.add_field(name="⏰ Schedule & Reminders", value=(
            "`/remind` – Set a reminder\n"
            "`/schedule` – Add to schedule\n"
            "`/memory` – View/clear memory"
        ), inline=False)
        embed.add_field(name="🗣️ Learning", value=(
            "`/teach` – Learn a language with Vyshu!"
        ), inline=False)
        embed.add_field(name="🛡️ Safety", value=(
            "`/warnings` – Your warning count\n"
            "`/badwords` – Bad word policy"
        ), inline=False)
        embed.add_field(name="❕ Language Commands", value=(
            "`!english` `!telugu` `!hindi` `!tamil` `!kannada`\n"
            "`!malayalam` `!bengali` `!marathi` `!indonesian`\n"
            "`!japanese` `!chinese` `!vietnamese` `!thai`\n"
            "`!korean` `!filipino` `!spanish` `!french` `!nepali`"
        ), inline=False)
        embed.add_field(name="⚡ AI Role Allocation", value=(
            "⚡ Groq — Translation + Detection + Fallback\n"
            "🟣 Gemini (up to 5 keys) — Primary brain + Chat\n"
            "🤖 OpenClaw — Bot Orchestration (V4)"
        ), inline=False)
        embed.set_footer(text="Vyshu AI V3 ⚡ Gemini + Groq")
        await interaction.response.send_message(embed=embed)

    # ── Events ───────────────────────────────────────────────
    @bot.event
    async def on_guild_join(guild):
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="👋 Vyshu AI has arrived!",
                    description=(
                        "🌐 **Multilingual AI Secretary**\n"
                        "⚡ Groq + Gemini powered\n\n"
                        "Type `/help` to see all commands!\n"
                        "Type `/vyshu` to talk to me! 😊\n"
                        "Type `/setup` to configure your mode!"
                    ),
                    color=0x00ccff
                )
                await ch.send(embed=embed)
                break

    @bot.event
    async def on_member_join(member):
        ch = member.guild.system_channel
        if ch:
            embed = discord.Embed(
                title=f"👋 Welcome {member.name}!",
                description=(
                    f"Hey {member.mention}! Welcome! 🎉\n\n"
                    f"🌐 I'm Vyshu AI!\n"
                    f"Type `/setup` to configure your mode!\n"
                    f"Type `/vyshu` to talk to me! 😊"
                ),
                color=0x00ff99
            )
            await ch.send(embed=embed)

    @bot.event
    async def on_ready():
        try:
            synced = await bot.tree.sync()
            print(f"✅ Vyshu AI online → {bot.user}")
            print(f"⚡ {len(synced)} slash commands synced")
            print(f"🤖 Gemini keys: {len(GEMINI_KEYS)} loaded "
                  f"{'✅' if GEMINI_KEYS else '❌'}")
            print(f"⚡ Groq: {'✅' if GROQ_API_KEY else '❌ Not set'}")
            print(f"🌐 Languages: {len(LANGUAGE_MAP)} loaded ✅")
            print(f"🔫 Bad word protection: 18 languages ✅")
            print(f"⏰ Reminder system: starting...")
            start_reminder_thread()
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        if message.content.startswith('!'):
            await bot.process_commands(message)
            return

        uid  = str(message.author.id)
        content = message.content.strip()
        if not content or len(content) < 2:
            return

        # Shield 1: Teja talks to Vyshu directly → V1 Gemini brain
        if message.author.id == ADMIN_ID \
                and "vyshu" in content.lower():
            async with message.channel.typing():
                reply = await vyshu_respond(uid, content)
                embed = discord.Embed(
                    description=f"💬 {reply}", color=0x00ccff)
                embed.set_author(name="Vyshu AI 🤖")
                embed.set_footer(text="Vyshu AI • Gemini ✨")
                await message.reply(embed=embed,
                                    mention_author=False)
            return

        # Shield 2: Bad word check
        if contains_bad_words(content):
            user_warnings[uid] = user_warnings.get(uid, 0) + 1
            count = user_warnings[uid]
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(
                get_warning_message(message.author.mention, count))
            if count >= 7:
                try:
                    admin = await bot.fetch_user(ADMIN_ID)
                    await admin.send(
                        f"🚨 **Warning Alert**\n"
                        f"User: {message.author} "
                        f"(`{message.author.id}`)\n"
                        f"Server: {message.guild.name}\n"
                        f"Channel: #{message.channel.name}\n"
                        f"Message: ||{content}||"
                    )
                except Exception as e:
                    print(f"[ADMIN DM ERROR] {e}")
                user_warnings[uid] = 0
            return

        # Shield 3: Basic skip
        if is_basic_skip(content):
            return

        # Shield 4: Groq translation
        translated = await groq_translate(content, 'en')
        if not translated:
            return
        embed = discord.Embed(
            description=f"🌐 {translated}", color=0x5865F2)
        embed.set_footer(
            text="Auto-translated → EN | Vyshu AI ⚡ Groq")
        await message.reply(embed=embed, mention_author=False)
        await bot.process_commands(message)

    bot.run(DISCORD_TOKEN)
  
  

# ──────────────────────────────────────────────────────────────
# SECTION 20 — WHATSAPP BRIDGE (Flask — port 5001)
# ──────────────────────────────────────────────────────────────

def run_whatsapp_bridge():
    from flask import Flask, request, jsonify
    app = Flask(__name__)

    @app.route('/message', methods=['POST'])
    def handle_message():
        data = request.json or {}
        user_msg = data.get('message', '')
        user_id  = data.get('userId', 'wa_user')
        if contains_bad_words(user_msg):
            return jsonify({"reply": cute_warning_text()})
        reply = vyshu_reply(user_msg, user_id)
        return jsonify({"reply": reply})

    @app.route('/status', methods=['GET'])
    def status():
        return jsonify({"status": "Vyshu WA Bridge active",
                        "bots": bots, "mode": auto_mode()})

    @app.route('/bot/<name>/<action>', methods=['POST'])
    def bot_control(name, action):
        return jsonify({"result": control_bot(name, action)})

    @app.route('/memory', methods=['GET'])
    def memory_view():
        return jsonify(load_memory())

    print("📱 Vyshu WhatsApp Bridge → port 5001")
    start_reminder_thread()
    app.run(host='0.0.0.0', port=5001)


# ──────────────────────────────────────────────────────────────
# SECTION 21 — TERMINAL MODE
# ──────────────────────────────────────────────────────────────

def run_terminal():
    print("=" * 55)
    print("💙 VYSHU AI V3 — Terminal Mode")
    print(f"👤 Owner  : {OWNER_FULL_NAME}")
    print(f"🌙 Mode   : {auto_mode()}")
    gemini_count = len(GEMINI_KEYS)
    print(f"🤖 Gemini : {gemini_count} key(s) loaded "
          f"{'✅' if gemini_count > 0 else '❌ Add GEMINI_KEY_1 in .env!'}")
    print(f"⚡ Groq   : {'✅' if GROQ_API_KEY else '❌ Add GROQ_API_KEY in .env!'}")
    print(f"🤖 OpenClaw: V4 hook")
    print("Type 'exit' to quit.")
    print("=" * 55)

    vyshu_speak(
        f"Hello {OWNER_SHORT_NAME} sir, Vyshu AI V3 is online!")
    start_reminder_thread()

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit","quit","bye"]:
                vyshu_speak("Goodbye Teja sir!")
                print("Vyshu: Goodbye Teja sir! 💙")
                break
            response = vyshu_reply(user_input)
            print(f"\nVyshu: {response}")
            vyshu_speak(response)
        except KeyboardInterrupt:
            print("\nVyshu: Goodbye Teja sir! 💙")
            break


# ──────────────────────────────────────────────────────────────
# SECTION 23 — ENTRY POINT
# ──────────────────────────────────────────────────────────────
# python vyshu_master.py              → Terminal mode
# python vyshu_master.py --discord    → Discord bot
# python vyshu_master.py --whatsapp   → WhatsApp bridge
# python vyshu_master.py --voice      → Voice command mode 🎙️

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--discord" in args:
        print("🤖 Starting Vyshu Discord Bot...")
        run_discord_bot()
    elif "--whatsapp" in args:
        print("📱 Starting Vyshu WhatsApp Bridge...")
        run_whatsapp_bridge()
    elif "--voice" in args:
        print("🎙️ Starting Vyshu Voice Command Mode...")
        voice_command_loop()
    else:
        run_terminal()

# ──────────────────────────────────────────────────────────────
# END — VYSHU AI V3 MASTER (V1 + V2 + V3 Combined)
# V1: Personality + Commands
# V2: Voice + Mobile Control + Spotify + YouTube + Calls
# V3: Discord + WhatsApp + Memory + Reminders + Teaching
# Next → V4: APK (Kivy) + OpenClaw + Gemini Auto-stickers
# "I think. I create. I execute." — Vyshu AI 💙
# ──────────────────────────────────────────────────────────────
