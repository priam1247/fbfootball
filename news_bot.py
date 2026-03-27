import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN      = os.getenv("FB_TOKEN")
FB_PAGE_ID    = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY  = os.getenv("FOOTBALL_KEY")

FB_POST_URL    = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
FOOTBALL_BASE  = "https://api.football-data.org/v4"
NEWS_STATE_FILE = "news_state.json"

# ── All leagues + internationals for matchday detection ──────────
ALL_LEAGUES = [
    "PL","PD","SA","CL","BL1","FL1","DED","ELC","PPL","BSA","WC","EC"
]

# ── 5 trusted sources — rotating ─────────────────────────────────
RSS_FEEDS = [
    {"name": "BBC Sport",   "url": "https://feeds.bbci.co.uk/sport/football/rss.xml"},
    {"name": "Sky Sports",  "url": "https://www.skysports.com/rss/0,20514,11095,00.xml"},
    {"name": "Telegraph",   "url": "https://www.telegraph.co.uk/football/rss.xml"},
    {"name": "Marca",       "url": "https://e00-marca.uecdn.es/rss/en/index.xml"},
    {"name": "TalkSPORT",   "url": "https://talksport.com/feed"},
]

# ── Category detection ────────────────────────────────────────────
CATEGORIES = {
    "BREAKING": {
        "emoji": "🚨",
        "keywords": ["breaking", "just in", "urgent", "alert", "exclusive"],
        "priority": True
    },
    "TRANSFER": {
        "emoji": "🔴",
        "keywords": ["transfer", "signing", "signs", "sign", "move", "deal", "fee",
                     "loan", "free agent", "bid", "offer", "target", "want",
                     "interested", "approach", "agree", "done deal", "medical"],
        "priority": False
    },
    "INJURY": {
        "emoji": "🤕",
        "keywords": ["injury", "injured", "out for", "miss", "scan", "fitness",
                     "doubt", "ruled out", "surgery", "fracture", "muscle"],
        "priority": False
    },
    "CONTRACT": {
        "emoji": "📝",
        "keywords": ["contract", "extends", "extension", "renew", "renewal",
                     "new deal", "signs new", "until 20"],
        "priority": False
    },
    "SACKED": {
        "emoji": "🔫",
        "keywords": ["sacked", "fired", "dismissed", "parts ways",
                     "relieved of", "resign", "resignation"],
        "priority": True
    },
    "OFFICIAL": {
        "emoji": "✅",
        "keywords": ["official", "confirmed", "announced", "unveil", "unveiled",
                     "completed", "done deal", "sealed", "here we go"],
        "priority": True
    },
    "BANNED": {
        "emoji": "🚫",
        "keywords": ["banned", "suspended", "suspension", "ban", "sanction",
                     "disciplinary", "red card appeal"],
        "priority": False
    },
    "APPOINTED": {
        "emoji": "👔",
        "keywords": ["appointed", "new manager", "new coach", "takes charge",
                     "named as", "hired", "unveiled as"],
        "priority": True
    },
    "INTERNATIONAL": {
        "emoji": "🌍",
        "keywords": ["international", "world cup", "euro", "nations league",
                     "friendly", "national team", "squad called"],
        "priority": False
    },
}

# Quality — only real news
QUALITY_KEYWORDS = [
    "transfer", "sign", "injury", "contract", "sack", "appoint", "ban",
    "suspend", "confirm", "official", "breaking", "deal", "free agent",
    "loan", "fee", "bid", "offer", "agree", "done", "medical", "unveil",
    "leave", "join", "depart", "arrive", "manager", "coach", "squad",
    "premier league", "la liga", "serie a", "bundesliga", "champions league",
    "ligue 1", "eredivisie", "world cup", "euro", "international", "friendly",
    "national team", "nations league",
    "barcelona", "real madrid", "manchester", "liverpool", "arsenal",
    "chelsea", "juventus", "milan", "inter", "bayern", "dortmund",
    "psg", "atletico", "tottenham", "newcastle", "city", "united",
    "england", "france", "spain", "germany", "brazil", "argentina",
    "portugal", "italy", "netherlands", "africa", "malawi"
]

