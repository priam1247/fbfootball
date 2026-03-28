import os, json, time, random, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN        = os.getenv("FB_TOKEN")
FB_PAGE_ID      = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY    = os.getenv("FOOTBALL_KEY")
APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY")
GROQ_KEY        = os.getenv("GROQ_KEY")

FB_POST_URL      = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
FOOTBALL_BASE    = "https://api.football-data.org/v4"
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
GROQ_URL         = "https://api.groq.com/openai/v1/chat/completions"
STATE_FILE       = "match_state.json"
PAGE_NAME        = "ScoreLine Live"
POST_INTERVAL    = 1200  # 20 minutes

# ── Leagues ───────────────────────────────────────────────────────
LEAGUES = {
    "PL":"Premier League","PD":"La Liga","SA":"Serie A",
    "BL1":"Bundesliga","FL1":"Ligue 1","CL":"Champions League",
    "ELC":"Championship","DED":"Eredivisie","PPL":"Primeira Liga",
    "BSA":"Brasileirao","WC":"FIFA World Cup","EC":"European Championship",
}
LEAGUE_FLAGS = {
    "PL":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","PD":"🇪🇸","SA":"🇮🇹","BL1":"🇩🇪","FL1":"🇫🇷",
    "CL":"🏆","ELC":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","DED":"🇳🇱","PPL":"🇵🇹","BSA":"🇧🇷",
    "WC":"🌍","EC":"🇪🇺","INTL":"🌍",
}
LEAGUE_HASHTAGS = {
    "PL":"#PremierLeague #EPL","PD":"#LaLiga","SA":"#SerieA",
    "BL1":"#Bundesliga","FL1":"#Ligue1","CL":"#ChampionsLeague #UCL",
    "ELC":"#Championship","DED":"#Eredivisie","PPL":"#PrimeiraLiga",
    "BSA":"#Brasileirao","WC":"#WorldCup","EC":"#EURO",
    "INTL":"#InternationalFootball #Friendlies",
}

# ── Filler posts ──────────────────────────────────────────────────
FILLER_POSTS = [
    "🔥 DEBATE TIME | Messi vs Ronaldo — who is the GOAT? 🐐\n\nDrop your vote 👇\n\n🇦🇷 Messi or 🇵🇹 Ronaldo?\n\n#Messi #Ronaldo #GOATDebate #Football",
    "⚔️ WHO WINS? | Haaland vs Mbappe — best player in 5 years? 👑\n\n⭐ Haaland or ⭐ Mbappe?\n\nDrop your pick 👇\n\n#Haaland #Mbappe #Football",
    "🐐 LEGEND APPRECIATION | Ronaldinho gave us the most beautiful football ever seen 🎩⚽\n\nAgree? Drop a 🔥 below!\n\n#Ronaldinho #Legend #Football",
    "🌍 WORLD CUP 2026 | 48 teams. 104 matches. USA 🇺🇸 Canada 🇨🇦 Mexico 🇲🇽\n\nWho lifts the trophy? 🏆 Drop your pick 👇\n\n#WorldCup2026 #FIFA #Football",
    "📣 POLL | Best league in the world right now? 🌍\n\n🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League\n🇪🇸 La Liga\n🇩🇪 Bundesliga\n🇮🇹 Serie A\n\nComment your choice 👇\n\n#Football #Poll",
    "😱 DID YOU KNOW? | Brazil 🇧🇷 is the ONLY nation to play in EVERY single World Cup!\n\nDrop a 🇧🇷 if you knew this!\n\n#Brazil #WorldCup #FootballFacts",
    "📣 NEXT GEN POLL | Who is the best young player right now? ⭐\n\n🇪🇸 Yamal\n🏴󠁧󠁢󠁥󠁮󠁧󠁿 Bellingham\n🇧🇷 Endrick\n🇫🇷 Camavinga\n\nYour pick? 👇\n\n#Football #NextGen",
    "📌 RECORD | Cristiano Ronaldo 🇵🇹 is the all-time top scorer in international football ⚽🏆\n\nWill ANYONE ever beat this? 👇\n\n#Ronaldo #CR7 #Record #Football",
    "🧠 FOOTBALL QUIZ | Which club has won the most Champions League titles? 🏆\n\nA) Real Madrid 🇪🇸\nB) AC Milan 🇮🇹\nC) Barcelona 🇪🇸\nD) Bayern Munich 🇩🇪\n\nComment your answer 👇\n\n#ChampionsLeague #FootballQuiz",
    "💬 DEBATE | Who was the better manager — Pep Guardiola or Jose Mourinho? 🧠\n\n👔 Pep or 👔 Mourinho?\n\nDrop your pick 👇\n\n#Guardiola #Mourinho #Football",
    "🏆 GREATEST EVER | Who is the greatest African footballer of all time? 🌍\n\n⭐ Didier Drogba\n⭐ Samuel Eto'o\n⭐ Jay-Jay Okocha\n⭐ George Weah\n\nYour pick? 👇\n\n#AfricanFootball #Football",
    "⚽ THROWBACK | Which era of football was the best to watch? 🎬\n\n90s 🔥 or 2000s 💫 or 2010s ⚡ or Now 🌟\n\nDrop your era 👇\n\n#Football #Throwback",
]

