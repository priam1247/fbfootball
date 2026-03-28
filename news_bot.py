import os, re, json, time, requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
GROQ_KEY   = os.getenv("GROQ_KEY")

FB_POST_URL     = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
NEWS_STATE_FILE = "news_state.json"
PAGE_NAME       = "ScoreLine Live"
POST_INTERVAL   = 2700  # 45 minutes

# ── RSS Sources ───────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "BBC Sport",  "url": "https://feeds.bbci.co.uk/sport/football/rss.xml"},
    {"name": "Sky Sports", "url": "https://www.skysports.com/rss/0,20514,11095,00.xml"},
    {"name": "Marca",      "url": "https://e00-marca.uecdn.es/rss/en/index.xml"},
    {"name": "TalkSPORT",  "url": "https://talksport.com/feed"},
]

# ── Categories ────────────────────────────────────────────────────
CATEGORIES = {
    "BREAKING":      {"emoji": "🚨", "keywords": ["breaking","just in","urgent","exclusive"], "priority": True},
    "TRANSFER":      {"emoji": "🔴", "keywords": ["transfer","signing","signs","move","deal","fee","loan","free agent","bid","offer","target","agree","done deal","medical"], "priority": False},
    "INJURY":        {"emoji": "🤕", "keywords": ["injury","injured","out for","miss","scan","fitness","doubt","ruled out","surgery","fracture","muscle"], "priority": False},
    "CONTRACT":      {"emoji": "📝", "keywords": ["contract","extends","extension","renew","renewal","new deal","signs new"], "priority": False},
    "SACKED":        {"emoji": "🔫", "keywords": ["sacked","fired","dismissed","parts ways","relieved of","resign","resignation"], "priority": True},
    "OFFICIAL":      {"emoji": "✅", "keywords": ["official","confirmed","announced","unveiled","completed","done deal","sealed","here we go"], "priority": True},
    "BANNED":        {"emoji": "🚫", "keywords": ["banned","suspended","suspension","ban","sanction","disciplinary"], "priority": False},
    "APPOINTED":     {"emoji": "👔", "keywords": ["appointed","new manager","new coach","takes charge","named as","hired","unveiled as"], "priority": True},
    "INTERNATIONAL": {"emoji": "🌍", "keywords": ["world cup","euro","nations league","friendly","national team","squad called"], "priority": False},
}

QUALITY_KEYWORDS = [
    "transfer","sign","injury","contract","sack","appoint","ban","suspend",
    "confirm","official","breaking","deal","free agent","loan","fee","bid",
    "offer","agree","done","medical","unveil","leave","join","depart","arrive",
    "manager","coach","squad","premier league","la liga","serie a","bundesliga",
    "champions league","ligue 1","world cup","euro","international","friendly",
    "barcelona","real madrid","manchester","liverpool","arsenal","chelsea",
    "juventus","milan","inter","bayern","dortmund","psg","atletico","tottenham",
    "newcastle","england","france","spain","germany","brazil","argentina",
    "portugal","italy","netherlands","africa","malawi",
]

FILLER_KEYWORDS = [
    "5 things","player ratings","fan reaction","remember when","best goals",
    "quiz","ranked","watch:","video:","gallery:","photos:","how to watch",
    "tv channel","betting odds","predicted lineup","match preview",
]

# ── State ─────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(NEWS_STATE_FILE):
        try:
            with open(NEWS_STATE_FILE) as f:
                d = json.load(f)
                return (
                    d.get("last_post_time", 0),
                    d.get("posts_today", 0),
                    d.get("last_reset_date", ""),
                    set(d.get("posted_keys", [])),
                    d.get("source_index", 0),
                )
        except Exception:
            pass
    return 0, 0, "", set(), 0

last_post_time, posts_today, last_reset_date, posted_keys, source_index = load_state()

def save_state():
    with open(NEWS_STATE_FILE, "w") as f:
        json.dump({
            "last_post_time": last_post_time,
            "posts_today": posts_today,
            "last_reset_date": last_reset_date,
            "posted_keys": list(posted_keys)[-300:],
            "source_index": source_index,
        }, f)

# ── Groq ──────────────────────────────────────────────────────────
def ask_groq(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.7,
    }
    try:
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        print(f"[GROQ] Error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[GROQ] Exception: {e}")
    return None

