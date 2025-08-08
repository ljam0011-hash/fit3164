#!/usr/bin/env python3
import http.server
import os
from pathlib import Path

class HTTPServer:
    def __init__(self, port=3000, directory='.'):
        self.port = port
        self.directory = Path(directory).resolve()

    def run(self):
        """Start the HTTP server"""
        os.chdir(self.directory)
        handler = http.server.SimpleHTTPRequestHandler
        server_address = ('localhost', self.port)
        httpd = http.server.HTTPServer(server_address, handler)

        print(f"\n🚀 HTTP Server is running!")
        print(f"🌐 URL: http://localhost:{self.port}")
        print(f"📁 Serving directory: {self.directory}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server manually stopped.")
            httpd.shutdown()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Start a local HTTP server.')
    parser.add_argument('--port', '-p', type=int, default=3000, help='Port number (default: 3000)')
    parser.add_argument('--dir', '-d', type=str, default='.', help='Directory to serve (default: current directory)')

    args = parser.parse_args()
    server = HTTPServer(port=args.port, directory=args.dir)
    server.run()
