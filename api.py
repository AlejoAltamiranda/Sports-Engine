import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/partidos":
            try:
                with open("matches.json") as f:
                    data = json.load(f)
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            except:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    print("API en puerto 8080")
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