# ── Facebook ──────────────────────────────────────────────────────
def post_to_facebook(message):
    try:
        r = requests.post(FB_POST_URL,
                          data={"message": message, "access_token": FB_TOKEN},
                          timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {message[:80]}...")
            return True
        print(f"[FB ERROR] {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[FB ERROR] {e}")
    return False

# ── Helpers ───────────────────────────────────────────────────────
def clean_key(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())[:80]

def detect_category(title, desc):
    text = (title + " " + desc).lower()
    for cat, info in CATEGORIES.items():
        if any(kw in text for kw in info["keywords"]):
            return cat, info["emoji"], info["priority"]
    return "NEWS", "📰", False

def is_quality(title, desc):
    text = (title + " " + desc).lower()
    if any(kw in text for kw in FILLER_KEYWORDS):
        return False
    return any(kw in text for kw in QUALITY_KEYWORDS)

def fetch_rss(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"[RSS ERROR] {url}: {e}")
    return None

# ── Write news post with Groq ─────────────────────────────────────
def write_news_post(category, emoji, title, desc, source):
    prompt = f"""You are a football Facebook page writer for ScoreLine Live.

Write an exciting Facebook post about this football news story.
Use ONLY the facts given — do NOT invent anything.

Category: {category}
Headline: {title}
Details: {desc}
Source: {source}

Format rules:
- Start with: {emoji} {category} |
- Write 2-3 clear, exciting sentences about the news in simple English
- Keep all player names and club names exactly as given
- Add relevant emojis throughout
- Add relevant hashtags at the end
- End with: Follow ScoreLine Live for updates 🔔
- Max 150 words
- ONLY use facts from the headline and details above
"""
    post = ask_groq(prompt)
    if not post:
        # Fallback plain post
        desc_short = desc[:150] + "..." if len(desc) > 150 else desc
        post = (
            f"{emoji} {category} | {title}\n\n"
            f"{desc_short}\n\n"
            f"📡 Source: {source}\n\n"
            f"Follow {PAGE_NAME} for updates 🔔"
        )
    return post

# ── Main news checker ─────────────────────────────────────────────
def check_news():
    global last_post_time, posts_today, last_reset_date, source_index, posted_keys

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        save_state()
        print("[NEWS] Daily counter reset.")

    if posts_today >= 30:
        print("[NEWS] Daily limit reached (30/30).")
        return

    elapsed = time.time() - last_post_time

    # Breaking news — check all feeds, post within 15 mins
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking for breaking news...")
    for feed in RSS_FEEDS:
        tree = fetch_rss(feed["url"])
        if not tree:
            continue
        items = tree.findall(".//item") or tree.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in items[:5]:
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue
            desc_el = item.find("description")
            desc = re.sub(r'<[^>]+>', '', (desc_el.text or "") if desc_el is not None else "").strip()
            category, emoji, is_priority = detect_category(title, desc)
            if not is_priority:
                continue
            if not is_quality(title, desc):
                continue
            key = clean_key(title)
            if key in posted_keys:
                continue
            post = write_news_post(category, emoji, title, desc, feed["name"])
            if post_to_facebook(post):
                posted_keys.add(key)
                last_post_time = time.time()
                posts_today += 1
                save_state()
                print(f"[NEWS] BREAKING posted ({posts_today}/30). Source: {feed['name']}")
                return

    # Regular news — check gap
    if elapsed < POST_INTERVAL:
        remaining = int((POST_INTERVAL - elapsed) / 60)
        print(f"[NEWS] Next regular news in {remaining} mins.")
        return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking regular news...")
    feeds_to_try = RSS_FEEDS[source_index:] + RSS_FEEDS[:source_index]

    for i, feed in enumerate(feeds_to_try):
        tree = fetch_rss(feed["url"])
        if not tree:
            continue
        items = tree.findall(".//item") or tree.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in items[:8]:
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue
            desc_el = item.find("description")
            desc = re.sub(r'<[^>]+>', '', (desc_el.text or "") if desc_el is not None else "").strip()
            if not is_quality(title, desc):
                continue
            key = clean_key(title)
            if key in posted_keys:
                continue
            category, emoji, _ = detect_category(title, desc)
            post = write_news_post(category, emoji, title, desc, feed["name"])
            if post_to_facebook(post):
                posted_keys.add(key)
                last_post_time = time.time()
                posts_today += 1
                source_index = (source_index + i + 1) % len(RSS_FEEDS)
                save_state()
                print(f"[NEWS] Posted ({posts_today}/30). Category: {category}. Source: {feed['name']}")
                return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No new quality stories found.")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print(f"{PAGE_NAME} News Bot started!")
    print("Sources  : BBC Sport, Sky Sports, Marca, TalkSPORT")
    print("Breaking : Posts within 15 minutes")
    print("Regular  : Every 45 minutes")
    print("Writing  : Groq AI for beautiful posts")
    print("Daily    : Max 30 news posts\n")
    while True:
        try:
            check_news()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(900)  # Check every 15 mins

if __name__ == "__main__":
    run()