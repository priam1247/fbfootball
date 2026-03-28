import os, requests
from dotenv import load_dotenv

load_dotenv()

FB_TOKEN   = os.getenv("FB_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
GEMINI_KEY = os.getenv("GEMINI_KEY")

def check_vars():
    print("Checking variables...\n")
    ok = True
    for name, val in [
        ("FB_TOKEN", FB_TOKEN),
        ("FB_PAGE_ID", FB_PAGE_ID),
        ("GEMINI_KEY", GEMINI_KEY),
    ]:
        if not val:
            print(f"❌ {name} NOT set")
            ok = False
        else:
            print(f"✅ {name} loaded")
    return ok

def test_gemini():
    print("\n--- Gemini API ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Say hello in one word."}]}],
        "generationConfig": {"maxOutputTokens": 10}
    }
    r = requests.post(url, json=payload, timeout=15)
    if r.status_code == 200:
        print("✅ Gemini API OK!")
    else:
        print(f"❌ FAILED: {r.status_code} {r.text[:200]}")

def test_facebook():
    print("\n--- Facebook ---")
    r = requests.post(
        f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
        data={"message": "🧪 ScoreLine Live bot test — delete this post ✅",
              "access_token": FB_TOKEN},
        timeout=10
    )
    print("✅ Facebook OK!" if r.status_code == 200 else f"❌ FAILED: {r.status_code} {r.text[:200]}")

if __name__ == "__main__":
    print("=" * 44)
    print("  ScoreLine Live — API Test (Gemini)")
    print("=" * 44 + "\n")
    if check_vars():
        test_gemini()
        test_facebook()
        print("\n✅ All tests done!")
    else:
        print("\n❌ Fix your variables first.")