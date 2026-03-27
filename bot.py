import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
LIVESCORE_KEY    = os.getenv("LIVESCORE_KEY")
LIVESCORE_SECRET = os.getenv("LIVESCORE_SECRET")

FB_POST_URL      = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
STATE_FILE       = "match_state.json"
PAGE_NAME        = "ScoreLine Live"

LIVE_UPDATE_INTERVAL = 300

BIG_TEAMS = {
    "England", "Spain", "Germany", "France", "Brazil", "Argentina", "Portugal",
    "Italy", "Netherlands", "Belgium", "Uruguay", "Switzerland", "Norway", "Serbia",
    "Morocco", "Nigeria", "Ghana", "Ivory Coast", "USA", "Japan", "South Korea",
    "Kenya", "Estonia"
}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                return set(d.get("goals", [])), set(d.get("kickoffs", [])), set(d.get("halftimes", [])), set(d.get("fulltimes", [])), d.get("match_last_update", {})
        except:
            pass
    return set(), set(), set(), set(), {}

posted_goals, posted_kickoffs, posted_halftimes, posted_ft, match_last_update = load_state()

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({
            "goals": list(posted_goals),
            "kickoffs": list(posted_kickoffs),
            "halftimes": list(posted_halftimes),
            "fulltimes": list(posted_ft),
            "match_last_update": match_last_update
        }, f)

