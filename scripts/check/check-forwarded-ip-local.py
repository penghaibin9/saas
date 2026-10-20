#!/usr/bin/env python3
"""Loopback-only check of the actual MySQL Nginx configuration and includes.

No SaaS process, production connection, Docker engine or TLS certificate is used.
Only temporary paths, worker count, user and loopback endpoints are substituted.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time


class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"xff": self.headers.get("X-Forwarded-For"),
                           "real": self.headers.get("X-Real-IP"),
                           "proto": self.headers.get("X-Forwarded-Proto")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def check(repo: Path) -> dict:
    executable = shutil.which("nginx")
    if executable is None:
        return {"executed": False, "passed": False, "reason": "nginx executable required"}
    config_root = repo / "deploy/nginx"
    checks = {}
    with tempfile.TemporaryDirectory(prefix="saas-proxy-check-") as directory:
        temporary = Path(directory)
        temporary.chmod(0o755)
        for name in ("conf", "pc", "enterprise", "miniapp"):
            (temporary / name).mkdir()
        for name in ("pc", "enterprise", "miniapp"):
            (temporary / name / "index.html").write_text("LOCAL-TEST-" + name)
        (temporary / "pc/app.a123.js").write_text("/* local static test */")
        for name in ("security-http.conf", "security-server.conf", "security-headers.conf"):
            text = (config_root / name).read_text(encoding="utf-8")
            (temporary / "conf" / name).write_text(
                text.replace("/etc/nginx/conf.d/", str(temporary / "conf") + "/"), encoding="utf-8")
        backend = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        process = None
        try:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            text = (config_root / "nginx.mysql.conf").read_text(encoding="utf-8")
            text = re.sub(r"^user\s+nginx;", "", text, flags=re.M)
            text = re.sub(r"^worker_processes\s+auto;", "worker_processes 1;", text, flags=re.M)
            text = text.replace("/var/log/nginx/", str(temporary) + "/")
            text = text.replace("/var/run/nginx.pid", str(temporary / "nginx.pid"))
            text = text.replace("/etc/nginx/conf.d/", str(temporary / "conf") + "/")
            text = text.replace("/usr/share/nginx/html/pc", str(temporary / "pc"))
            text = text.replace("/usr/share/nginx/html", str(temporary))
            text = text.replace("server backend:8000;", f"server 127.0.0.1:{backend.server_port};")
            text, replacements = re.subn(r"listen\s+80;", f"listen 127.0.0.1:{port};", text)
            if replacements != 1:
                raise RuntimeError("expected exactly one HTTP listener; inspect changed topology")
            text = text.replace("http {", f"http {{\n    client_body_temp_path {temporary}/client_temp;\n"
                                f"    proxy_temp_path {temporary}/proxy_temp;", 1)
            config = temporary / "nginx.conf"
            config.write_text(text, encoding="utf-8")
            syntax = subprocess.run([executable, "-t", "-c", str(config), "-p", str(temporary)],
                                    capture_output=True, text=True, timeout=10)
            checks["syntax"] = syntax.returncode == 0
            if not checks["syntax"]:
                return {"executed": True, "passed": False, "checks": checks, "error": syntax.stderr}
            process = subprocess.Popen([executable, "-c", str(config), "-p", str(temporary),
                                        "-g", "daemon off;"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError("local nginx stopped before readiness")
                    time.sleep(0.02)
            else:
                raise RuntimeError("local nginx did not listen")

            def get(path: str, headers=None):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                try:
                    connection.request("GET", path, headers=headers or {})
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()

            status, _, body = get("/api/proxy-check", {
                "X-Forwarded-For": "1.1.1.1", "X-Real-IP": "9.9.9.9", "X-Forwarded-Proto": "https",
            })
            checks["edge_replaces_untrusted_headers"] = status == 200 and json.loads(body) == {
                "xff": "127.0.0.1", "real": "127.0.0.1", "proto": "http",
            }
            for path, expected in (("/uploads/private.xlsx", 404), ("/exports/grades.xlsx", 404),
                                   ("/.env", 403), ("/backup.sql", 403)):
                checks["deny:" + path] = get(path)[0] == expected
            for path, name in (("/login", "pc"), ("/enterprise/login", "enterprise"),
                               ("/miniapp/pages/login", "miniapp")):
                status, headers, body = get(path)
                checks["history:" + name] = status == 200 and body.decode() == "LOCAL-TEST-" + name
                checks["security_headers:" + name] = all(key in headers for key in (
                    "Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options"))
            status, headers, _ = get("/app.a123.js")
            checks["static_asset_headers"] = status == 200 and "Content-Security-Policy" in headers
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            backend.shutdown()
            backend.server_close()
            thread.join(timeout=2)
    version = subprocess.run([executable, "-v"], capture_output=True, text=True, timeout=5)
    return {"executed": True, "passed": all(checks.values()), "checks": checks,
            "nginxVersion": version.stderr.strip(),
            "scope": "loopback nginx + echo backend; actual config/include directives",
            "fullSaasBackend": "NOT_RUN", "docker": "NOT_RUN", "productionTls": "NOT_RUN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        result = check(args.repo.resolve())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        result = {"executed": False, "passed": False, "errorType": type(exc).__name__, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
