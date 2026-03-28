import os, json, time, random, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY     = os.getenv("FOOTBALL_KEY")
APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")
LIVESCORE_KEY    = os.getenv("LIVESCORE_KEY")
LIVESCORE_SECRET = os.getenv("LIVESCORE_SECRET")
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY")

FOOTBALL_BASE    = "https://api.football-data.org/v4"
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
LIVESCORE_BASE   = "https://livescore-api.com/api-client"
RAPIDFREE_BASE   = "https://free-api-live-football-data.p.rapidapi.com"
FB_POST_URL      = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
STATE_FILE       = "match_state.json"
PAGE_NAME        = "ScoreLine Live"

# ── Club leagues (football-data.org) ─────────────────────────────
LEAGUES = {
    "PL":"Premier League","PD":"La Liga","SA":"Serie A",
    "BL1":"Bundesliga","FL1":"Ligue 1","CL":"Champions League",
    "ELC":"Championship","DED":"Eredivisie","PPL":"Primeira Liga",
    "BSA":"Brasileirao","WC":"FIFA World Cup","EC":"European Championship",
}
LEAGUE_FLAGS = {
    "PL":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","PD":"🇪🇸","SA":"🇮🇹","BL1":"🇩🇪","FL1":"🇫🇷","CL":"🏆",
    "ELC":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","DED":"🇳🇱","PPL":"🇵🇹","BSA":"🇧🇷","WC":"🌍","EC":"🇪🇺","INTL":"🌍",
}
LEAGUE_HASHTAGS = {
    "PL":"#PremierLeague #EPL","PD":"#LaLiga #SpanishFootball",
    "SA":"#SerieA #ItalianFootball","BL1":"#Bundesliga #GermanFootball",
    "FL1":"#Ligue1 #FrenchFootball","CL":"#ChampionsLeague #UCL",
    "ELC":"#Championship #EFL","DED":"#Eredivisie #DutchFootball",
    "PPL":"#PrimeiraLiga #PortugueseFootball","BSA":"#Brasileirao #BrazilianFootball",
    "WC":"#WorldCup #FIFA","EC":"#EURO #EuropeanChampionship",
    "INTL":"#InternationalFootball #WorldCup2026",
}

# ── Nation importance for ranking ────────────────────────────────
TOP_NATIONS = {
    # Tier 1
    "Brazil","France","England","Spain","Germany","Argentina",
    "Portugal","Italy","Netherlands","Belgium",
    # Tier 2
    "Uruguay","Colombia","Mexico","USA","Japan","South Korea",
    "Morocco","Senegal","Egypt","Nigeria","Ghana","Ivory Coast",
    "Switzerland","Denmark","Croatia","Austria","Serbia","Poland",
    "Turkey","Greece","Sweden","Norway","Saudi Arabia","Iran",
    "Australia","Algeria","South Africa","Kenya","Cameroon",
    # Tier 3
    "Ecuador","Peru","Chile","Paraguay","Venezuela","Scotland",
    "Wales","Ireland","Czech Republic","Tunisia","Indonesia","Jordan",
    "Azerbaijan","Montenegro","Finland","Slovakia","Ukraine",
    "Panama","Costa Rica","Honduras","El Salvador","Guatemala",
}

# ── Continent maps ────────────────────────────────────────────────
EUROPE = {
    "England","Spain","Germany","France","Italy","Portugal","Netherlands",
    "Belgium","Switzerland","Denmark","Croatia","Austria","Serbia","Poland",
    "Turkey","Greece","Sweden","Norway","Scotland","Wales","Ireland",
    "Czech Republic","Finland","Slovakia","Ukraine","Russia","Montenegro",
    "Azerbaijan","Romania","Hungary","Bosnia","Albania","Kosovo","Georgia",
    "Bulgaria","North Macedonia","Estonia","Latvia","Lithuania","Andorra",
    "Iceland","Moldova","Cyprus","Malta","Luxembourg","Football Union of Russia",
}
AFRICA = {
    "Morocco","Senegal","Egypt","Nigeria","Ghana","Ivory Coast","Algeria",
    "Tunisia","Cameroon","South Africa","Kenya","Mali","Burkina Faso",
    "Guinea","Zimbabwe","Uganda","Tanzania","Zambia","Angola","Rwanda",
    "Congo","DR Congo","Libya","Sudan","Mauritania","Benin","Togo",
    "Gabon","Cape Verde","Madagascar","Malawi","Botswana","Namibia",
    "Sierra Leone","Liberia","Mozambique","Ethiopia","Comoros",
}
AMERICAS = {
    "Brazil","Argentina","Uruguay","Colombia","Chile","Peru","Ecuador",
    "Paraguay","Venezuela","Bolivia","Mexico","USA","Canada","Costa Rica",
    "Panama","Honduras","El Salvador","Guatemala","Jamaica",
    "Trinidad and Tobago","Haiti","Cuba","Nicaragua","Curacao",
    "St. Kitts and Nevis","St Lucia","Suriname","Guyana","Bermuda",
    "Dominican Republic","Puerto Rico","Barbados","Belize","Martinique",
}
ASIA = {
    "Japan","South Korea","Iran","Saudi Arabia","Australia","Indonesia",
    "China","Vietnam","Thailand","Malaysia","Philippines","India","UAE",
    "Qatar","Bahrain","Kuwait","Oman","Iraq","Syria","Jordan","Lebanon",
    "Uzbekistan","Kazakhstan","Kyrgyzstan","Nepal","Sri Lanka","Pakistan",
    "Myanmar","Cambodia","Singapore","Hong Kong","Yemen","Palestine",
    "North Korea","Bangladesh","Tajikistan","Turkmenistan",
}
CONTINENT_FLAGS = {
    "Europe":"🇪🇺","Africa":"🌍","Americas":"🌎","Asia":"🌏","Other":"🌐",
}

def get_continent(name):
    if name in EUROPE:   return "Europe"
    if name in AFRICA:   return "Africa"
    if name in AMERICAS: return "Americas"
    if name in ASIA:     return "Asia"
    return "Other"

# ── Fan questions ─────────────────────────────────────────────────
GOAL_Q     = ["Who saw that coming? 😱","What a strike! Did you see it live? 👀",
               "The crowd is going wild! 🔥","Class finish! Drop a ⚽ if you saw it!",
               "Game changer! Who wins from here? 👇"]