# ── State ─────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                return (
                    d.get("last_post_time", 0),
                    set(d.get("posted_summaries", [])),
                    set(d.get("posted_filler", [])),
                    d.get("preview_posted", ""),
                )
        except Exception:
            pass
    return 0, set(), set(), ""

last_post_time, posted_summaries, posted_filler, preview_posted = load_state()

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({
            "last_post_time": last_post_time,
            "posted_summaries": list(posted_summaries)[-200:],
            "posted_filler": list(posted_filler),
            "preview_posted": preview_posted,
        }, f)

# ── Groq AI ───────────────────────────────────────────────────────
def ask_groq(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.8,
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

# ── football-data.org ─────────────────────────────────────────────
def football_get(path):
    try:
        r = requests.get(f"{FOOTBALL_BASE}{path}",
                         headers={"X-Auth-Token": FOOTBALL_KEY}, timeout=10)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            print("[WARN] football-data.org rate limit")
            time.sleep(60)
    except Exception as e:
        print(f"[ERROR] football-data.org: {e}")
    return None

# ── API-Football (internationals only) ───────────────────────────
apif_used = 0
apif_date = None

def apif_ok():
    global apif_used, apif_date
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if apif_date != today:
        apif_used = 0
        apif_date = today
    return apif_used < 80

def apifootball_get(path):
    global apif_used
    if not APIFOOTBALL_KEY or not apif_ok():
        return None
    try:
        r = requests.get(f"{APIFOOTBALL_BASE}{path}",
                         headers={"x-rapidapi-host": "v3.football.api-sports.io",
                                  "x-rapidapi-key": APIFOOTBALL_KEY}, timeout=10)
        apif_used += 1
        if r.status_code == 200:
            return r.json()
        print(f"[APIFOOTBALL] HTTP {r.status_code}")
    except Exception as e:
        print(f"[APIFOOTBALL ERROR] {e}")
    return None

# ── Fetch finished matches ────────────────────────────────────────
def fetch_finished_club():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    matches = []
    for code in LEAGUES:
        data = football_get(f"/competitions/{code}/matches?dateFrom={today}&dateTo={today}&status=FINISHED")
        if data:
            for m in data.get("matches", []):
                m["_league_code"] = code
                m["_comp_name"] = LEAGUES[code]
                matches.append(m)
    return matches

def fetch_finished_intl():
    if not APIFOOTBALL_KEY:
        return []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = apifootball_get(f"/fixtures?date={today}&status=FT")
    if not data:
        return []
    return data.get("response", [])

# ── Build match data ──────────────────────────────────────────────
def build_club_summary(m):
    home = m["homeTeam"]["shortName"]
    away = m["awayTeam"]["shortName"]
    hs   = m["score"]["fullTime"].get("home", 0) or 0
    as_  = m["score"]["fullTime"].get("away", 0) or 0
    code = m.get("_league_code", "INTL")
    comp = m.get("_comp_name", "Football")
    flag = LEAGUE_FLAGS.get(code, "⚽")
    tags = LEAGUE_HASHTAGS.get(code, "#Football")

    goals = []
    for g in m.get("goals", []):
        scorer = g.get("scorer", {}).get("name", "Unknown")
        minute = g.get("minute", "?")
        team   = g.get("team", {}).get("shortName", "")
        goals.append(f"{scorer} ({minute}') — {team}")

    cards = []
    for b in m.get("bookings", []):
        player = b.get("player", {}).get("name", "Unknown")
        minute = b.get("minute", "?")
        card   = b.get("card", "")
        team   = b.get("team", {}).get("shortName", "")
        if "RED" in card.upper():
            cards.append(f"🟥 {player} ({minute}') — {team}")
        else:
            cards.append(f"🟨 {player} ({minute}') — {team}")

    return {
        "id": str(m["id"]), "home": home, "away": away,
        "home_score": hs, "away_score": as_,
        "comp": comp, "flag": flag, "tags": tags,
        "goals": goals, "cards": cards,
    }

def build_intl_summary(f):
    teams  = f.get("teams", {})
    goals  = f.get("goals", {})
    home   = teams.get("home", {}).get("name", "?")
    away   = teams.get("away", {}).get("name", "?")
    hs     = goals.get("home", 0) or 0
    as_    = goals.get("away", 0) or 0
    league = f.get("league", {})
    comp   = league.get("name", "International")
    fix_id = str(f.get("fixture", {}).get("id", ""))

    goal_list = []
    card_list = []
    for g in f.get("events", []):
        if g.get("type") == "Goal":
            player = g.get("player", {}).get("name", "Unknown")
            minute = g.get("time", {}).get("elapsed", "?")
            team   = g.get("team", {}).get("name", "")
            goal_list.append(f"{player} ({minute}') — {team}")
        elif g.get("type") == "Card":
            player = g.get("player", {}).get("name", "Unknown")
            minute = g.get("time", {}).get("elapsed", "?")
            detail = g.get("detail", "")
            team   = g.get("team", {}).get("name", "")
            if "Red" in detail:
                card_list.append(f"🟥 {player} ({minute}') — {team}")
            else:
                card_list.append(f"🟨 {player} ({minute}') — {team}")

    return {
        "id": fix_id, "home": home, "away": away,
        "home_score": hs, "away_score": as_,
        "comp": comp, "flag": "🌍", "tags": "#InternationalFootball #Friendlies",
        "goals": goal_list, "cards": card_list,
    }

# ── Write post with Groq ──────────────────────────────────────────
def write_summary_post(data):
    home, away = data["home"], data["away"]
    hs, as_    = data["home_score"], data["away_score"]
    goals_text = "\n".join(data["goals"]) if data["goals"] else "No goals scored"
    cards_text = "\n".join(data["cards"]) if data["cards"] else "No cards"

    if hs > as_:   result = f"{home} WIN!"
    elif as_ > hs: result = f"{away} WIN!"
    else:          result = "IT'S A DRAW!"

    prompt = f"""You are a football Facebook page writer for ScoreLine Live.

Write an exciting match summary post using ONLY this real data — do NOT invent anything:

Match: {home} {hs} - {as_} {away}
Competition: {data["comp"]}
Result: {result}
Goalscorers: {goals_text}
Cards: {cards_text}

Format rules:
- Start with 🏁 FULL TIME | {data["flag"]} {data["comp"]}
- Show score boldly: {home} {hs} — {as_} {away}
- List every goalscorer with ⚽ emoji, minute and team
- Show red cards with 🟥, yellow cards with 🟨 if any
- Write 2 exciting sentences about the result
- End with a fan engagement question
- Add hashtags: {data["tags"]} #Football #FullTime
- Final line: Follow ScoreLine Live for more updates 🔔
- Use emojis generously throughout
- Max 250 words
- ONLY use facts given above
"""
    post = ask_groq(prompt)
    if not post:
        # Fallback if Groq fails
        goals_fmt = "\n".join(f"  ⚽ {g}" for g in data["goals"]) or "  No goals"
        cards_fmt = ("\n🃏 Cards:\n" + "\n".join(f"  {c}" for c in data["cards"])) if data["cards"] else ""
        post = (
            f"🏁 FULL TIME | {data['flag']} {data['comp']}\n\n"
            f"{'🏆' if hs != as_ else '🤝'} {home} {hs} — {as_} {away}\n\n"
            f"⚽ Goalscorers:\n{goals_fmt}\n"
            f"{cards_fmt}\n\n"
            f"{result} 🔥\n\n"
            f"Who was your Man of the Match? 🏆 Drop your pick 👇\n\n"
            f"{data['tags']} #Football #FullTime\n\n"
            f"Follow {PAGE_NAME} for more updates 🔔"
        )
    return post

# ── Daily preview ─────────────────────────────────────────────────
def handle_preview():
    global preview_posted, last_post_time
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if preview_posted == today:
        return False

    print("[BOT] Generating daily preview...")
    all_matches = []
    for code in LEAGUES:
        data = football_get(f"/competitions/{code}/matches?dateFrom={today}&dateTo={today}")
        if data:
            for m in data.get("matches", []):
                m["_comp_name"] = LEAGUES[code]
                m["_league_code"] = code
                all_matches.append(m)

    if not all_matches:
        return False

    match_list = []
    for m in all_matches[:10]:
        h    = m["homeTeam"]["shortName"]
        a    = m["awayTeam"]["shortName"]
        c    = m.get("_comp_name", "")
        flag = LEAGUE_FLAGS.get(m.get("_league_code", ""), "⚽")
        try:
            ko = datetime.strptime(m.get("utcDate", ""), "%Y-%m-%dT%H:%M:%SZ").strftime("%H:%M UTC")
        except:
            ko = "TBD"
        match_list.append(f"{flag} {h} vs {a} — {ko} | {c}")

    prompt = f"""Write an exciting daily football preview Facebook post for ScoreLine Live.

Today is {datetime.utcnow().strftime('%A %d %B %Y')}.
Today's matches:
{chr(10).join(match_list)}

Rules:
- Start with ⚽ TODAY'S MATCHES 🔥
- List all matches with their flags, teams and kickoff times
- Write 2 exciting sentences hyping the best games
- Ask fans which game they are most excited about
- Add relevant hashtags
- End with: Follow ScoreLine Live for live updates 🔔
- Use lots of emojis
- Max 200 words
"""
    post = ask_groq(prompt)
    if post and post_to_facebook(post):
        preview_posted = today
        last_post_time = time.time()
        save_state()
        print("[BOT] Daily preview posted.")
        return True
    return False

# ── Filler ────────────────────────────────────────────────────────
def handle_filler():
    global last_post_time, posted_filler
    avail = [p for p in FILLER_POSTS if p[:50] not in posted_filler]
    if not avail:
        posted_filler.clear()
        avail = FILLER_POSTS
    post = random.choice(avail)
    if post_to_facebook(post):
        posted_filler.add(post[:50])
        last_post_time = time.time()
        save_state()
        print("[BOT] Filler posted.")
        return True
    return False

# ── Main cycle ────────────────────────────────────────────────────
def check_matches():
    global last_post_time, posted_summaries

    now     = time.time()
    elapsed = now - last_post_time

    if elapsed < POST_INTERVAL:
        remaining = int((POST_INTERVAL - elapsed) / 60)
        print(f"[BOT] Next post in {remaining} mins.")
        return

    now_hour = datetime.utcnow().hour
    today    = datetime.utcnow().strftime("%Y-%m-%d")

    # 1. Daily preview 6-8 AM UTC
    if preview_posted != today and 6 <= now_hour <= 8:
        if handle_preview():
            return

    # 2. Check finished matches
    print("[BOT] Checking for finished matches...")
    unposted = []

    for m in fetch_finished_club():
        key = f"{m['id']}_summary"
        if key not in posted_summaries:
            unposted.append(("club", m))

    for f in fetch_finished_intl():
        fix_id = str(f.get("fixture", {}).get("id", ""))
        key = f"{fix_id}_summary"
        if key not in posted_summaries:
            unposted.append(("intl", f))

    if unposted:
        match_type, match = unposted[0]
        data = build_club_summary(match) if match_type == "club" else build_intl_summary(match)
        key  = f"{data['id']}_summary"
        post = write_summary_post(data)
        if post_to_facebook(post):
            posted_summaries.add(key)
            last_post_time = time.time()
            save_state()
            print(f"[BOT] Summary posted: {data['home']} vs {data['away']}")
            return

    # 3. No matches — post filler to keep 20 min cadence
    print("[BOT] No new matches. Posting filler...")
    handle_filler()

# ── Run ───────────────────────────────────────────────────────────
def run():
    print(f"{PAGE_NAME} Bot started!")
    print("Mode     : Match summaries + debates/polls")
    print("Interval : Every 20 minutes guaranteed")
    print("APIs     : football-data.org + API-Football + Groq AI")
    print("Coverage : Club leagues + International friendlies\n")
    while True:
        try:
            check_matches()
        except Exception as e:
            print(f"[ERROR] {e}")
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checked. Sleeping 5 mins...")
        time.sleep(300)

if __name__ == "__main__":
    run()