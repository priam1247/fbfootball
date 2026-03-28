import os, json, time, random, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
GEMINI_KEY = os.getenv("GEMINI_KEY")

FB_POST_URL  = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
STATE_FILE   = "match_state.json"
PAGE_NAME    = "ScoreLine Live"

# ── Fan engagement questions ──────────────────────────────────────
GOAL_Q    = ["Who saw that coming? 😱","What a strike! Did you see it live? 👀",
              "The crowd is going wild! 🔥","Class finish! Drop a ⚽ if you saw it!",
              "Game changer! Who wins from here? 👇"]
HT_Q      = ["Who has impressed you most so far? 👇",
              "What changes do you expect in the second half? 🤔",
              "Still anyone's game! Your prediction? 👇",
              "Which team has been better so far? 👇"]
FT_Q      = ["Who was your Man of the Match? 🏆 Drop your pick 👇",
              "What's your reaction? 👇","Did you predict this result? 🤔",
              "Fair result or did one team deserve more? 👇",
              "Rate this match out of 10 👇"]
PREVIEW_Q = ["Which game are you watching today? 👀",
              "Who's your pick for biggest match today? 👇",
              "Big day of football! Who wins today? 🏆"]

# ── Filler posts for quiet times ──────────────────────────────────
FILLER_POSTS = [
    "🔥 DEBATE | Messi vs Ronaldo — who is the GOAT? Drop your vote 👇\n\n#Messi #Ronaldo #GOATDebate #Football",
    "⚔️ DEBATE | Haaland vs Mbappe — who will be the best in 5 years? 👑\n\n#Haaland #Mbappe #Football",
    "🐐 LEGEND | Ronaldinho — pure magic. One of the greatest entertainers ever 🔥\n\nAgree? 👇\n\n#Ronaldinho #Legend",
    "🐐 LEGEND | Zidane won the World Cup, Euro and Champions League. Top 5 ever? 👇\n\n#Zidane #Legend",
    "😱 DID YOU KNOW | Brazil is the only country in every single World Cup 🇧🇷\n\nDrop a 🇧🇷 if you knew!\n\n#Brazil #WorldCup",
    "📣 POLL | Best league in the world right now?\n\n🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League\n🇪🇸 La Liga\n🇩🇪 Bundesliga\n🇮🇹 Serie A\n\n👇\n\n#Football #Poll",
    "🌍 WORLD CUP 2026 | Who wins it? 🏆\n\nDrop your pick 👇\n\n#WorldCup2026 #FIFA #Football",
    "🌍 WORLD CUP 2026 | 48 teams, 104 matches across USA, Canada and Mexico! 🔥\n\nExcited? 👇\n\n#WorldCup2026",
    "📣 POLL | Who is the best young player in the world?\n\n⭐ Yamal\n⭐ Bellingham\n⭐ Endrick\n⭐ Camavinga\n\n👇\n\n#Football #NextGen",
    "📌 RECORD | Ronaldo — all-time top scorer in international football 🇵🇹\n\nWill anyone beat this? 👇\n\n#Ronaldo #Record",
]

# ── State ─────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                return (d.get("last_post_time", 0),
                        d.get("last_filler_time", 0),
                        d.get("preview_posted", ""),
                        set(d.get("filler_posted", [])),
                        d.get("posts_today", 0),
                        d.get("last_reset_date", ""))
        except Exception:
            pass
    return 0, 0, "", set(), 0, ""

last_post_time, last_filler_time, preview_posted, posted_filler, posts_today, last_reset_date = load_state()

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({
            "last_post_time": last_post_time,
            "last_filler_time": last_filler_time,
            "preview_posted": preview_posted,
            "filler_posted": list(posted_filler),
            "posts_today": posts_today,
            "last_reset_date": last_reset_date,
        }, f)

# ── Gemini API call with Google Search ───────────────────────────
def ask_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800}
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
        print(f"[ERROR] FB post failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] FB post exception: {e}")
    return False