HT_Q       = ["Who has impressed you most so far? 👇",
               "What changes do you expect in the second half? 🤔",
               "Still anyone's game! Your prediction? 👇",
               "Which team has been better so far? 👇"]
FT_Q       = ["Who was your Man of the Match? 🏆 Drop your pick 👇",
               "What's your reaction? 👇","Did you predict this result? 🤔",
               "Fair result or did one team deserve more? 👇",
               "Rate this match out of 10 👇"]
LINEUP_Q   = ["Who's winning the midfield battle today? ⚔️",
               "Any surprise selections? 👀","Is your favourite player starting? 👇",
               "Which lineup looks stronger? 👇"]
PREVIEW_Q  = ["Which game are you watching today? 👀",
               "Who's your pick for biggest match today? 👇",
               "Big day of football! Who wins today? 🏆"]
REDCARD_Q  = ["How will this change the game? 🤔","Harsh or deserved? 👇",
               "Can the 10-man side hold on? 💪","Did the ref make the right call? 👇"]
KICKOFF_L  = ["The whistle has blown! We are UNDERWAY! 🔥",
               "LET'S GO! Kick off has been taken! ⚽",
               "IT'S STARTED! Who scores first? 👇",
               "We are LIVE! 90 minutes of football ahead! 🔥"]

# ── Filler ────────────────────────────────────────────────────────
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
                return (set(d.get("goals",[])), set(d.get("var_cancelled",[])),
                        set(d.get("cards",[])), set(d.get("lineups",[])),
                        set(d.get("halftimes",[])), set(d.get("fulltimes",[])),
                        set(d.get("matchdays",[])), set(d.get("kickoffs",[])),
                        set(d.get("filler_posted",[])))
        except Exception:
            pass
    return set(),set(),set(),set(),set(),set(),set(),set(),set()

(posted_goals, posted_var, posted_cards, posted_lineups,
 posted_halftimes, posted_ft, posted_matchdays,
 posted_kickoffs, posted_filler) = load_state()

last_filler_time = 0

def save_state():
    with open(STATE_FILE,"w") as f:
        json.dump({
            "goals":list(posted_goals),"var_cancelled":list(posted_var),
            "cards":list(posted_cards),"lineups":list(posted_lineups),
            "halftimes":list(posted_halftimes),"fulltimes":list(posted_ft),
            "matchdays":list(posted_matchdays),"kickoffs":list(posted_kickoffs),
            "filler_posted":list(posted_filler),
        }, f)

# ── API-Football budget ───────────────────────────────────────────
apif_used = 0
apif_date = None

def apif_ok():
    global apif_used, apif_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if apif_date != today:
        apif_used = 0
        apif_date = today
    return apif_used < 90

# ── Intl cache ────────────────────────────────────────────────────
_intl_matches    = []
_intl_date       = None
_intl_last_live  = 0
LIVE_INTERVAL    = 60

# ── API calls ─────────────────────────────────────────────────────
def football_get(path):
    try:
        r = requests.get(f"{FOOTBALL_BASE}{path}",
                         headers={"X-Auth-Token": FOOTBALL_KEY}, timeout=10)
        if r.status_code == 200: return r.json()
        if r.status_code == 429:
            print("[WARN] football-data.org rate limit"); time.sleep(60)
    except Exception as e:
        print(f"[ERROR] football-data.org: {e}")
    return None