# Filler to skip
FILLER_KEYWORDS = [
    "5 things", "player ratings", "fan reaction", "remember when",
    "best goals", "worst goals", "quiz", "ranked", "every goal",
    "watch:", "video:", "gallery:", "photos:", "in pictures",
    "how to watch", "tv channel", "betting odds", "predicted lineup",
    "vs preview", "match preview", "ones to watch"
]

# Entity names for deduplication
PLAYER_NAMES = [
    "salah", "haaland", "mbappe", "vinicius", "bellingham", "saka",
    "odegaard", "de bruyne", "kane", "lewandowski", "messi", "ronaldo",
    "neymar", "rashford", "fernandes", "rice", "rodri", "pedri",
    "yamal", "gavi", "ter stegen", "alisson", "ederson", "courtois",
    "modric", "benzema", "griezmann", "dembele", "camavinga", "valverde"
]

CLUB_NAMES = [
    "liverpool", "manchester city", "manchester united", "arsenal", "chelsea",
    "tottenham", "newcastle", "barcelona", "real madrid", "atletico",
    "juventus", "milan", "inter", "napoli", "bayern", "dortmund",
    "psg", "ajax", "porto", "benfica", "celtic", "rangers", "lazio", "roma"
]

# ── Free template rewriter ────────────────────────────────────────
# Remove journalist fluff — keep all names intact
CLEAN_PHRASES = [
    (r"'[^']*'\s*[-–—:]\s*", ""),          # Remove 'quote' - prefix
    (r'"[^"]*"\s*[-–—:]\s*', ""),           # Remove "quote" - prefix
    (r"\baccording to reports\b[,]?", ""),
    (r"\bit has been claimed that\b", ""),
    (r"\bit is understood that\b", ""),
    (r"\bit is believed that\b", ""),
    (r"\bsources have told\b.*?(?=\.|$)", ""),
    (r"\bexclusive:\s*", ""),
    (r"\bbreaking:\s*", ""),
    (r"\breport:\s*", ""),
    (r"\breports:\s*", ""),
    (r"\bwatch:\s*", ""),
    (r"\banalysis:\s*", ""),
    (r"\[\d+\]", ""),
    (r"\s{2,}", " "),
]

# Replace complex words with simple ones — NEVER replace names
WORD_REPLACEMENTS = [
    ("depart from",           "leave"),
    ("departs from",          "leaves"),
    ("departed from",         "left"),
    ("terminate his contract", "end his contract"),
    ("contractual agreement", "contract"),
    ("upon expiration of his","when his contract at"),
    ("upon expiration of her","when her contract at"),
    ("is set to",             "will"),
    ("are set to",            "will"),
    ("amid growing",          "as"),
    ("following the",         "after the"),
    ("securing a",            "getting a"),
    ("approximately",         "about"),
    ("remainder of the",      "rest of the"),
    ("in the coming weeks",   "soon"),
    ("in the near future",    "soon"),
    ("it has emerged that",   ""),
    ("has emerged that",      ""),
]

def simplify_title(title):
    """Clean journalist fluff but keep all player and club names exactly."""
    text = title.strip()
    for pattern, replacement in CLEAN_PHRASES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    for old, new in WORD_REPLACEMENTS:
        text = re.sub(r'\b' + re.escape(old) + r'\b', new, text,
                      flags=re.IGNORECASE)
    # Clean up double spaces and capitalize first letter only
    text = re.sub(r'\s{2,}', ' ', text).strip()
    if text:
        text = text[0].upper() + text[1:]
    return text

def build_simple_sentence(title, desc):
    """
    Build a clean 1-2 sentence post in simple English.
    Keep all player names, club names and facts exactly as they are.
    Only remove journalist language and replace complex words.
    """
    clean = simplify_title(title)
    text  = clean

    # Add one sentence from description if it adds new information
    if desc:
        desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
        desc_clean = re.sub(r'\s+', ' ', desc_clean)
        # Take first meaningful sentence
        sentences = [s.strip() for s in desc_clean.split('.') if len(s.strip()) > 20]
        if sentences:
            first = sentences[0]
            # Only add if it contains new information not already in title
            title_words = set(clean.lower().split())
            first_words = set(first.lower().split())
            overlap = len(title_words & first_words) / max(len(first_words), 1)
            if overlap < 0.6:  # Less than 60% overlap = new info
                for old, new in WORD_REPLACEMENTS:
                    first = re.sub(r'\b' + re.escape(old) + r'\b', new,
                                   first, flags=re.IGNORECASE)
                first = first.strip()
                if first and len(text) + len(first) < 280:
                    text = f"{clean}. {first[0].upper() + first[1:]}"

    if text and not text.endswith('.'):
        text += '.'
    return text

