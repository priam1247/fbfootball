import os, json, time, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
GEMINI_KEY = os.getenv("GEMINI_KEY")

FB_POST_URL = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
GEMINI_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent?key={GEMINI_KEY}"
NEWS_STATE_FILE = "news_state.json"

# ── State ─────────────────────────────────────────────────────────
def load_news_state():
    if os.path.exists(NEWS_STATE_FILE):
        try:
            with open(NEWS_STATE_FILE) as f:
                d = json.load(f)
                return (d.get("last_post_time", 0),
                        d.get("posts_today", 0),
                        d.get("last_reset_date", ""),
                        set(d.get("posted_headlines", [])))
        except Exception:
            pass
    return 0, 0, "", set()

last_post_time, posts_today, last_reset_date, posted_headlines = load_news_state()

def save_news_state():
    with open(NEWS_STATE_FILE, "w") as f:
        json.dump({
            "last_post_time": last_post_time,
            "posts_today": posts_today,
            "last_reset_date": last_reset_date,
            "posted_headlines": list(posted_headlines)[-100:],  # keep last 100
        }, f)

# ── Gemini API call with Google Search ───────────────────────────
def ask_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 600}
    }
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        print(f"[GEMINI] Error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[GEMINI] Exception: {e}")
    return None

# ── Facebook post ─────────────────────────────────────────────────
def post_to_facebook(message):
    try:
        r = requests.post(FB_POST_URL,
                          data={"message": message, "access_token": FB_TOKEN},
                          timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {message[:80]}...")
            return True
        print(f"[ERROR] FB failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] FB exception: {e}")
    return False

# ── Check for news ────────────────────────────────────────────────
def check_news():
    global last_post_time, posts_today, last_reset_date, posted_headlines

    # Reset daily counter
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        save_news_state()
        print("[NEWS] Daily counter reset.")

    # Max 15 news posts per day
    if posts_today >= 15:
        print(f"[NEWS] Daily limit reached (15/15).")
        return

    elapsed = time.time() - last_post_time

    # Breaking news check every 30 mins
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking football news...")

    prompt = f"""Search for the latest football news right now ({datetime.utcnow().strftime('%H:%M UTC, %d %B %Y')}).

Look for BREAKING or important news in these categories:
- Transfer deals (signings, bids, done deals)
- Manager sackings or appointments  
- Injuries to top players
- Contract extensions
- Suspensions or bans
- Official announcements

Already posted these headlines (DO NOT repeat): {list(posted_headlines)[-20:]}

If you find genuinely new important football news:
Write a Facebook post for ScoreLine Live page.
- Start with the right emoji and category: 🚨 BREAKING, 🔴 TRANSFER, 🤕 INJURY, 📝 CONTRACT, 🔫 SACKED, ✅ OFFICIAL, 👔 APPOINTED, 🚫 BANNED
- Write 2-3 clear sentences about the news in simple English
- Add relevant hashtags
- End with "Follow ScoreLine Live for updates 🔔"
- Max 200 words

If there is NO new important news, respond with exactly: NO_NEWS
"""
    response = ask_gemini(prompt)

    if not response or response.strip() == "NO_NEWS":
        remaining = int((2700 - elapsed) / 60) if elapsed < 2700 else 0
        print(f"[NEWS] No new stories. Next check in 30 mins.")
        return

    # Simple dedup — check if first 60 chars already posted
    key = response[:60].strip()
    if key in posted_headlines:
        print("[NEWS] Duplicate detected, skipping.")
        return

    if post_to_facebook(response):
        posted_headlines.add(key)
        last_post_time = time.time()
        posts_today += 1
        save_news_state()
        print(f"[NEWS] Posted ({posts_today}/15 today).")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print("ScoreLine Live News Bot (Gemini Edition) started!")
    print("Powered by: Google Gemini + Google Search")
    print("Checks: Every 30 minutes for breaking news")
    print("Daily limit: 15 posts\n")
    while True:
        try:
            check_news()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(1800)  # Check every 30 minutes

if __name__ == "__main__":
    run()