def livescore_get(path):
    if not LIVESCORE_KEY or not LIVESCORE_SECRET: return None
    try:
        sep = "&" if "?" in path else "?"
        r   = requests.get(f"{LIVESCORE_BASE}{path}{sep}key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            if d.get("success"): return d.get("data", d)
            print(f"[LIVESCORE] {d.get('error','unknown error')}")
        else:
            print(f"[LIVESCORE] HTTP {r.status_code}")
    except Exception as e:
        print(f"[ERROR] livescore-api: {e}")
    return None

def rapidfree_get(path):
    if not RAPIDAPI_KEY: return None
    try:
        r = requests.get(f"{RAPIDFREE_BASE}{path}",
                         headers={"x-rapidapi-host":"free-api-live-football-data.p.rapidapi.com",
                                  "x-rapidapi-key": RAPIDAPI_KEY}, timeout=10)
        if r.status_code == 200: return r.json()
        print(f"[RAPIDFREE] HTTP {r.status_code}")
    except Exception as e:
        print(f"[ERROR] RapidFree: {e}")
    return None

def apifootball_get(path):
    global apif_used
    if not APIFOOTBALL_KEY or not apif_ok():
        print(f"[INTL] API-Football budget reached ({apif_used}/90)"); return None
    try:
        r = requests.get(f"{APIFOOTBALL_BASE}{path}",
                         headers={"x-rapidapi-host":"v3.football.api-sports.io",
                                  "x-rapidapi-key": APIFOOTBALL_KEY}, timeout=10)
        apif_used += 1
        if r.status_code == 200:
            d = r.json()
            if d.get("errors"): print(f"[INTL] API-Football: {d['errors']}"); return None
            print(f"[INTL] API-Football: {apif_used}/90 used")
            return d
        print(f"[INTL] API-Football HTTP {r.status_code}")
    except Exception as e:
        print(f"[ERROR] API-Football: {e}")
    return None

def post_to_facebook(msg):
    try:
        r = requests.post(FB_POST_URL, data={"message":msg,"access_token":FB_TOKEN}, timeout=10)
        if r.status_code == 200:
            print(f"[POSTED] {msg[:70]}...")
            return True
        print(f"[ERROR] FB {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"[ERROR] FB: {e}")
    return False

# ── Match importance score ────────────────────────────────────────
def nation_score(name):
    """Partial match so 'Spain U21', 'ESP', 'Spain' all hit TOP_NATIONS."""
    if not name: return 0
    nl = name.lower()
    for n in TOP_NATIONS:
        if n.lower() in nl or nl in n.lower():
            return 10
    return 0

def importance(match):
    score = 0
    home  = match.get("homeTeam", {}).get("shortName", "")
    away  = match.get("awayTeam", {}).get("shortName", "")
    score += nation_score(home)
    score += nation_score(away)
    _cn = match.get("_comp_name","")
    comp = (_cn if isinstance(_cn, str) else "").lower()
    if any(k in comp for k in ["world cup","qualifier","playoff"]): score += 15
    if any(k in comp for k in ["nations league"]):                  score += 12
    if any(k in comp for k in ["afcon","copa america","gold cup","asian cup","euro"]): score += 12
    if "friendly" in comp or "amical" in comp or "amistoso" in comp: score += 5
    code = match.get("_league_code","")
    if code in ("PL","PD","SA","BL1","FL1","CL"): score += 8
    return score

def top_matches(all_matches, n=10):
    flat = []
    for code, matches in all_matches.items():
        for m in matches:
            if "_league_code" not in m: m["_league_code"] = code
            flat.append(m)
    flat.sort(key=importance, reverse=True)
    return flat[:n]

# ── Helpers ───────────────────────────────────────────────────────
def get_score(m):
    ft  = m["score"]["fullTime"]
    ht  = m["score"]["halfTime"]
    # Count goals from goals list if score fields are missing
    goals_list = m.get("goals", [])
    home_name  = m["homeTeam"]["shortName"]
    away_name  = m["awayTeam"]["shortName"]
    def _int(v):
        try: return int(v)
        except: return None
    hs  = _int(ft.get("home")) if _int(ft.get("home")) is not None else _int(ht.get("home"))
    as_ = _int(ft.get("away")) if _int(ft.get("away")) is not None else _int(ht.get("away"))
    # Last resort: count goals from goals list
    if hs is None and goals_list:
        hs  = sum(1 for g in goals_list if g.get("team",{}).get("shortName","") == home_name)
        as_ = sum(1 for g in goals_list if g.get("team",{}).get("shortName","") == away_name)
    hs  = hs  if hs  is not None else 0
    as_ = as_ if as_ is not None else 0
    return home_name, away_name, hs, as_

def flag(m):
    code = m.get("_league_code","INTL")
    if code == "INTL":
        return CONTINENT_FLAGS.get(get_continent(m["homeTeam"]["shortName"]),"🌍")
    return LEAGUE_FLAGS.get(code,"🌍")

def hashtags(m):
    code = m.get("_league_code","INTL")
    base = LEAGUE_HASHTAGS.get(code,"#InternationalFootball #WorldCup2026")
    ht   = "#" + m["homeTeam"]["shortName"].replace(" ","")
    at   = "#" + m["awayTeam"]["shortName"].replace(" ","")
    return f"{base} {ht} {at}"

def comp(m):
    code = m.get("_league_code","INTL")
    cn = m.get("_comp_name", LEAGUES.get(code,"International"))
    if isinstance(cn, dict):
        cn = cn.get("name", cn.get("long_name", "International"))
    return cn or "International"

# ── Normalize livescore-api match ─────────────────────────────────
def norm_ls(m, default_comp="International"):
    STATUS = {
        "IN PLAY":"IN_PLAY","HALF TIME":"PAUSED","FULL TIME":"FINISHED",
        "FINISHED":"FINISHED","NOT STARTED":"SCHEDULED","POSTPONED":"POSTPONED",
        "CANCELLED":"CANCELLED","ABANDONED":"CANCELLED","EXTRA TIME":"IN_PLAY",
        "PENALTY":"IN_PLAY","LIVE":"IN_PLAY",
    }
    raw    = (m.get("status") or m.get("time") or "NOT STARTED").upper().strip()
    status = STATUS.get(raw, "SCHEDULED")
    home   = m.get("home_name", m.get("home",{}).get("name",""))
    away   = m.get("away_name", m.get("away",{}).get("name",""))

    # Score — livescore-api uses multiple field names
    hs = as_ = ht_h = ht_a = None
    def _int(v):
        try: return int(v)
        except: return None
    # Try score field "1:2" or "1 : 2"
    try:
        sc_raw = m.get("score") or ""
        if isinstance(sc_raw, str):
            p = sc_raw.replace(" ","").split(":")
            if len(p)==2 and p[0].isdigit(): hs,as_ = int(p[0]),int(p[1])
    except Exception: pass
    # Try home_score / away_score direct fields
    if hs is None:
        hs  = _int(m.get("home_score", m.get("score_home")))
        as_ = _int(m.get("away_score", m.get("score_away")))
    # Halftime
    try:
        p = (m.get("ht_score") or "").replace(" ","").split(":")
        if len(p)==2 and p[0].isdigit(): ht_h,ht_a = int(p[0]),int(p[1])
    except Exception: pass
    if ht_h is None:
        ht_h = _int(m.get("ht_home_score", m.get("halftime_score_home")))
        ht_a = _int(m.get("ht_away_score", m.get("halftime_score_away")))

    # Events
    goals, bookings = [], []
    for ev in (m.get("events") or []):
        etype  = (ev.get("type") or "").lower()
        player = ev.get("player","Unknown")
        minute = ev.get("minute","?")
        team   = ev.get("team","")
        assist = ev.get("assist","")
        if etype in ("goal","penalty goal","penalty"):
            sfx = " (pen)" if "penalty" in etype else ""
            goals.append({"minute":minute,"scorer":{"name":f"{player}{sfx}"},
                          "assist":{"name":assist} if assist else {},"team":{"shortName":team}})
        elif etype == "own goal":
            goals.append({"minute":minute,"scorer":{"name":f"{player} (OG)"},
                          "assist":{},"team":{"shortName":team}})
        elif etype in ("red card","red-card"):
            bookings.append({"minute":minute,"card":"RED_CARD",
                             "player":{"name":player},"team":{"shortName":team}})

    # Lineups
    lineups = []
    hl = m.get("lineup",{}).get("home",[])
    al = m.get("lineup",{}).get("away",[])
    if hl: lineups.append({"startXI":[{"player":{"name":p}} for p in hl]})
    if al: lineups.append({"startXI":[{"player":{"name":p}} for p in al]})

    date_str = m.get("date","")
    time_str = m.get("time","00:00")
    utc_date = f"{date_str}T{time_str}:00Z" if date_str else ""

    return {
        "id":f"ls_{m.get('id','')}","utcDate":utc_date,"status":status,
        "_comp_name":(lambda c: c.get("name", c.get("long_name", default_comp)) if isinstance(c, dict) else (c or default_comp))(m.get("competition", default_comp)),
        "_comp_flag":"🌍","_league_code":"INTL",
        "homeTeam":{"id":str(m.get("home_id","")),"name":home,"shortName":home},
        "awayTeam":{"id":str(m.get("away_id","")),"name":away,"shortName":away},
        "score":{"halfTime":{"home":ht_h,"away":ht_a},"fullTime":{"home":hs,"away":as_}},
        "goals":goals,"bookings":bookings,"lineups":lineups,
    }

# ── Fetch today's internationals ──────────────────────────────────
# ── Priority nations always tracked ─────────────────────────────
PRIORITY_NATIONS = {
    "Brazil","France","England","Spain","Germany","Argentina",
    "Portugal","Italy","Netherlands","Belgium","Morocco","Norway",
    "Uruguay","Colombia","Mexico","USA","Japan","South Korea",
    "Senegal","Egypt","Nigeria","Ghana","Ivory Coast","Switzerland",
    "Denmark","Croatia","Austria","Serbia","Poland","Turkey",
    "Sweden","Scotland","Wales","Ireland","Ukraine","Algeria",
    "Saudi Arabia","Iran","Australia","Czech Republic","Tunisia",
}

def make_intl_match(home, away, comp="International Friendly",
                    status="SCHEDULED", utc_date="", uid=None):
    mid = uid or f"manual_{home}_{away}".replace(" ","_")
    return {
        "id": mid, "utcDate": utc_date, "status": status,
        "_comp_name": comp, "_comp_flag": "🌍", "_league_code": "INTL",
        "homeTeam": {"id":"","name":home,"shortName":home},
        "awayTeam": {"id":"","name":away,"shortName":away},
        "score": {"halfTime":{"home":None,"away":None},
                  "fullTime":{"home":None,"away":None}},
        "goals":[], "bookings":[], "lineups":[],
    }

# ── Junk match filter ────────────────────────────────────────────
# Keywords that identify non-international / low-tier matches to skip
JUNK_TEAMS = {
    # Australian state/amateur leagues
    "sharks","manly united","olympic kingsway","perth glory ii","stirling",
    "perth sc","western knight","perth redstar","sorrento","balcatta",
    "fremantle city","armadale","sunshine","st. albans","holland park",
    "altona magic","green gully","moreton city","eastern suburbs",
    "st george","capalaba","redlands","logan lightning","brisbane strikers",
    "north star","north west sydney","willawong",
    # Reserve / B / II teams
    " ii"," b "," b$","reserve","youth","u18","u20","u21","u23",
    "dinamo moscow ii","alania","fc yenisey","fc ufa",
    # Czech/Slovak lower leagues
    "hlucin","frydek","zbrojovka brno ii","slovacko b","velke hamry",
    "loko vltavin","hostoun","motorlet","petrin","taborsko",
    "tatran liptovsky","pribram ii","plzen ii",
    # Ukrainian lower
    "tarasivka","metalurh zaporizhya","metal kharkiv","viktoriya sumy",
}

JUNK_COMPS = {
    "victorian","npl","state league","npls","amateur","reserve",
    "youth","u18","u20","u21","u23","friendly cup","regional",
    "czech republic division","czech ii","slovak ii","fnl",
    "russian fnl","russian second","czech second","australian",
    "national premier","fdl","wpl","w-league",
}

def is_junk(m):
    """Return True if this match should be filtered out."""
    home = m.get("homeTeam",{}).get("shortName","").lower()
    away = m.get("awayTeam",{}).get("shortName","").lower()
    comp_raw = m.get("_comp_name","")
    if isinstance(comp_raw, dict):
        comp_name = comp_raw.get("name","").lower()
    else:
        comp_name = str(comp_raw).lower()

    # Filter junk competitions
    for jc in JUNK_COMPS:
        if jc in comp_name:
            return True

    # Filter if team name contains junk keywords
    for jt in JUNK_TEAMS:
        if jt in home or jt in away:
            return True

    # Filter reserve/B teams by name pattern
    for pat in [" ii", " b team", " reserves", " u21", " u23", " u20"]:
        if home.endswith(pat) or away.endswith(pat):
            return True

    # Only allow matches where AT LEAST ONE team is a known nation
    # OR the competition is clearly international
    home_known = any(n.lower() in home or home in n.lower() for n in PRIORITY_NATIONS)
    away_known = any(n.lower() in away or away in n.lower() for n in PRIORITY_NATIONS)
    intl_comp  = any(k in comp_name for k in [
        "world cup","qualifier","friendly","nations league","international",
        "afcon","gold cup","copa america","euro","qualification","olympic",
        "concacaf","conmebol","afc","caf","uefa","fifa","k league",
        "j league","j1","j2","mls","premier league","la liga","serie a",
        "bundesliga","ligue 1","champions league","europa league",
    ])

    if not home_known and not away_known and not intl_comp:
        return True

    return False

def fetch_intl_today():
    global _intl_matches, _intl_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if _intl_date == today and _intl_matches:
        return _intl_matches

    print(f"[INTL] Fetching today's international fixtures ({today})...")
    matches = []
    seen_ids = set()

    def add(m):
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
            matches.append(m)

    # 1. livescore-api.com — fetch ONLY national team / international competitions
    if LIVESCORE_KEY and LIVESCORE_SECRET:
        # Strategy: fetch fixtures filtered to national_teams competitions only
        # Try multiple federation endpoints to get all confederations
        FEDERATION_IDS = [1, 2, 3, 4, 5, 6, 7]  # FIFA,UEFA,CONMEBOL,CAF,AFC,CONCACAF,OFC
        ls_raw = []

        # First try: fixtures with national_teams_only filter
        for fed_id in FEDERATION_IDS:
            d = livescore_get(f"/fixtures/matches.json?date={today}&federation_id={fed_id}")
            if d:
                items = d if isinstance(d, list) else d.get("match", d.get("fixtures", []))
                ls_raw.extend(items if isinstance(items, list) else [])

        # If federation filter gave nothing, fall back to all fixtures but filter aggressively
        if not ls_raw:
            d = livescore_get(f"/fixtures/matches.json?date={today}")
            if d:
                ls_raw = d if isinstance(d, list) else d.get("match", d.get("fixtures", []))

        # Also fetch live matches
        dl = livescore_get("/matches/live.json")
        if dl:
            live_items = dl if isinstance(dl, list) else dl.get("match", dl.get("fixtures", []))
            ls_raw.extend(live_items if isinstance(live_items, list) else [])

        raw_count = 0
        ls_kept = []
        ls_rejected = []
        for m in ls_raw:
            n = norm_ls(m)
            if n["homeTeam"]["shortName"] and n["awayTeam"]["shortName"]:
                raw_count += 1
                if not is_junk(n):
                    add(n)
                    ls_kept.append(f"{n['homeTeam']['shortName']} vs {n['awayTeam']['shortName']} [{n.get('_comp_name','?')}]")
                else:
                    ls_rejected.append(f"{n['homeTeam']['shortName']} vs {n['awayTeam']['shortName']}")
        print(f"[DEBUG-LS] livescore-api returned {raw_count} matches, kept {len(ls_kept)}, rejected {len(ls_rejected)}")
        for x in ls_kept:
            print(f"  [LS-KEPT] {x}")
        if ls_rejected:
            print(f"  [LS-REJECTED] {len(ls_rejected)} junk matches filtered out")

    # 2. RapidAPI free live football
    if RAPIDAPI_KEY:
        data = rapidfree_get("/football-current-live")
        if data:
            items = data.get("response", data.get("matches",[]))
            for m in items:
                home = (m.get("home") or {}).get("name","")
                away = (m.get("away") or {}).get("name","")
                if not home or not away: continue
                sc   = m.get("score",{})
                matches.append({
                    "id":f"rf_{m.get('id','')}","utcDate":today+"T00:00:00Z",
                    "status":"IN_PLAY","_comp_name":m.get("competition",{}).get("name","International"),
                    "_comp_flag":"🌍","_league_code":"INTL",
                    "homeTeam":{"id":"","name":home,"shortName":home},
                    "awayTeam":{"id":"","name":away,"shortName":away},
                    "score":{"halfTime":{"home":None,"away":None},
                             "fullTime":{"home":sc.get("home"),"away":sc.get("away")}},
                    "goals":[],"bookings":[],"lineups":[],
                })
            rf_names = [f"{m.get('homeTeam',{}).get('shortName','?')} vs {m.get('awayTeam',{}).get('shortName','?')}" for m in matches if m['id'].startswith('rf_')]
            print(f"[DEBUG-RF] RapidFree returned {len(rf_names)} live matches:")
            for x in rf_names:
                print(f"  [RF] {x}")
            if not rf_names:
                print(f"  [RF] No live matches right now")

    # 3. API-Football — fetch ALL fixtures and filter internationals
    if APIFOOTBALL_KEY:
        CLUB = ["premier league","la liga","serie a","bundesliga","ligue 1","championship",
                "eredivisie","primeira liga","super lig","mls","brasileirao",
                "champions league","europa league","conference league","fa cup",
                "copa del rey","dfb-pokal","coppa italia","carabao"]
        INTL = ["world cup","qualifier","friendly","friendlies","nations league",
                "international","afcon","gold cup","concacaf","copa america",
                "afc","uefa","fifa","playoff","amical","amistoso","olympics",
                "qualification","euro","african","asian","conmebol","ofc"]
        INTL_C = {"world","europe","south america","north america","africa","asia","oceania"}
        SMAP   = {"NS":"SCHEDULED","TBD":"TIMED","1H":"IN_PLAY","2H":"IN_PLAY",
                  "ET":"IN_PLAY","P":"IN_PLAY","BT":"PAUSED","HT":"PAUSED",
                  "FT":"FINISHED","AET":"FINISHED","PEN":"FINISHED",
                  "AWD":"FINISHED","WO":"FINISHED","PST":"POSTPONED","CANC":"CANCELLED"}

        def parse_apif_fixture(fx):
            lg    = fx.get("league",{})
            ln    = lg.get("name","").lower()
            lt    = lg.get("type","").lower()
            country = lg.get("country","")
            lc    = (country.get("name","") if isinstance(country, dict) else country).lower()
            if any(k in ln for k in CLUB): return None
            if not (lt in ("cup","international","friendly") or
                    any(k in ln for k in INTL) or lc in INTL_C): return None
            fix   = fx.get("fixture",{})
            teams = fx.get("teams",{})
            goals = fx.get("goals",{})
            sc    = fx.get("score",{})
            hn    = teams.get("home",{}).get("name","")
            an    = teams.get("away",{}).get("name","")
            if not hn or not an: return None
            gs, bks = [], []
            for ev in fx.get("events",[]):
                et = ev.get("type","").lower()
                dt = ev.get("detail","").lower()
                pl = ev.get("player",{}).get("name","Unknown")
                mn = ev.get("time",{}).get("elapsed","?")
                at = (ev.get("assist") or {})
                tm = ev.get("team",{}).get("name","")
                if et == "goal" and "missed" not in dt:
                    sfx = " (pen)" if "penalty" in dt else " (OG)" if "own" in dt else ""
                    gs.append({"minute":mn,"scorer":{"name":f"{pl}{sfx}"},
                               "assist":{"name":at.get("name","")} if at.get("name") else {},
                               "team":{"shortName":tm}})
                elif et == "card" and "red" in dt:
                    bks.append({"minute":mn,"card":"RED_CARD",
                                "player":{"name":pl},"team":{"shortName":tm}})
            return {
                "id":f"apif_{fix.get('id','')}",
                "utcDate":fix.get("date",""),
                "status":SMAP.get(fix.get("status",{}).get("short",""),"SCHEDULED"),
                "_comp_name":lg.get("name","International"),
                "_comp_flag":"🌍","_league_code":"INTL",
                "homeTeam":{"id":str(teams.get("home",{}).get("id","")),"name":hn,"shortName":hn},
                "awayTeam":{"id":str(teams.get("away",{}).get("id","")),"name":an,"shortName":an},
                "score":{"halfTime":{"home":sc.get("halftime",{}).get("home"),
                                     "away":sc.get("halftime",{}).get("away")},
                         "fullTime":{"home":goals.get("home"),"away":goals.get("away")}},
                "goals":gs,"bookings":bks,"lineups":[],
                "_apif_fixture_id":fix.get("id",""),
            }

        # Fetch all today's fixtures
        data = apifootball_get(f"/fixtures?date={today}")
        apif_count = 0
        if data:
            for fx in data.get("response",[]):
                m = parse_apif_fixture(fx)
                if m:
                    add(m)
                    apif_count += 1
            apif_names = [f"{m.get('homeTeam',{}).get('shortName','?')} vs {m.get('awayTeam',{}).get('shortName','?')} [{m.get('_comp_name','?')}]" for m in matches if m['id'].startswith('apif_')]
            print(f"[DEBUG-APIF] API-Football returned {len(apif_names)} international matches:")
            for x in apif_names:
                print(f"  [APIF] {x}")
            if not apif_names:
                print(f"  [APIF] No international matches found or budget reached")

        # Also search specifically for each priority nation to make sure none are missed
        already_has = {
            n.lower()
            for mx in matches
            for n in [mx["homeTeam"]["shortName"], mx["awayTeam"]["shortName"]]
        }
        missing = [n for n in PRIORITY_NATIONS if n.lower() not in already_has]
        if missing:
            print(f"[INTL] Searching API-Football for {len(missing)} missing priority nations...")
            for nation in missing[:10]:  # max 10 extra calls to save budget
                nd = apifootball_get(f"/fixtures?date={today}&search={requests.utils.quote(nation)}")
                if nd:
                    for fx in nd.get("response",[]):
                        m = parse_apif_fixture(fx)
                        if m:
                            add(m)
                            print(f"[INTL] Found via search: {m['homeTeam']['shortName']} vs {m['awayTeam']['shortName']}")

    # ── Guaranteed seed list — updated each international window ────
    SEED = {
        "2026-03-27": [
            ("England","Uruguay","International Friendly","2026-03-27T19:45:00Z"),
            ("Spain","Serbia","International Friendly","2026-03-27T20:00:00Z"),
            ("Germany","Netherlands","International Friendly","2026-03-27T19:45:00Z"),
            ("Morocco","Cameroon","International Friendly","2026-03-27T19:00:00Z"),
            ("Norway","Turkey","International Friendly","2026-03-27T18:00:00Z"),
            ("Portugal","Colombia","International Friendly","2026-03-27T19:45:00Z"),
            ("France","Croatia","International Friendly","2026-03-27T20:45:00Z"),
            ("Brazil","Mexico","International Friendly","2026-03-27T00:30:00Z"),
            ("Argentina","Chile","International Friendly","2026-03-27T23:00:00Z"),
        ],
        "2026-03-28": [
            ("South Korea","Ivory Coast","International Friendly","2026-03-28T14:00:00Z"),
            ("Scotland","Japan","International Friendly","2026-03-28T17:00:00Z"),
            ("USA","Belgium","International Friendly","2026-03-28T19:30:00Z"),
            ("Senegal","Peru","International Friendly","2026-03-28T16:00:00Z"),
            ("Canada","Iceland","International Friendly","2026-03-28T17:00:00Z"),
            ("Hungary","Slovenia","International Friendly","2026-03-28T17:00:00Z"),
            ("Zambia","Malawi","International Friendly","2026-03-28T13:00:00Z"),
        ],
        "2026-03-31": [
            ("DR Congo","New Caledonia","FIFA World Cup Playoff","2026-03-31T21:00:00Z"),
            ("Iraq","Suriname","FIFA World Cup Playoff","2026-03-31T03:00:00Z"),
        ],
    }
    existing_pairs = {
        f"{m['homeTeam']['shortName'].lower()}_{m['awayTeam']['shortName'].lower()}"
        for m in matches
    }
    seeded_count = 0
    for home, away, comp_name, utc in SEED.get(today, []):
        pair = f"{home.lower()}_{away.lower()}"
        if pair not in existing_pairs:
            matches.append(make_intl_match(home, away, comp_name, "SCHEDULED", utc))
            existing_pairs.add(pair)
            seeded_count += 1
    if seeded_count:
        print(f"[INTL] Seeded {seeded_count} guaranteed matches for {today}")

    total = len(matches)
    print(f"[INTL] Total fixtures after merge: {total}")
    _intl_matches, _intl_date = matches, today
    return matches

def refresh_live():
    global _intl_matches, _intl_last_live
    if not _intl_matches: return
    now = time.time()
    if now - _intl_last_live < LIVE_INTERVAL: return
    _intl_last_live = now

    # livescore live endpoint
    if LIVESCORE_KEY and LIVESCORE_SECRET:
        data = livescore_get("/matches/live.json")
        if data:
            items    = data if isinstance(data,list) else data.get("match",[])
            live_map = {}
            for m in items:
                n   = norm_ls(m)
                key = f"{n['homeTeam']['shortName']}_{n['awayTeam']['shortName']}"
                live_map[key] = n
            _intl_matches = [live_map.get(f"{m['homeTeam']['shortName']}_{m['awayTeam']['shortName']}", m)
                             for m in _intl_matches]
            return

    # RapidFree fallback
    if RAPIDAPI_KEY:
        data = rapidfree_get("/football-current-live")
        if data:
            items    = data.get("response", data.get("matches",[]))
            live_map = {}
            for m in items:
                h = (m.get("home") or {}).get("name","")
                a = (m.get("away") or {}).get("name","")
                if h and a: live_map[f"{h}_{a}"] = m
            for match in _intl_matches:
                key  = f"{match['homeTeam']['shortName']}_{match['awayTeam']['shortName']}"
                live = live_map.get(key)
                if live:
                    sc = live.get("score",{})
                    match["status"] = "IN_PLAY"
                    match["score"]["fullTime"]["home"] = sc.get("home")
                    match["score"]["fullTime"]["away"] = sc.get("away")

# ── Daily preview — grouped by continent ─────────────────────────
def handle_preview(all_matches):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key   = f"matchday_{today}"
    if key in posted_matchdays or not all_matches: return

    by_cont = {"Europe":[],"Americas":[],"Africa":[],"Asia":[],"Other":[]}
    for code, matches in all_matches.items():
        for m in matches:
            if code == "INTL":
                cont = get_continent(m["homeTeam"]["shortName"])
            else:
                cont = "Europe"
            by_cont[cont].append((code, m))

    lines = [f"📅 TODAY'S MATCHES — {datetime.utcnow().strftime('%d %b %Y')}\n"]
    for cont in ["Europe","Americas","Africa","Asia","Other"]:
        items = by_cont[cont]
        if not items: continue
        cf = CONTINENT_FLAGS[cont]
        lines.append(f"{cf} {cont.upper()}")
        for code, m in sorted(items, key=lambda x: x[1].get("utcDate","")):
            home = m["homeTeam"]["shortName"]
            away = m["awayTeam"]["shortName"]
            try:
                ko   = datetime.strptime(m.get("utcDate",""), "%Y-%m-%dT%H:%M:%SZ")
                tstr = ko.strftime("%H:%M UTC")
            except Exception:
                tstr = "TBD"
            c = m.get("_comp_name", LEAGUES.get(code,""))
            lines.append(f"  ⚔️  {home} vs {away}  —  {tstr}")
        lines.append("")

    if len(lines) <= 2: return

    lines.append(random.choice(PREVIEW_Q))
    lines.append("")
    lines.append("#MatchDay #FootballToday #Football #ScoreLineLive #WorldCup2026")
    lines.append(f"\nFollow {PAGE_NAME} for live updates 🔔")

    posted_matchdays.add(key)
    save_state()
    post_to_facebook("\n".join(lines))

# ── Kickoff ───────────────────────────────────────────────────────
def handle_kickoff(m):
    key = f"{m['id']}_kickoff"
    if key in posted_kickoffs: return
    home = m["homeTeam"]["shortName"]
    away = m["awayTeam"]["shortName"]
    posted_kickoffs.add(key); save_state()
    post_to_facebook(
        f"🟢 KICK OFF | {home} vs {away}\n\n"
        f"{random.choice(KICKOFF_L)}\n\n"
        f"🏆 {comp(m)}\n\n"
        f"{hashtags(m)} #KickOff #LiveFootball\n\n"
        f"Follow {PAGE_NAME} for live updates 🔔"
    )

# ── Lineups ───────────────────────────────────────────────────────
def handle_lineups(m):
    key = f"{m['id']}_lineup"
    if key in posted_lineups: return
    home    = m["homeTeam"]["shortName"]
    away    = m["awayTeam"]["shortName"]
    lineups = m.get("lineups",[])
    if len(lineups) < 2: return

    def fmt(lu):
        players = lu.get("startXI",[])
        if not players: return "  Not yet confirmed"
        return "\n".join(f"  {i+1}. {p.get('player',{}).get('name','')}"
                         for i,p in enumerate(players))

    posted_lineups.add(key); save_state()
    post_to_facebook(
        f"📋 LINEUPS | {home} vs {away}\n\n"
        f"🔵 {home}:\n{fmt(lineups[0])}\n\n"
        f"🔴 {away}:\n{fmt(lineups[1])}\n\n"
        f"{random.choice(LINEUP_Q)}\n\n"
        f"{flag(m)} {comp(m)} | {hashtags(m)} #Lineup #MatchDay\n\n"
        f"Follow {PAGE_NAME} for live updates 🔔"
    )

# ── Goals + VAR ───────────────────────────────────────────────────
def handle_goals(m):
    mid              = m["id"]
    home,away,hs,as_ = get_score(m)
    current_keys     = set()

    for g in m.get("goals",[]):
        scorer = g.get("scorer",{}).get("name","Unknown")
        minute = g.get("minute","?")
        team   = g.get("team",{}).get("shortName","")
        current_keys.add(f"{mid}_{team}_{minute}_{scorer}")

    # VAR cancellations
    for k in list(posted_goals):
        if k.startswith(f"{mid}_") and k not in current_keys and k not in posted_var:
            posted_var.add(k); save_state()
            post_to_facebook(
                f"❌ VAR CANCELLATION!\n\n"
                f"A goal has been RULED OUT by VAR!\n\n"
                f"🚩 {home} {hs} — {as_} {away}  ← Correct score\n\n"
                f"{flag(m)} {comp(m)} | {hashtags(m)} #VAR #GoalDisallowed\n\n"
                f"Follow {PAGE_NAME} for live updates 🔔"
            )

    # New goals
    for g in m.get("goals",[]):
        scorer = g.get("scorer",{}).get("name","Unknown")
        assist = g.get("assist",{})
        minute = g.get("minute","?")
        team   = g.get("team",{}).get("shortName","")
        k      = f"{mid}_{team}_{minute}_{scorer}"
        if k not in posted_goals:
            posted_goals.add(k); save_state()
            aline = f"🅰️ Assist: {assist['name']}\n\n" if assist and assist.get("name") else ""
            post_to_facebook(
                f"⚽ GOAL! {scorer} scores at {minute}'\n\n"
                f"🚩 {home} {hs} — {as_} {away}\n\n"
                f"{aline}"
                f"{random.choice(GOAL_Q)}\n\n"
                f"{flag(m)} {comp(m)} | {hashtags(m)} #GoalAlert #LiveFootball\n\n"
                f"Follow {PAGE_NAME} for live updates 🔔"
            )

# ── Red cards ─────────────────────────────────────────────────────
def handle_cards(m):
    mid              = m["id"]
    home,away,hs,as_ = get_score(m)
    for b in m.get("bookings",[]):
        if b.get("card") != "RED_CARD": continue
        player = b.get("player",{}).get("name","Unknown")
        minute = b.get("minute","?")
        team   = b.get("team",{}).get("shortName","")
        k      = f"{mid}_{player}_{minute}"
        if k not in posted_cards:
            posted_cards.add(k); save_state()
            post_to_facebook(
                f"🟥 RED CARD! {player} sent off at {minute}'\n\n"
                f"🚩 {home} {hs} — {as_} {away}\n"
                f"{team} down to 10 men!\n\n"
                f"{random.choice(REDCARD_Q)}\n\n"
                f"{flag(m)} {comp(m)} | {hashtags(m)} #RedCard #LiveFootball\n\n"
                f"Follow {PAGE_NAME} for live updates 🔔"
            )

# ── Half time ─────────────────────────────────────────────────────
def handle_halftime(m):
    k = f"{m['id']}_halftime"
    if k in posted_halftimes: return
    home = m["homeTeam"]["shortName"]
    away = m["awayTeam"]["shortName"]
    hs, as_ = (m["score"]["fullTime"].get("home") or m["score"]["halfTime"].get("home") or 0), (m["score"]["fullTime"].get("away") or m["score"]["halfTime"].get("away") or 0)
    gls  = "\n".join(f"  ⚽ {g.get('scorer',{}).get('name','?')} ({g.get('minute','?')}')"
                     f" — {g.get('team',{}).get('shortName','')}"
                     for g in m.get("goals",[])) or "  No goals yet"
    posted_halftimes.add(k); save_state()
    post_to_facebook(
        f"⏸️ HALF TIME | {home} {hs} — {as_} {away}\n\n"
        f"⚽ Goals so far:\n{gls}\n\n"
        f"{random.choice(HT_Q)}\n\n"
        f"{flag(m)} {comp(m)} | {hashtags(m)} #HalfTime #FootballLive\n\n"
        f"Follow {PAGE_NAME} for live updates 🔔"
    )

# ── Full time ─────────────────────────────────────────────────────
def handle_fulltime(m):
    k = f"{m['id']}_fulltime"
    if k in posted_ft: return
    home,away,hs,as_ = get_score(m)
    gls = "\n".join(f"  ⚽ {g.get('scorer',{}).get('name','?')} ({g.get('minute','?')}')"
                    f" — {g.get('team',{}).get('shortName','')}"
                    for g in m.get("goals",[])) or "  No goals"
    if hs > as_:   result, rht = f"🏆 {home} WIN!", "#"+home.replace(" ","")
    elif as_ > hs: result, rht = f"🏆 {away} WIN!", "#"+away.replace(" ","")
    else:          result, rht = "🤝 IT'S A DRAW!", "#Draw"
    posted_ft.add(k); save_state()
    post_to_facebook(
        f"🏁 FULL TIME | {home} {hs} — {as_} {away}\n\n"
        f"{result}\n\n"
        f"⚽ Match Goals:\n{gls}\n\n"
        f"{random.choice(FT_Q)}\n\n"
        f"{flag(m)} {comp(m)} | {hashtags(m)} #FullTime #MatchResult {rht}\n\n"
        f"Follow {PAGE_NAME} for more football updates 🔔"
    )
    # Next fixture for club leagues only
    code = m.get("_league_code","INTL")
    if code != "INTL":
        handle_next_fixture(m)

# ── Next fixture ──────────────────────────────────────────────────
def handle_next_fixture(m):
    k    = f"{m['id']}_nextfixture"
    code = m.get("_league_code","")
    if not code or code == "INTL": return
    home_id = m["homeTeam"].get("id","")
    away_id = m["awayTeam"].get("id","")
    hn, an  = m["homeTeam"]["shortName"], m["awayTeam"]["shortName"]
    home_next = away_next = None
    try:
        today  = datetime.utcnow().strftime("%Y-%m-%d")
        future = (datetime.utcnow()+timedelta(days=30)).strftime("%Y-%m-%d")
        data   = football_get(f"/competitions/{code}/matches?dateFrom={today}&dateTo={future}&status=SCHEDULED")
        if data:
            for mx in data.get("matches",[]):
                mh = mx["homeTeam"].get("id"); ma = mx["awayTeam"].get("id")
                if not home_next and (mh==home_id or ma==home_id): home_next = mx
                if not away_next and (mh==away_id or ma==away_id): away_next = mx
                if home_next and away_next: break
    except Exception as e:
        print(f"[ERROR] next fixture: {e}")
    lines = ["🔜 NEXT FIXTURES\n"]
    for nx in [home_next, away_next]:
        if not nx: continue
        nh = nx["homeTeam"]["shortName"]; na = nx["awayTeam"]["shortName"]
        try: nd = datetime.strptime(nx.get("utcDate",""),"%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
        except: nd = "TBD"
        lines.append(f"  ⚔️  {nh} vs {na} — {nd}")
    if len(lines) <= 1: return
    lines += ["\nPredictions? 👀",
              f"\n{flag(m)} | {hashtags(m)} #NextFixture",
              f"\nFollow {PAGE_NAME} for live updates 🔔"]
    post_to_facebook("\n".join(lines))

# ── Filler ────────────────────────────────────────────────────────
def handle_filler(has_live):
    global last_filler_time
    if has_live: return
    now = time.time()
    if now - last_filler_time < 1800: return
    avail = [p for p in FILLER_POSTS if p[:50] not in posted_filler]
    if not avail:
        posted_filler.clear(); avail = FILLER_POSTS
    post = random.choice(avail)
    if post_to_facebook(post):
        posted_filler.add(post[:50]); last_filler_time = now; save_state()
        print("[FILLER] Posted.")

# ── Process one match ─────────────────────────────────────────────
def process(m):
    status = m.get("status")

    # Lineups: keep trying from 75 mins before kickoff until kickoff
    if status in ("TIMED","SCHEDULED"):
        try:
            ko   = datetime.strptime(m.get("utcDate",""),"%Y-%m-%dT%H:%M:%SZ")
            diff = (ko - datetime.utcnow()).total_seconds() / 60
            if -5 <= diff <= 75:
                handle_lineups(m)
        except Exception:
            pass

    if status == "IN_PLAY":
        handle_kickoff(m)
        handle_goals(m)
        handle_cards(m)

    if status == "PAUSED":
        handle_halftime(m)

    if status == "FINISHED":
        handle_goals(m)   # capture final minute goals
        handle_fulltime(m)

# ── Main cycle ────────────────────────────────────────────────────
preview_posted = None

def check_matches():
    global preview_posted
    today    = datetime.utcnow().strftime("%Y-%m-%d")
    now_hour = datetime.utcnow().hour

    all_matches = {}

    # Club leagues
    for code in LEAGUES:
        data = football_get(f"/competitions/{code}/matches?dateFrom={today}&dateTo={today}")
        if data:
            ms = data.get("matches",[])
            if ms:
                for mx in ms:
                    mx["_league_code"] = code
                    mx["_comp_name"]   = LEAGUES[code]
                all_matches[code] = ms

    # Internationals
    intl = fetch_intl_today()
    if intl:
        all_matches["INTL"] = intl

    # Refresh live scores
    refresh_live()

    # Top 10 for live coverage
    top10 = top_matches(all_matches, n=10)

    # Debug: show what was selected
    print("[DEBUG] Top 10 selected matches:")
    for mx in top10:
        h  = mx.get("homeTeam",{}).get("shortName","?")
        a  = mx.get("awayTeam",{}).get("shortName","?")
        c  = mx.get("_comp_name","?")
        s  = mx.get("status","?")
        sc = importance(mx)
        print(f"  [{s}] {h} vs {a} | {c} | score={sc}")

    has_live = any(
        mx.get("status") in ("IN_PLAY","PAUSED")
        for ms in all_matches.values() for mx in ms
    )

    # Daily preview at 6-7 AM UTC, or on startup if we missed it
    if preview_posted != today:
        if 6 <= now_hour <= 7 or now_hour > 7:
            handle_preview(all_matches)
            preview_posted = today

    # Live updates for top 10 only
    for m in top10:
        process(m)

    if not has_live:
        handle_filler(has_live)

    if APIFOOTBALL_KEY:
        print(f"[BUDGET] API-Football: {apif_used}/90 today")

# ── Run ───────────────────────────────────────────────────────────
def run():
    print(f"{PAGE_NAME} Match Bot v2.0 started!")
    print("Coverage  : Top 10 biggest games per day")
    print("Preview   : Daily morning post grouped by continent")
    print("Live posts: Kick off, Lineups, Goals, VAR, Red Cards, HT, FT")
    print("APIs      : livescore-api.com + RapidFree + API-Football + football-data.org\n")
    while True:
        try:
            check_matches()
        except Exception as e:
            print(f"[ERROR] {e}")
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checked. Waiting 60s...")
        time.sleep(60)

if __name__ == "__main__":
    run()