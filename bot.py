import os
import runpy
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def start_http_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=start_http_server, daemon=True).start()
    
    # Launch the userbot to monitor channels (it will gracefully exit if TG_SESSION_STRING is missing)
    userbot_path = str(Path(__file__).parent / "userbot" / "userbot.py")
    subprocess.Popen([sys.executable, userbot_path])
    
    # Run the main telegram bot
    runpy.run_path(str(Path(__file__).parent / "bot" / "bot.py"), run_name="__main__")
