"""
serve_site.py — local docs server with Resync buttons.

The generated site is still static HTML (file:// works, no JavaScript required
to read). This process is the optional local server: it serves `site/`, injects
a Resync bar into HTML responses, and on POST runs `bin/lookout` then
`render_site.py`.

Usage:
    python3 serve_site.py [--port 8899] [--out site]

Resync is localhost-only. It never writes to a target repo.
"""
import argparse
import html
import os
import re
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).parent
DEFAULT_PORT = 8899
DEFAULT_BIND = "127.0.0.1"

_PROJECT_RE = re.compile(r"/notes/projects/([^/]+)/")

_job_lock = threading.Lock()
_job = {
    "running": False,
    "target": None,
    "log": "",
    "error": None,
    "started": False,
}


def _load_targets() -> list[str]:
    try:
        import yaml
        data = yaml.safe_load((REPO_ROOT / "targets.yaml").read_text()) or {}
        return list(data.get("targets", {}).keys())
    except Exception:
        return []


def _run_resync(target: str | None, out_dir: Path) -> None:
    with _job_lock:
        _job["running"] = True
        _job["error"] = None
        _job["log"] = ""
        _job["target"] = target
        _job["started"] = True
    chunks: list[str] = []
    try:
        lookout = REPO_ROOT / "bin" / "lookout"
        if target:
            cmd = [sys.executable, str(lookout), target]
        else:
            cmd = [sys.executable, str(lookout), "--all"]
        chunks.append("$ " + " ".join(cmd) + "\n")
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        chunks.append(proc.stdout or "")
        if proc.stderr:
            chunks.append(proc.stderr)
        if proc.returncode != 0:
            raise RuntimeError(f"lookout exited {proc.returncode}")

        render = [sys.executable, str(REPO_ROOT / "render_site.py"), "--out", str(out_dir)]
        chunks.append("\n$ " + " ".join(render) + "\n")
        proc2 = subprocess.run(
            render,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        chunks.append(proc2.stdout or "")
        if proc2.stderr:
            chunks.append(proc2.stderr)
        if proc2.returncode != 0:
            raise RuntimeError(f"render_site exited {proc2.returncode}")
    except Exception as exc:
        with _job_lock:
            _job["error"] = str(exc)
            _job["log"] = "".join(chunks)
            _job["running"] = False
        return
    with _job_lock:
        _job["log"] = "".join(chunks)
        _job["running"] = False


def _toolbar(project: str | None) -> str:
    buttons = [
        '<form method="post" action="/resync">'
        '<button type="submit">Resync all</button></form>'
    ]
    if project:
        buttons.append(
            f'<form method="post" action="/resync/{html.escape(project)}">'
            f'<button type="submit">Resync {html.escape(project)}</button></form>'
        )
    return (
        '<div class="resync-bar">'
        + "".join(buttons)
        + '<span class="resync-hint">Re-runs lookout, then rebuilds these pages. '
        "About a minute. Localhost only.</span></div>"
    )


def _waiting_page(project: str | None) -> bytes:
    label = project or "all projects"
    body = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>Resyncing…</title>
<style>
 body {{ font-family: -apple-system, sans-serif; margin: 2rem; color: #222; }}
 pre {{ background: #f4f4f2; padding: 1rem; overflow: auto; font-size: 12px; }}
</style>
</head><body>
<h1>Resyncing {html.escape(label)}</h1>
<p>This page refreshes until the run finishes. Leave it open.</p>
</body></html>
"""
    return body.encode("utf-8")


def _done_page(error: str | None, log: str, next_href: str) -> bytes:
    if error:
        title = "Resync failed"
        lead = f"<p>{html.escape(error)}</p>"
    else:
        title = "Resync finished"
        lead = f'<p><a href="{html.escape(next_href)}">Back to the docs</a></p>'
    body = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
 body {{ font-family: -apple-system, sans-serif; margin: 2rem; color: #222; }}
 pre {{ background: #f4f4f2; padding: 1rem; overflow: auto; font-size: 12px; max-height: 24rem; }}
</style>
</head><body>
<h1>{html.escape(title)}</h1>
{lead}
<pre>{html.escape(log[-8000:])}</pre>
</body></html>
"""
    return body.encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    out_dir: Path = REPO_ROOT / "site"
    valid_targets: list[str] = []

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        target = None
        if path == "/resync":
            target = None
        elif path.startswith("/resync/"):
            target = path.split("/", 2)[2]
            if target not in self.valid_targets:
                self._send(404, b"unknown target")
                return
        else:
            self._send(404, b"not found")
            return

        with _job_lock:
            running = _job["running"]
        if running:
            self.send_response(303)
            self.send_header("Location", "/resync-status")
            self.end_headers()
            return

        thread = threading.Thread(
            target=_run_resync,
            args=(target, self.out_dir),
            daemon=True,
        )
        thread.start()
        self.send_response(303)
        self.send_header("Location", "/resync-status")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") == "/resync-status":
            with _job_lock:
                running = _job["running"]
                error = _job["error"]
                log = _job["log"]
                target = _job["target"]
                started = _job["started"]
            if running or not started:
                self._send(200, _waiting_page(target))
                return
            next_href = "/"
            if target:
                next_href = f"/notes/projects/{target}/situation.html"
            self._send(200, _done_page(error, log, next_href))
            return

        # Serve static files; inject the resync bar into HTML.
        rel = parsed.path.lstrip("/") or "index.html"
        fs_path = (self.out_dir / rel).resolve()
        try:
            fs_path.relative_to(self.out_dir.resolve())
        except ValueError:
            self._send(403, b"forbidden")
            return
        if fs_path.is_dir():
            fs_path = fs_path / "index.html"
        if not fs_path.is_file():
            self._send(404, b"not found")
            return

        data = fs_path.read_bytes()
        ctype = self.guess_type(str(fs_path))
        if fs_path.suffix.lower() == ".html":
            project = None
            m = _PROJECT_RE.search(parsed.path)
            if m and m.group(1) in self.valid_targets:
                project = m.group(1)
            bar = _toolbar(project).encode("utf-8")
            text = data
            marker = b"<body>"
            idx = text.find(marker)
            if idx != -1:
                insert_at = idx + len(marker)
                text = text[:insert_at] + b"\n" + bar + text[insert_at:]
            data = text
            ctype = "text/html; charset=utf-8"
        self._send(200, data, ctype)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the lookout HTML site")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--bind", default=DEFAULT_BIND)
    parser.add_argument("--out", default=str(REPO_ROOT / "site"))
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    if not (out_dir / "index.html").exists():
        print(f"No site at {out_dir}. Run: python3 render_site.py", file=sys.stderr)
        return 1

    Handler.out_dir = out_dir
    Handler.valid_targets = _load_targets()
    # SimpleHTTPRequestHandler uses cwd for translation; we serve via out_dir
    # directly in do_GET, so chdir is unnecessary.

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"lookout site: http://{args.bind}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    sys.exit(main())
