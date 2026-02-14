import http.server
import socketserver
import json
import subprocess
import sys
import os

# --- SECURITY CONFIGURATION ---
# 1. Get the PORT from the hosting provider (default to 8080 if not set)
PORT = int(os.environ.get("PORT", 8080))

# 2. Get the API Key from the environment (NEVER hardcode this in live code)
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# 3. Define Allowed Origins (Who is allowed to talk to this server?)
ALLOWED_ORIGINS = [
    "https://hypedecay.com",
    "https://www.hypedecay.com",
    "http://hypedecay.com" # Optional: allow non-SSL if needed
]

# Check if key exists before starting
if not API_KEY:
    print("CRITICAL ERROR: 'ANTHROPIC_API_KEY' environment variable not found!")
    print("Please set this variable in your hosting dashboard.")
    sys.exit(1)

MODEL_NAME = "claude-3-haiku-20240307"

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_OPTIONS(self):
        # This handles the "Pre-flight" check browsers do for security
        origin = self.headers.get('Origin')
        
        self.send_response(200, "ok")
        
        # Only allow our specific domain
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
        
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")
        self.end_headers()

    def do_POST(self):
        print(f"---------> INCOMING REQUEST: {self.path} <---------")

        # Security: Check Origin header
        origin = self.headers.get('Origin')
        if origin not in ALLOWED_ORIGINS:
            print(f"!!! SECURITY BLOCK: Request from unauthorized origin: {origin}")
            self.send_error(403, "Forbidden: Unauthorized Origin")
            return

        if 'chat' in self.path:
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                user_json = json.loads(post_data)

                print(f"1. Calling Anthropic (Model: {MODEL_NAME})...")
                
                curl_data = {
                    "model": MODEL_NAME, 
                    "max_tokens": 150,
                    "messages": user_json['messages']
                }

                # We use the SECURE key variable here
                cmd = [
                    "curl", "https://api.anthropic.com/v1/messages",
                    "-s", 
                    "-H", f"x-api-key: {API_KEY}",
                    "-H", "anthropic-version: 2023-06-01",
                    "-H", "content-type: application/json",
                    "-d", json.dumps(curl_data)
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"!!! CURL ERROR: {result.stderr}")
                    raise Exception("Curl command failed")

                if '"error"' in result.stdout:
                    print(f"!!! API ERROR: {result.stdout}")
                    self.send_response(500) 
                    self.end_headers()
                    self.wfile.write(result.stdout.encode())
                    return

                print(f"2. Success! Response sent to {origin}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                
                # Dynamic CORS header based on who asked
                self.send_header('Access-Control-Allow-Origin', origin)
                
                self.end_headers()
                self.wfile.write(result.stdout.encode())

            except Exception as e:
                print(f"!!! CRASH: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_error(404)

print(f"CipherBob Secure Server (PORT {PORT}) is listening...")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
    httpd.serve_forever()