# ── Persistent state ──────────────────────────────────────────────
def load_news_state():
    if os.path.exists(NEWS_STATE_FILE):
        try:
            with open(NEWS_STATE_FILE, "r") as f:
                data = json.load(f)
                return (
                    set(data.get("posted_keys", [])),
                    data.get("last_post_time", 0),
                    data.get("posts_today", 0),
                    data.get("last_reset_date", ""),
                    list(data.get("recent_entities", [])),
                    data.get("source_index", 0),
                )
        except Exception:
            pass
    return set(), 0, 0, "", [], 0

def save_news_state(posted_keys, last_post_time, posts_today,
                    last_reset_date, recent_entities, source_index):
    with open(NEWS_STATE_FILE, "w") as f:
        json.dump({
            "posted_keys":     list(posted_keys),
            "last_post_time":  last_post_time,
            "posts_today":     posts_today,
            "last_reset_date": last_reset_date,
            "recent_entities": list(recent_entities)[-100:],
            "source_index":    source_index,
        }, f)

(posted_keys, last_post_time,
 posts_today, last_reset_date,
 recent_entities, source_index) = load_news_state()

# ── Helpers ───────────────────────────────────────────────────────
def clean_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9 ]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title

def detect_category(title, desc=""):
    text = (title + " " + desc).lower()
    for cat_name, cat_data in CATEGORIES.items():
        if any(kw in text for kw in cat_data["keywords"]):
            return cat_name, cat_data["emoji"], cat_data["priority"]
    return "NEWS", "📰", False

def is_quality_story(title, desc=""):
    text = (title + " " + desc).lower()
    if any(filler in text for filler in FILLER_KEYWORDS):
        return False
    return any(kw in text for kw in QUALITY_KEYWORDS)

def extract_entities(title):
    text = title.lower()
    return [n for n in PLAYER_NAMES + CLUB_NAMES if n in text]

def is_duplicate_entity(title):
    entities = extract_entities(title)
    now = time.time()
    for entry in recent_entities:
        if now - entry.get("time", 0) < 14400:
            if set(entities) & set(entry.get("entities", [])) and entities:
                return True
    return False

def add_entity_record(title):
    entities = extract_entities(title)
    if entities:
        recent_entities.append({"time": time.time(), "entities": entities})

