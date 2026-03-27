import os, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN         = os.getenv("FB_TOKEN")
FB_PAGE_ID       = os.getenv("FB_PAGE_ID")
FOOTBALL_KEY     = os.getenv("FOOTBALL_KEY")
APIFOOTBALL_KEY  = os.getenv("APIFOOTBALL_KEY")
LIVESCORE_KEY    = os.getenv("LIVESCORE_KEY")
LIVESCORE_SECRET = os.getenv("LIVESCORE_SECRET")
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY")

def check_vars():
    print("Checking Railway variables...\n")
    ok = True
    for name, val in [
        ("FB_TOKEN",FB_TOKEN),("FB_PAGE_ID",FB_PAGE_ID),
        ("FOOTBALL_KEY",FOOTBALL_KEY),
    ]:
        if not val or "your_" in str(val):
            print(f"❌ {name} NOT set"); ok = False
        else:
            print(f"✅ {name} loaded")
    # Optional but important
    for name, val in [
        ("LIVESCORE_KEY",LIVESCORE_KEY),("LIVESCORE_SECRET",LIVESCORE_SECRET),
        ("RAPIDAPI_KEY",RAPIDAPI_KEY),("APIFOOTBALL_KEY",APIFOOTBALL_KEY),
    ]:
        if not val:
            print(f"⚠️  {name} not set (optional but recommended)")
        else:
            print(f"✅ {name} loaded")
    return ok

def test_facebook():
    print("\n--- Facebook ---")
    r = requests.post(f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
                      data={"message":"🧪 ScoreLine Live bot test — delete this post ✅",
                            "access_token":FB_TOKEN}, timeout=10)
    print("✅ Facebook OK!" if r.status_code==200 else f"❌ FAILED: {r.status_code} {r.text[:200]}")

def test_football_data():
    print("\n--- football-data.org ---")
    r = requests.get("https://api.football-data.org/v4/competitions/PL",
                     headers={"X-Auth-Token":FOOTBALL_KEY}, timeout=10)
    print("✅ football-data.org OK!" if r.status_code==200 else f"❌ FAILED: {r.status_code}")

def test_livescore():
    print("\n--- livescore-api.com ---")
    if not LIVESCORE_KEY or not LIVESCORE_SECRET:
        print("⏭️  Skipped — no key set"); return
    r = requests.get(
        f"https://livescore-api.com/api-client/matches/live.json"
        f"?key={LIVESCORE_KEY}&secret={LIVESCORE_SECRET}", timeout=10)
    if r.status_code == 200:
        d = r.json()
        if d.get("success"):
            items = d.get("data",{})
            total = len(items.get("match",items) if isinstance(items,dict) else items)
            print(f"✅ livescore-api.com OK! {total} live matches right now")
        else:
            print(f"❌ API error: {d.get('error','unknown')}")
    else:
        print(f"❌ FAILED: {r.status_code}")

def test_rapidfree():
    print("\n--- RapidAPI Free Football ---")
    if not RAPIDAPI_KEY:
        print("⏭️  Skipped — no key set"); return
    r = requests.get(
        "https://free-api-live-football-data.p.rapidapi.com/football-current-live",
        headers={"x-rapidapi-host":"free-api-live-football-data.p.rapidapi.com",
                 "x-rapidapi-key":RAPIDAPI_KEY}, timeout=10)
    if r.status_code == 200:
        d     = r.json()
        total = len(d.get("response", d.get("matches",[])))
        print(f"✅ RapidFree OK! {total} live matches right now")
    else:
        print(f"❌ FAILED: {r.status_code}")

def test_apifootball():
    print("\n--- API-Football (100/day) ---")
    if not APIFOOTBALL_KEY:
        print("⏭️  Skipped — no key set"); return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    r = requests.get(
        f"https://v3.football.api-sports.io/fixtures?date={today}",
        headers={"x-rapidapi-host":"v3.football.api-sports.io",
                 "x-rapidapi-key":APIFOOTBALL_KEY}, timeout=10)
    if r.status_code == 200:
        d   = r.json()
        rem = r.headers.get("x-ratelimit-requests-remaining","?")
        print(f"✅ API-Football OK! {len(d.get('response',[]))} fixtures today. {rem}/100 requests remaining")
    else:
        print(f"❌ FAILED: {r.status_code}")

if __name__ == "__main__":
    print("="*44)
    print("  ScoreLine Live — Full API Test")
    print("="*44+"\n")
    if check_vars():
        test_football_data()
        test_livescore()
        test_rapidfree()
        test_apifootball()
        test_facebook()
        print("\n✅ All tests done! Push to GitHub → Railway auto-deploys.")
    else:
        print("\n❌ Fix your Railway variables first.")