# ── Daily preview ─────────────────────────────────────────────────
def handle_preview():
    global preview_posted, posts_today, last_post_time
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if preview_posted == today:
        return

    print("[BOT] Generating daily preview...")
    prompt = f"""Today is {datetime.utcnow().strftime('%A %d %B %Y')}.
Search for all major football matches scheduled today across Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, and international fixtures.

Write a Facebook post for a football page called ScoreLine Live.
Format it like this:
- Start with "⚽ TODAY'S BIG MATCHES" 
- List the top 5-8 matches with kickoff times (UTC) and league flags
- End with a fan engagement question and relevant hashtags
- Keep it exciting and engaging
- Max 300 words
- End with "Follow ScoreLine Live for live updates 🔔"
"""
    post = ask_gemini(prompt)
    if post and post_to_facebook(post):
        preview_posted = today
        posts_today += 1
        last_post_time = time.time()
        save_state()
        print(f"[BOT] Daily preview posted.")

# ── Live scores update ────────────────────────────────────────────
def handle_live_scores():
    global posts_today, last_post_time
    print("[BOT] Checking live scores...")
    prompt = f"""Search for football matches that are currently LIVE or finished in the last 2 hours right now ({datetime.utcnow().strftime('%H:%M UTC, %d %B %Y')}).

Write a Facebook post for ScoreLine Live page.
- If there are live matches: show current scores with minute, goalscorers, league flags
- If matches just finished: show final scores and results
- Start with "🔴 LIVE SCORES" or "🏁 FULL TIME RESULTS"
- Include goalscorers if available
- Add fan engagement question at the end
- Add relevant hashtags
- End with "Follow ScoreLine Live for live updates 🔔"
- Max 250 words
- If no live matches or recent results found, respond with exactly: NO_LIVE
"""
    post = ask_gemini(prompt)
    if not post or post.strip() == "NO_LIVE":
        print("[BOT] No live matches right now.")
        return False

    if post_to_facebook(post):
        posts_today += 1
        last_post_time = time.time()
        save_state()
        print(f"[BOT] Live scores posted ({posts_today}/20 today).")
        return True
    return False

# ── Filler post ───────────────────────────────────────────────────
def handle_filler():
    global last_filler_time, posted_filler, posts_today, last_post_time
    now = time.time()
    if now - last_filler_time < 3600:
        return
    avail = [p for p in FILLER_POSTS if p[:50] not in posted_filler]
    if not avail:
        posted_filler.clear()
        avail = FILLER_POSTS
    post = random.choice(avail)
    if post_to_facebook(post):
        posted_filler.add(post[:50])
        last_filler_time = now
        posts_today += 1
        last_post_time = time.time()
        save_state()
        print("[BOT] Filler posted.")

# ── Main cycle ────────────────────────────────────────────────────
def check_matches():
    global posts_today, last_reset_date, last_post_time

    # Reset daily counter
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    if today_str != last_reset_date:
        posts_today = 0
        last_reset_date = today_str
        save_state()
        print("[BOT] Daily counter reset.")

    # Max 20 posts per day to save Gemini quota
    if posts_today >= 20:
        print(f"[BOT] Daily limit reached (20/20).")
        return

    now_hour = datetime.utcnow().hour

    # Daily preview at 6 AM UTC
    if 6 <= now_hour <= 8:
        handle_preview()

    # Check live scores every 30 minutes
    elapsed = time.time() - last_post_time
    if elapsed >= 1800:
        live = handle_live_scores()
        if not live:
            handle_filler()
    else:
        remaining = int((1800 - elapsed) / 60)
        print(f"[BOT] Next check in {remaining} mins.")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print(f"{PAGE_NAME} Match Bot (Gemini Edition) started!")
    print("Powered by: Google Gemini + Google Search")
    print("Posts: Daily preview + Live scores every 30 mins")
    print("Daily limit: 20 posts\n")
    while True:
        try:
            check_matches()
        except Exception as e:
            print(f"[ERROR] {e}")
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checked. Waiting 5 mins...")
        time.sleep(300)

if __name__ == "__main__":
    run()