def livescore_get(path):
    if not LIVESCORE_KEY or not LIVESCORE_SECRET:
        return None
    try:
        sep = "&" if "?" in path else "?"
        r = requests.get(f"https://livescore-api.com/api-client{path}{sep}key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}", timeout=15)
        print(f"[LIVESCORE] Status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            if d.get("success"):
                return d.get("data", {})
    except Exception as e:
        print(f"[LIVESCORE ERROR] {e}")
    return {}

def post_to_facebook(msg):
    try:
        r = requests.post(FB_POST_URL, data={"message": msg, "access_token": FB_TOKEN}, timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {msg[:80]}...")
            return True
    except Exception as e:
        print(f"[FB ERROR] {e}")
    return False

# Fixed Normalization for real Livescore structure
def norm_ls(m):
    def clean(name):
        if not name: return ""
        name = str(name).strip()
        name = name.replace("The Netherlands", "Netherlands").replace("U21", "").replace("Women", "").strip()
        return name

    home = clean(m.get("home", {}).get("name") or m.get("home_name"))
    away = clean(m.get("away", {}).get("name") or m.get("away_name"))

    # Score
    hs = as_ = 0
    scores = m.get("scores", {}) or {}
    score_str = scores.get("score", "")
    if score_str and "-" in score_str:
        try:
            parts = score_str.replace(" ", "").split("-")
            hs, as_ = int(parts[0]), int(parts[1])
        except:
            pass

    # Status
    raw = str(m.get("status", "")).upper()
    status = {"IN PLAY": "IN_PLAY", "HALF TIME": "PAUSED", "FULL TIME": "FINISHED", "LIVE": "IN_PLAY"}.get(raw, "SCHEDULED")

    comp = m.get("competition", {})
    comp_name = comp.get("name", "International Friendly") if isinstance(comp, dict) else "International Friendly"

    return {
        "id": f"ls_{m.get('id','')}",
        "utcDate": f"{m.get('date','')}T{m.get('scheduled','00:00')}:00Z",
        "status": status,
        "_comp_name": comp_name,
        "homeTeam": {"shortName": home},
        "awayTeam": {"shortName": away},
        "score": {"fullTime": {"home": hs, "away": as_}},
        "goals": []
    }

def is_important_match(m):
    home = str(m["homeTeam"].get("shortName", "")).strip()
    away = str(m["awayTeam"].get("shortName", "")).strip()
    comp = str(m.get("_comp_name", "")).lower()

    print(f"[DEBUG MATCH] {home} vs {away} | Comp: {comp}")

    if home in BIG_TEAMS or away in BIG_TEAMS:
        return True
    if any(k in comp for k in ["friendly", "fifa", "finalissima", "series", "nations", "international"]):
        return True
    return False

def fetch_intl_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INTL] Fetching internationals for {today}...")

    matches = []
    seen = set()

    data = livescore_get(f"/fixtures/matches.json?date={today}")
    items = data.get("match", []) if isinstance(data, dict) else []

    print(f"[INTL] Raw matches received: {len(items)}")

    for item in items:
        if isinstance(item, dict):
            norm = norm_ls(item)
            if is_important_match(norm):
                key = f"{norm['homeTeam']['shortName']}_{norm['awayTeam']['shortName']}"
                if key not in seen:
                    seen.add(key)
                    matches.append(norm)

    print(f"[INTL] Filtered important matches: {len(matches)}")
    return matches

# Keep your original helpers & process functions (simplified for speed)
def get_score(m):
    ft = m.get("score", {}).get("fullTime", {})
    return m["homeTeam"].get("shortName", ""), m["awayTeam"].get("shortName", ""), ft.get("home", 0), ft.get("away", 0)

def is_big_match(m):
    return m["homeTeam"].get("shortName", "") in BIG_TEAMS or m["awayTeam"].get("shortName", "") in BIG_TEAMS

def get_minute(m):
    try:
        ko = datetime.strptime(m.get("utcDate", ""), "%Y-%m-%dT%H:%M:%SZ")
        return int(max(1, (datetime.utcnow() - ko).total_seconds() / 60))
    except:
        return "?"

def handle_live_update(m):
    if not is_big_match(m): return
    mid = m["id"]
    if time.time() - match_last_update.get(mid, 0) < LIVE_UPDATE_INTERVAL: return
    home, away, hs, as_ = get_score(m)
    minute = get_minute(m)
    match_last_update[mid] = time.time()
    save_state()
    msg = f"📍 {minute}' | {home} {hs}–{as_} {away}\n\n🔥 Big match live!"
    post_to_facebook(msg)

def process(m):
    status = m.get("status", "")
    if status == "IN_PLAY":
        key = f"{m['id']}_kickoff"
        if key not in posted_kickoffs:
            posted_kickoffs.add(key)
            save_state()
            post_to_facebook(f"🟢 KICK OFF | {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}")
        handle_live_update(m)
    elif status == "PAUSED" and f"{m['id']}_halftime" not in posted_halftimes:
        posted_halftimes.add(f"{m['id']}_halftime")
        save_state()
        home, away, hs, as_ = get_score(m)
        post_to_facebook(f"⏸️ HALF TIME | {home} {hs}–{as_} {away}")
    elif status == "FINISHED" and f"{m['id']}_fulltime" not in posted_ft:
        posted_ft.add(f"{m['id']}_fulltime")
        save_state()
        home, away, hs, as_ = get_score(m)
        post_to_facebook(f"🏁 FULL TIME | {home} {hs}–{as_} {away}")

def post_daily_preview(matches):
    big = [m for m in matches if is_big_match(m)]
    if not big: return
    lines = [f"🔥 TODAY'S BIG INTERNATIONAL MATCHES ({datetime.utcnow().strftime('%d %b %Y')})\n"]
    for m in big:
        lines.append(f"⚔️ {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}")
    lines.append("\nFollow ScoreLine Live 🔔")
    post_to_facebook("\n".join(lines))

def run():
    print(f"{PAGE_NAME} Bot v2.8 – Quick API Fix")
    preview_posted = False
    while True:
        try:
            matches = fetch_intl_today()
            if not preview_posted and matches:
                post_daily_preview(matches)
                preview_posted = True
            for m in matches[:15]:
                process(m)
            print(f"[DEBUG] Tracking {len(matches)} important matches")
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(60)

if __name__ == "__main__":
    run()