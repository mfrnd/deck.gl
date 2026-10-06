"""Serves the GPU check page; holds /gate until a result arrives so headless Edge's load event waits."""
import argparse
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DONE = {}


def done(version):
    return DONE.setdefault(version, threading.Event())


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/gate"):
            # Every page load waits for its own result
            version = parse_qs(urlparse(self.path).query).get("v", ["unknown"])[0]
            DONE[version] = threading.Event()
            DONE[version].wait(timeout=240)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        query = parse_qs(urlparse(self.path).query)
        version = query.get("v", ["unknown"])[0]
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path.startswith("/log"):
            with open(Path(self.server.out_dir, f"log-{version}.jsonl"), "ab") as log:
                log.write(body + b"\n")
            self.send_response(204)
            self.end_headers()
            return
        Path(self.server.out_dir, f"result-{version}.json").write_bytes(body)
        self.send_response(204)
        self.end_headers()
        done(version).set()

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    import functools
    server = ThreadingHTTPServer(("127.0.0.1", args.port), functools.partial(Handler, directory=str(args.dir)))
    server.out_dir = args.dir / "out"
    server.out_dir.mkdir(exist_ok=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
