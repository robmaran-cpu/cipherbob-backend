import http.server
import socketserver
import json
import os
import urllib.request
import urllib.error

# --- CONFIGURATION ---
PORT = int(os.environ.get("PORT", 8080))
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

# Clean first-party API identifier slug for stable inference routing
MODEL_NAME = "claude-haiku-4-5"

ALLOWED_ORIGINS = [
    "http://localhost:8788",
    "http://127.0.0.1:8788",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://hypedecay.com",
    "https://www.hypedecay.com",
    "https://robmaran.com",
    "https://www.robmaran.com"
]

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    
    def _set_cors_headers(self):
        origin = self.headers.get('Origin')
        
        # Universal fallback handling: Grants passage to browser-native 'null' 
        # configurations and seamlessly matches all dynamic staging pages subdomains.
        if not origin or origin == 'null':
            self.send_header('Access-Control-Allow-Origin', '*')
        elif origin in ALLOWED_ORIGINS or origin.endswith('.pages.dev'):
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            self.send_header('Access-Control-Allow-Origin', '*')
            
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type, Authorization, Accept")

    def do_OPTIONS(self):
        # Intercept and terminate preflight OPTIONS validations immediately with an empty 200 frame
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        print(f"---------> INCOMING REQUEST: {self.path} <---------", flush=True)

        if 'chat' in self.path:
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                user_json = json.loads(post_data)

                print(f"1. Calling Anthropic (Model: {MODEL_NAME})...", flush=True)
                
                req_data = json.dumps({
                    "model": MODEL_NAME, 
                    "max_tokens": 150,
                    "messages": user_json.get('messages', [])
                }).encode('utf-8')

                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=req_data,
                    headers={
                        "x-api-key": API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                        # 🚨 REMOVED: anthropic-beta header is deleted to prevent 400 Bad Request syntax drops
                    },
                    method="POST"
                )

                try:
                    with urllib.request.urlopen(req) as response:
                        result_data = response.read()
                        
                    print(f"2. Success! Received valid response.", flush=True)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(result_data)

                except urllib.error.HTTPError as e:
                    error_body = e.read().decode('utf-8')
                    print(f"!!! API ERROR: {e.code} - {error_body}", flush=True)
                    self.send_response(e.code)
                    self.send_header('Content-type', 'application/json')
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(error_body.encode())

            except Exception as e:
                print(f"!!! CRASH: {e}", flush=True)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": {"message": str(e)}}).encode())
        else:
            print("!!! ROUTE NOT FOUND", flush=True)
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

print(f"Server V11 (PORT {PORT}) started at http://0.0.0.0:{PORT}", flush=True)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), ProxyHandler) as httpd:
    httpd.serve_forever()