def is_matchday():
    """Check league matches AND international friendlies."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Check all league competitions
    for code in ALL_LEAGUES:
        try:
            headers = {"X-Auth-Token": FOOTBALL_KEY}
            r = requests.get(
                f"{FOOTBALL_BASE}/competitions/{code}/matches"
                f"?dateFrom={today}&dateTo={today}",
                headers=headers, timeout=8
            )
            if r.status_code == 200 and r.json().get("matches"):
                print(f"[NEWS] Matchday detected: {code}")
                return True
        except Exception:
            pass

    # Also check general matches endpoint for friendlies
    try:
        headers = {"X-Auth-Token": FOOTBALL_KEY}
        r = requests.get(
            f"{FOOTBALL_BASE}/matches?dateFrom={today}&dateTo={today}",
            headers=headers, timeout=8
        )
        if r.status_code == 200 and r.json().get("matches"):
            print(f"[NEWS] International/friendly matches detected today")
            return True
    except Exception:
        pass

    return False

def fetch_rss(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"[ERROR] RSS fetch failed for {url}: {e}")
    return None

def post_to_facebook(message):
    payload = {"message": message, "access_token": FB_TOKEN}
    r = requests.post(FB_POST_URL, data=payload, timeout=10)
    if r.status_code == 200:
        print(f"[POSTED] {message[:80]}...")
        return True
    print(f"[ERROR] FB post failed: {r.status_code} {r.text}")
    return False

def format_post(category, emoji, body, source):
    return (
        f"{emoji} {category} | {body}\n\n"
        f"📡 Source: {source}\n\n"
        f"Follow ScoreLine Live for updates 🔔"
    )

# ── Main news checker ─────────────────────────────────────────────
def check_news():
    global last_post_time, posts_today, last_reset_date, source_index

    # Reset daily counter
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        print(f"[NEWS] Daily counter reset.")

    # Max 30 posts per day
    if posts_today >= 30:
        print(f"[NEWS] Daily limit reached (30/30).")
        return

    now_ts  = time.time()
    elapsed = now_ts - last_post_time

    # First check ALL sources for BREAKING/OFFICIAL/SACKED/APPOINTED
    # These post within 15 minutes regardless of gap
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking for breaking news...")
    for feed in RSS_FEEDS:
        tree = fetch_rss(feed["url"])
        if tree is None:
            continue
        items = (tree.findall(".//item") or
                 tree.findall(".//{http://www.w3.org/2005/Atom}entry"))
        for item in items[:5]:
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue
            desc_el = item.find("description")
            desc = re.sub(r'<[^>]+>', '',
                          (desc_el.text or "") if desc_el is not None else "").strip()
            category, emoji, is_priority = detect_category(title, desc)
            if not is_priority:
                continue
            if not is_quality_story(title, desc):
                continue
            key = clean_title(title)
            if key in posted_keys:
                continue
            if is_duplicate_entity(title):
                posted_keys.add(key)
                continue
            # Post breaking news immediately
            body = build_simple_sentence(title, desc)
            msg  = format_post(category, emoji, body, feed["name"])
            if post_to_facebook(msg):
                posted_keys.add(key)
                add_entity_record(title)
                last_post_time = time.time()
                posts_today += 1
                save_news_state(posted_keys, last_post_time, posts_today,
                                last_reset_date, recent_entities, source_index)
                print(f"[NEWS] BREAKING posted ({posts_today}/30). Source: {feed['name']}")
                return

    # Regular news — check time gap
    matchday  = is_matchday()
    gap       = 7200 if matchday else 2700
    gap_label = "2 hrs (matchday)" if matchday else "45 mins (no games)"
    remaining = int((gap - elapsed) / 60)

    if elapsed < gap:
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
              f"Next regular news in {remaining} mins ({gap_label})")
        return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking regular news...")

    # True round-robin rotation — cycle through all 5 sources evenly
    feeds_to_try = (RSS_FEEDS[source_index:] + RSS_FEEDS[:source_index])

    for i, feed in enumerate(feeds_to_try):
        tree = fetch_rss(feed["url"])
        if tree is None:
            continue
        items = (tree.findall(".//item") or
                 tree.findall(".//{http://www.w3.org/2005/Atom}entry"))
        for item in items[:8]:
            title_el = item.find("title")
            if title_el is None:
                continue
            title = (title_el.text or "").strip()
            if not title:
                continue
            desc_el = item.find("description")
            desc = re.sub(r'<[^>]+>', '',
                          (desc_el.text or "") if desc_el is not None else "").strip()
            if not is_quality_story(title, desc):
                continue
            key = clean_title(title)
            if key in posted_keys:
                continue
            if is_duplicate_entity(title):
                posted_keys.add(key)
                continue
            category, emoji, _ = detect_category(title, desc)
            body = build_simple_sentence(title, desc)
            msg  = format_post(category, emoji, body, feed["name"])
            if post_to_facebook(msg):
                posted_keys.add(key)
                add_entity_record(title)
                last_post_time = time.time()
                posts_today   += 1
                # Advance rotation to next source
                source_index = (source_index + i + 1) % len(RSS_FEEDS)
                save_news_state(posted_keys, last_post_time, posts_today,
                                last_reset_date, recent_entities, source_index)
                print(f"[NEWS] Posted ({posts_today}/30). "
                      f"Category: {category}. Source: {feed['name']}")
                return

    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No new quality stories.")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print("ScoreLine Live News Bot started...")
    print("Sources: BBC Sport, Sky Sports, Telegraph, Marca, TalkSPORT")
    print("Breaking news: posts within 15 minutes")
    print("Regular news: 45 mins (no games) / 2 hrs (matchday)")
    print("International friendlies: detected automatically")
    print("Duplicate filter: ON — source rotation: ON\n")

    while True:
        try:
            check_news()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(900)  # Check every 15 minutes

if __name__ == "__main__":
    run()
