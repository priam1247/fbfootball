import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")
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

def apifootball_get(path):
    if not APIFOOTBALL_KEY:
        print("[APIFOOTBALL] Missing key")
        return None
    try:
        r = requests.get(
            f"https://v3.football.api-sports.io{path}",
            headers={"x-rapidapi-host": "v3.football.api-sports.io", "x-rapidapi-key": APIFOOTBALL_KEY},
            timeout=15
        )
        print(f"[APIFOOTBALL] Status: {r.status_code}")
        data = r.json()
        return data.get("response", []) if data.get("results", 0) > 0 else []
    except Exception as e:
        print(f"[APIFOOTBALL ERROR] {e}")
        return []

def livescore_get(path):
    if not LIVESCORE_KEY or not LIVESCORE_SECRET:
        return {}
    try:
        sep = "&" if "?" in path else "?"
        r = requests.get(f"https://livescore-api.com/api-client{path}{sep}key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}", timeout=15)
        if r.status_code == 200:
            d = r.json()
            if d.get("success"):
                return d.get("data", {})
    except:
        pass
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

def norm_match(m):
    # Normalize API-Football format
    home = m.get("teams", {}).get("home", {}).get("name", "")
    away = m.get("teams", {}).get("away", {}).get("name", "")
    status = m.get("fixture", {}).get("status", {}).get("short", "NS")
    score = m.get("goals", {}) or {}

    status_map = {"1H": "IN_PLAY", "HT": "PAUSED", "2H": "IN_PLAY", "FT": "FINISHED", "NS": "SCHEDULED"}
    norm_status = status_map.get(status, "SCHEDULED")

    return {
        "id": f"af_{m.get('fixture', {}).get('id', '')}",
        "utcDate": m.get("fixture", {}).get("date", ""),
        "status": norm_status,
        "_comp_name": m.get("league", {}).get("name", "International Friendly"),
        "homeTeam": {"shortName": home},
        "awayTeam": {"shortName": away},
        "score": {"fullTime": {"home": score.get("home", 0), "away": score.get("away", 0)}}
    }

def is_important_match(m):
    home = str(m["homeTeam"].get("shortName", "")).strip()
    away = str(m["awayTeam"].get("shortName", "")).strip()
    comp = str(m.get("_comp_name", "")).lower()

    print(f"[DEBUG MATCH] {home} vs {away} | Comp: {comp}")

    if home in BIG_TEAMS or away in BIG_TEAMS:
        return True
    if any(k in comp for k in ["friendly", "finalissima", "fifa", "series", "nations"]):
        return True
    return False

def fetch_intl_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INTL] Fetching internationals for {today} using API-Football...")

    # Use API-Football for fixtures (much more reliable for scheduled internationals)
    fixtures = apifootball_get(f"/fixtures?date={today}&timezone=UTC")

    print(f"[INTL] Raw fixtures received: {len(fixtures)}")

    matches = []
    seen = set()
    for item in fixtures:
        if isinstance(item, dict):
            norm = norm_match(item)
            if is_important_match(norm):
                key = f"{norm['homeTeam']['shortName']}_{norm['awayTeam']['shortName']}"
                if key not in seen:
                    seen.add(key)
                    matches.append(norm)

    print(f"[INTL] Filtered important matches: {len(matches)}")
    return matches

# (Keep the rest of your functions: get_score, is_big_match, get_minute, handle_live_update, process, post_daily_preview, run)

def get_score(m):
    ft = m.get("score", {}).get("fullTime", {})
    return m["homeTeam"].get("shortName", ""), m["awayTeam"].get("shortName", ""), ft.get("home", 0), ft.get("away", 0)

def is_big_match(m):
    return m["homeTeam"].get("shortName", "") in BIG_TEAMS or m["awayTeam"].get("shortName", "") in BIG_TEAMS

def get_minute(m):
    try:
        ko = datetime.fromisoformat(m.get("utcDate", "").replace("Z", "+00:00"))
        elapsed = (datetime.utcnow() - ko).total_seconds() / 60
        return int(max(1, elapsed))
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
    post_to_facebook(f"📍 {minute}' | {home} {hs}–{as_} {away}\n\n🔥 Big match live!")

def process(m):
    status = m.get("status", "")
    if status == "IN_PLAY":
        key = f"{m['id']}_kickoff"
        if key not in posted_kickoffs:
            posted_kickoffs.add(key)
            save_state()
            post_to_facebook(f"🟢 KICK OFF | {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}")
        handle_live_update(m)
    elif status == "PAUSED":
        key = f"{m['id']}_halftime"
        if key not in posted_halftimes:
            posted_halftimes.add(key)
            save_state()
            home, away, hs, as_ = get_score(m)
            post_to_facebook(f"⏸️ HALF TIME | {home} {hs}–{as_} {away}")
    elif status == "FINISHED":
        key = f"{m['id']}_fulltime"
        if key not in posted_ft:
            posted_ft.add(key)
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
    print(f"{PAGE_NAME} Bot v3.0 – Using API-Football for fixtures")
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