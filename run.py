import os
import threading
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler

load_dotenv()

import bot
import news_bot

# ── Keep-alive server for Railway ────────────────────────────────
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ScoreLine Live Bot is running!")

    def log_message(self, format, *args):
        pass  # Silence HTTP logs

def run_server():
    port   = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()

# ── Start everything ──────────────────────────────────────────────
print("=" * 42)
print("  ScoreLine Live — Football Bot Suite")
print("=" * 42)
print()
print("Starting match bot + news bot simultaneously...")
print()

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
print(f"Keep-alive server started on port {os.getenv('PORT', 8080)}")

match_thread = threading.Thread(target=bot.run, daemon=True)
match_thread.start()

news_thread = threading.Thread(target=news_bot.run, daemon=True)
news_thread.start()

match_thread.join()
news_thread.join()
