import os
import json
import time
import random
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ====================== RAILWAY VARIABLES ======================
FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")
LIVESCORE_KEY    = os.getenv("LIVESCORE_KEY")
LIVESCORE_SECRET = os.getenv("LIVESCORE_SECRET")

FB_POST_URL      = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
STATE_FILE       = "match_state.json"
PAGE_NAME        = "ScoreLine Live"

LIVE_UPDATE_INTERVAL = 300  # 5 minutes

# ====================== BIG TEAMS ======================
BIG_TEAMS = {
    "England", "Spain", "Germany", "France", "Brazil", "Argentina", "Portugal",
    "Italy", "Netherlands", "Belgium", "Uruguay", "Switzerland", "Norway", "Serbia",
    "Morocco", "Nigeria", "Ghana", "Ivory Coast", "USA", "Japan", "South Korea"
}

# ====================== STATE MANAGEMENT ======================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                return (
                    set(d.get("goals", [])),
                    set(d.get("kickoffs", [])),
                    set(d.get("halftimes", [])),
                    set(d.get("fulltimes", [])),
                    d.get("match_last_update", {})
                )
        except Exception:
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

# ====================== API HELPERS ======================
def livescore_get(path):
    if not LIVESCORE_KEY or not LIVESCORE_SECRET:
        return None
    try:
        sep = "&" if "?" in path else "?"
        r = requests.get(
            f"https://livescore-api.com/api-client{path}{sep}key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}",
            timeout=10
        )
        if r.status_code == 200:
            d = r.json()
            return d.get("data", d) if d.get("success") else None
    except Exception as e:
        print(f"[LIVESCORE ERROR] {e}")
    return None

def apifootball_get(path):
    if not APIFOOTBALL_KEY:
        return None
    try:
        r = requests.get(
            f"https://v3.football.api-sports.io{path}",
            headers={
                "x-rapidapi-host": "v3.football.api-sports.io",
                "x-rapidapi-key": APIFOOTBALL_KEY
            },
            timeout=10
        )
        d = r.json()
        return d if not d.get("errors") else None
    except Exception:
        return None

def post_to_facebook(msg):
    try:
        r = requests.post(FB_POST_URL, data={"message": msg, "access_token": FB_TOKEN}, timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {msg[:75]}...")
            return True
        print(f"[FB ERROR] {r.status_code}")
    except Exception as e:
        print(f"[FB ERROR] {e}")
    return False

# ====================== NORMALIZATION ======================
def norm_ls(m):
    def safe_name(field):
        if isinstance(field, dict):
            return field.get("name", "") or str(field)
        if isinstance(field, str):
            return field.strip()
        return str(field or "")

    home = m.get("home_name") or safe_name(m.get("home")) or ""
    away = m.get("away_name") or safe_name(m.get("away")) or ""

    hs = as_ = None
    try:
        score_raw = str(m.get("score", ""))
        if ":" in score_raw:
            p = score_raw.replace(" ", "").split(":")
            if len(p) == 2 and p[0].isdigit():
                hs, as_ = int(p[0]), int(p[1])
    except:
        pass

    raw = str(m.get("status") or "NOT STARTED").upper()
    status = {"IN PLAY": "IN_PLAY", "HALF TIME": "PAUSED", "FULL TIME": "FINISHED", "LIVE": "IN_PLAY"}.get(raw, "SCHEDULED")

    return {
        "id": f"ls_{m.get('id','')}",
        "utcDate": f"{m.get('date','')}T{m.get('time','00:00')}:00Z",
        "status": status,
        "_comp_name": m.get("competition", "International Friendly"),
        "homeTeam": {"shortName": home},
        "awayTeam": {"shortName": away},
        "score": {"fullTime": {"home": hs, "away": as_}},
        "goals": m.get("events", []) if isinstance(m.get("events"), list) else []
    }

# ====================== FILTERING ======================
def is_important_match(m):
    home = m["homeTeam"].get("shortName", "")
    away = m["awayTeam"].get("shortName", "")
    if home in BIG_TEAMS or away in BIG_TEAMS:
        return True
    comp = m.get("_comp_name", "").lower()
    if any(word in comp for word in ["friendly", "nations", "world cup", "euro", "finalissima"]):
        return True
    return False

def fetch_intl_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INTL] Fetching important internationals ({today})...")

    matches = []
    seen = set()

    def add(m):
        key = f"{m['homeTeam']['shortName']}_{m['awayTeam']['shortName']}"
        if key not in seen:
            seen.add(key)
            matches.append(m)

    # Livescore
    data = livescore_get(f"/fixtures/matches.json?date={today}")
    if data:
        items = data if isinstance(data, list) else data.get("match", [])
        for item in items:
            if isinstance(item, dict):
                norm = norm_ls(item)
                if is_important_match(norm):
                    add(norm)

    print(f"[INTL] Filtered important matches: {len(matches)}")
    return matches

