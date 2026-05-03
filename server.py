import http.server
import socketserver
import json
import os
import urllib.request
import urllib.error

# --- CONFIGURATION ---
# Render dynamically assigns a PORT. Fallback to 8080 for local testing.
PORT = int(os.environ.get("PORT", 8080))

# Safely grabs the key from Render's Environment Variables, or replace the second string with your key.
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")
MODEL_NAME = "claude-3-haiku-20240307"

# Define Allowed Origins (Who is allowed to talk to this server?)
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
        # 1. Grab the origin of the website trying to connect
        origin = self.headers.get('Origin')
        
        # 2. Check if they are on the VIP list
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
        
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        print(f"---------> INCOMING REQUEST: {self.path} <---------")

        if 'chat' in self.path:
            try:
                # 1. Parse the incoming request from the frontend
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                user_json = json.loads(post_data)

                print(f"1. Calling Anthropic (Model: {MODEL_NAME})...")
                
                # 2. Format the payload for Claude
                req_data = json.dumps({
                    "model": MODEL_NAME, 
                    "max_tokens": 150,
                    "messages": user_json.get('messages', [])
                }).encode('utf-8')

                # 3. Create the native Python HTTP request
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=req_data,
                    headers={
                        "x-api-key": API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    method="POST"
                )

                try:
                    # 4. Fire the request and read the response
                    with urllib.request.urlopen(req) as response:
                        result_data = response.read()
                        
                    print(f"2. Success! Received valid response.")
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(result_data)

                # Catch errors directly from the Anthropic API (e.g., bad API key, rate limits)
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode('utf-8')
                    print(f"!!! API ERROR: {e.code} - {error_body}")
                    self.send_response(e.code)
                    self.send_header('Content-type', 'application/json')
                    self._set_cors_headers()
                    self.end_headers()
                    self.wfile.write(error_body.encode())

            # Catch server-level crashes (e.g., malformed JSON)
            except Exception as e:
                print(f"!!! CRASH: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_error(404)

print(f"Server V8 (PORT {PORT}) started at http://0.0.0.0:{PORT}")
socketserver.TCPServer.allow_reuse_address = True
# Bind to 0.0.0.0 so Render can route external traffic to it
with socketserver.TCPServer(("0.0.0.0", PORT), ProxyHandler) as httpd:
    httpd.serve_forever()
