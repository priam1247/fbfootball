import os, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN        = os.getenv("FB_TOKEN")
FB_PAGE_ID      = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY    = os.getenv("FOOTBALL_KEY")
APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY")
GROQ_KEY        = os.getenv("GROQ_KEY")

def check_vars():
    print("Checking variables...\n")
    ok = True
    for name, val in [
        ("FB_TOKEN", FB_TOKEN),
        ("FB_PAGE_ID", FB_PAGE_ID),
        ("FOOTBALL_KEY", FOOTBALL_KEY),
        ("GROQ_KEY", GROQ_KEY),
    ]:
        if not val:
            print(f"❌ {name} NOT set")
            ok = False
        else:
            print(f"✅ {name} loaded")
    if not APIFOOTBALL_KEY:
        print("⚠️  APIFOOTBALL_KEY not set (optional — for international friendlies)")
    else:
        print(f"✅ APIFOOTBALL_KEY loaded")
    return ok

def test_groq():
    print("\n--- Groq AI ---")
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "Say hello in one word."}],
        "max_tokens": 10
    }
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers=headers, json=payload, timeout=15)
    print("✅ Groq OK!" if r.status_code == 200 else f"❌ FAILED: {r.status_code} {r.text[:200]}")

def test_football_data():
    print("\n--- football-data.org ---")
    r = requests.get("https://api.football-data.org/v4/competitions/PL",
                     headers={"X-Auth-Token": FOOTBALL_KEY}, timeout=10)
    print("✅ football-data.org OK!" if r.status_code == 200 else f"❌ FAILED: {r.status_code}")

def test_apifootball():
    print("\n--- API-Football (internationals) ---")
    if not APIFOOTBALL_KEY:
        print("⏭️  Skipped — not set")
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = requests.get(
        f"https://v3.football.api-sports.io/fixtures?date={today}",
        headers={"x-rapidapi-host": "v3.football.api-sports.io",
                 "x-rapidapi-key": APIFOOTBALL_KEY}, timeout=10)
    if r.status_code == 200:
        rem = r.headers.get("x-ratelimit-requests-remaining", "?")
        print(f"✅ API-Football OK! {rem}/100 requests remaining today")
    else:
        print(f"❌ FAILED: {r.status_code}")

def test_facebook():
    print("\n--- Facebook ---")
    r = requests.post(
        f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
        data={"message": "🧪 ScoreLine Live bot test — delete this post ✅",
              "access_token": FB_TOKEN}, timeout=10)
    print("✅ Facebook OK!" if r.status_code == 200 else f"❌ FAILED: {r.status_code} {r.text[:200]}")

if __name__ == "__main__":
    print("=" * 44)
    print("  ScoreLine Live — Full Test")
    print("=" * 44 + "\n")
    if check_vars():
        test_groq()
        test_football_data()
        test_apifootball()
        test_facebook()
        print("\n✅ All tests done! Push to GitHub → Railway auto-deploys.")
    else:
        print("\n❌ Fix your variables first.")