import os, json, time, random, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Railway Environment Variables - Do NOT hardcode them
FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY     = os.getenv("FOOTBALL_KEY")
APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")
LIVESCORE_KEY    = os.getenv("LIVESCORE_KEY")
LIVESCORE_SECRET = os.getenv("LIVESCORE_SECRET")
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY")

FB_POST_URL      = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
STATE_FILE       = "match_state.json"
PAGE_NAME        = "ScoreLine Live"

LIVE_UPDATE_INTERVAL = 300  # 5 minutes - good balance for instant feeling

# ── Leagues & Config ─────────────────────────────────────────────
LEAGUES = {
    "PL":"Premier League", "PD":"La Liga", "SA":"Serie A", "BL1":"Bundesliga",
    "FL1":"Ligue 1", "CL":"Champions League"
}

LEAGUE_FLAGS = {
    "PL":"🏴󠁧󠁢󠁥󠁮󠁧󠁿", "PD":"🇪🇸", "SA":"🇮🇹", "BL1":"🇩🇪", "FL1":"🇫🇷", 
    "CL":"🏆", "INTL":"🌍"
}

LEAGUE_HASHTAGS = {
    "PL":"#PremierLeague #EPL", "PD":"#LaLiga", "SA":"#SerieA", 
    "BL1":"#Bundesliga", "FL1":"#Ligue1", "CL":"#ChampionsLeague",
    "INTL":"#InternationalFootball #WorldCup2026"
}

TOP_NATIONS = {"England","Spain","Germany","France","Brazil","Argentina","Portugal",
               "Italy","Netherlands","Belgium","Uruguay","Switzerland","Norway","Serbia"}

# ── State ────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                return (
                    set(d.get("goals",[])), set(d.get("cards",[])), 
                    set(d.get("halftimes",[])), set(d.get("fulltimes",[])),
                    set(d.get("kickoffs",[])), d.get("match_last_update", {})
                )
        except:
            pass
    return set(), set(), set(), set(), set(), {}

posted_goals, posted_cards, posted_halftimes, posted_ft, posted_kickoffs, match_last_update = load_state()

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({
            "goals": list(posted_goals),
            "cards": list(posted_cards),
            "halftimes": list(posted_halftimes),
            "fulltimes": list(posted_ft),
            "kickoffs": list(posted_kickoffs),
            "match_last_update": match_last_update
        }, f)