# ====================== HELPERS ======================
def get_score(m):
    ft = m.get("score", {}).get("fullTime", {})
    hs = ft.get("home") or 0
    as_ = ft.get("away") or 0
    return m["homeTeam"].get("shortName", ""), m["awayTeam"].get("shortName", ""), int(hs), int(as_)

def flag(m):
    return "🌍"  # Simplified for internationals

def is_big_match(m):
    home = m["homeTeam"].get("shortName", "")
    away = m["awayTeam"].get("shortName", "")
    return home in BIG_TEAMS or away in BIG_TEAMS

def get_minute(m):
    try:
        ko = datetime.strptime(m.get("utcDate", ""), "%Y-%m-%dT%H:%M:%SZ")
        elapsed = (datetime.utcnow() - ko).total_seconds() / 60
        return int(max(1, elapsed))
    except:
        return "?"

# ====================== GOAL DETECTION ======================
def handle_goals(m):
    mid = m["id"]
    home, away, hs, as_ = get_score(m)
    for g in m.get("goals", []):
        if not isinstance(g, dict):
            continue
        minute = g.get("minute") or g.get("time", "?")
        scorer = g.get("player", {}).get("name") or "Unknown"
        key = f"{mid}_{minute}_{scorer}"

        if key not in posted_goals:
            posted_goals.add(key)
            save_state()

            msg = (f"⚽ GOAL! {scorer} at {minute}'\n\n"
                   f"{home} {hs}–{as_} {away}\n\n"
                   f"What a strike! 🔥\n\n"
                   f"Follow {PAGE_NAME} for live updates 🔔")
            post_to_facebook(msg)

# ====================== LIVE UPDATES (Big Teams Only) ======================
def handle_live_update(m):
    if not is_big_match(m):
        return

    mid = m["id"]
    now = time.time()
    if now - match_last_update.get(mid, 0) < LIVE_UPDATE_INTERVAL:
        return

    home, away, hs, as_ = get_score(m)
    minute = get_minute(m)
    match_last_update[mid] = now
    save_state()

    msg = f"📍 {minute}' | {home} {hs}–{as_} {away}\n\n🔥 Big match is live! Who scores next? 👇\n\nFollow {PAGE_NAME} 🔔"
    post_to_facebook(msg)

# ====================== PROCESS MATCH ======================
def process(m):
    status = m.get("status", "")

    if status == "IN_PLAY":
        key = f"{m['id']}_kickoff"
        if key not in posted_kickoffs:
            posted_kickoffs.add(key)
            save_state()
            post_to_facebook(f"🟢 KICK OFF | {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}\n\nThe match is underway! 🔥")

        handle_goals(m)
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

# ====================== DAILY PREVIEW ======================
def post_daily_preview(matches):
    big_matches = [m for m in matches if is_big_match(m)]
    if not big_matches:
        return

    lines = [f"🔥 TODAY'S BIG INTERNATIONAL MATCHES ({datetime.utcnow().strftime('%d %b %Y')})\n"]
    for m in big_matches:
        lines.append(f"⚔️ {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}")

    lines.append("\nWhich match are you watching? Drop your pick 👇")
    lines.append(f"\nFollow {PAGE_NAME} for live goal updates 🔔")
    post_to_facebook("\n".join(lines))

# ====================== MAIN LOOP ======================
def run():
    print(f"{PAGE_NAME} Bot v2.6 – Fixed & Optimized")
    preview_posted = False

    while True:
        try:
            matches = fetch_intl_today()

            if not preview_posted and matches:
                post_daily_preview(matches)
                preview_posted = True

            for m in matches[:12]:
                process(m)

            print(f"[DEBUG] Currently tracking {len(matches)} important matches")

        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(60)

if __name__ == "__main__":
    run()