# ── API Functions ────────────────────────────────────────────────
def livescore_get(path):
    if not LIVESCORE_KEY or not LIVESCORE_SECRET: return None
    try:
        sep = "&" if "?" in path else "?"
        r = requests.get(f"https://livescore-api.com/api-client{path}{sep}key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return d.get("data", d) if d.get("success") else None
    except Exception as e:
        print(f"[LIVESCORE ERROR] {e}")
    return None

def apifootball_get(path):
    if not APIFOOTBALL_KEY: return None
    try:
        r = requests.get(f"https://v3.football.api-sports.io{path}",
                         headers={"x-rapidapi-host":"v3.football.api-sports.io", "x-rapidapi-key": APIFOOTBALL_KEY}, timeout=10)
        d = r.json()
        return d if not d.get("errors") else None
    except:
        return None

def post_to_facebook(msg):
    try:
        r = requests.post(FB_POST_URL, data={"message": msg, "access_token": FB_TOKEN}, timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {msg[:70]}...")
            return True
        print(f"[FB ERROR] {r.status_code}")
    except Exception as e:
        print(f"[FB ERROR] {e}")
    return False

# ── Safe livescore normalizer (Fixed crash) ──────────────────────
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

    raw_status = str(m.get("status") or "NOT STARTED").upper()
    status = {"IN PLAY":"IN_PLAY", "HALF TIME":"PAUSED", "FULL TIME":"FINISHED", "LIVE":"IN_PLAY"}.get(raw_status, "SCHEDULED")

    return {
        "id": f"ls_{m.get('id','')}",
        "utcDate": f"{m.get('date','')}T{m.get('time','00:00')}:00Z",
        "status": status,
        "_comp_name": m.get("competition", "International Friendly"),
        "_league_code": "INTL",
        "homeTeam": {"shortName": home},
        "awayTeam": {"shortName": away},
        "score": {"fullTime": {"home": hs, "away": as_}},
        "goals": [], "bookings": []
    }

# ── Fetch Big Internationals ─────────────────────────────────────
def fetch_intl_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INTL] Fetching today's internationals ({today})...")

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
                add(norm_ls(item))

    # API-Football + Priority Search for big nations
    if APIFOOTBALL_KEY:
        data = apifootball_get(f"/fixtures?date={today}")
        if data:
            for fx in data.get("response", []):
                lg_name = fx.get("league", {}).get("name", "").lower()
                if any(club in lg_name for club in ["premier","la liga","serie a","bundesliga","ligue 1"]):
                    continue
                home = fx.get("teams", {}).get("home", {}).get("name", "")
                away = fx.get("teams", {}).get("away", {}).get("name", "")
                if home and away:
                    add({
                        "id": f"apif_{fx.get('fixture',{}).get('id')}",
                        "utcDate": fx.get("fixture", {}).get("date", ""),
                        "status": fx.get("fixture", {}).get("status", {}).get("short", "SCHEDULED"),
                        "_comp_name": fx.get("league", {}).get("name", "International Friendly"),
                        "_league_code": "INTL",
                        "homeTeam": {"shortName": home},
                        "awayTeam": {"shortName": away},
                        "score": {"fullTime": {"home": None, "away": None}},
                        "goals": [], "bookings": []
                    })

    print(f"[INTL] Total matches fetched: {len(matches)}")
    return matches

# ── Helpers ──────────────────────────────────────────────────────
def get_score(m):
    ft = m.get("score", {}).get("fullTime", {})
    hs = ft.get("home") or 0
    as_ = ft.get("away") or 0
    return m["homeTeam"].get("shortName", "Home"), m["awayTeam"].get("shortName", "Away"), int(hs), int(as_)

def flag(m): return LEAGUE_FLAGS.get(m.get("_league_code"), "🌍")
def hashtags(m): return LEAGUE_HASHTAGS.get(m.get("_league_code"), "#Football")
def comp(m): return m.get("_comp_name", "International")

def get_minute(m):
    try:
        ko = datetime.strptime(m["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
        elapsed = (datetime.utcnow() - ko).total_seconds() / 60
        return int(max(1, elapsed))
    except:
        return "?"

# ── Live Score Update (every 5 min) ──────────────────────────────
def handle_live_update(m):
    mid = m["id"]
    now = time.time()
    if now - match_last_update.get(mid, 0) < LIVE_UPDATE_INTERVAL:
        return

    home, away, hs, as_ = get_score(m)
    minute = get_minute(m)
    match_last_update[mid] = now
    save_state()

    msg = f"📍 {minute}' | {home} {hs}–{as_} {away}\n\n🔥 Match is live! Who scores next? 👇\n\n{flag(m)} {comp(m)} | {hashtags(m)} #LiveUpdate\n\nFollow {PAGE_NAME} 🔔"
    post_to_facebook(msg)

# ── Process Match ────────────────────────────────────────────────
def process(m):
    status = m.get("status", "")
    if status == "IN_PLAY":
        # Kickoff (only once)
        key = f"{m['id']}_kickoff"
        if key not in posted_kickoffs:
            posted_kickoffs.add(key)
            save_state()
            post_to_facebook(f"🟢 KICK OFF | {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}\n\nThe match is underway! 🔥\n\n{flag(m)} {comp(m)}")

        handle_live_update(m)   # Every 5 minutes

    elif status == "PAUSED":
        key = f"{m['id']}_halftime"
        if key not in posted_halftimes:
            posted_halftimes.add(key)
            save_state()
            home, away, hs, as_ = get_score(m)
            post_to_facebook(f"⏸️ HALF TIME | {home} {hs}–{as_} {away}\n\nWhat are your thoughts? 👇")

    elif status == "FINISHED":
        key = f"{m['id']}_fulltime"
        if key not in posted_ft:
            posted_ft.add(key)
            save_state()
            home, away, hs, as_ = get_score(m)
            post_to_facebook(f"🏁 FULL TIME | {home} {hs}–{as_} {away}\n\nGreat match! Rate it 👇")

# ── Main Loop ────────────────────────────────────────────────────
def run():
    print(f"{PAGE_NAME} Bot Started - Live updates every 5 minutes 🔥")
    while True:
        try:
            intl_matches = fetch_intl_today()
            for m in intl_matches[:12]:        # Top 12 matches
                process(m)
        except Exception as e:
            print(f"[ERROR] {e}")
        
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Cycle completed. Waiting 60s...")
        time.sleep(60)

if __name__ == "__main__":
    run()