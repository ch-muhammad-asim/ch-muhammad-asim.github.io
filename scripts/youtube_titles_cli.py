#!/usr/bin/env python3
"""Bulk YouTube title optimizer using only the Python standard library.

The tool intentionally preserves each video's existing snippet metadata and
changes only snippet.title during apply.
"""

from __future__ import annotations

import argparse
import csv
import http.server
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any


API_ROOT = "https://www.googleapis.com/youtube/v3"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
DEFAULT_CHANNEL_ID = "UCH67fQImw9yO3uvD3h9F3Jg"


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, Any]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None and form is not None:
        raise ValueError("Use either body or form, not both")
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc


def read_oauth_client(path: Path) -> tuple[str, str]:
    data = json.loads(path.read_text())
    cfg = data.get("installed") or data.get("web")
    if not cfg:
        raise SystemExit(f"{path} does not look like an OAuth client JSON file")
    return cfg["client_id"], cfg.get("client_secret", "")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def token_from_credentials(credentials: Path, token_path: Path) -> str:
    token = load_token(token_path)
    if token:
        return token

    client_id, client_secret = read_oauth_client(credentials)
    port = free_port()
    redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    class Handler(http.server.BaseHTTPRequestHandler):
        code: str | None = None
        error: str | None = None

        def log_message(self, *_: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            Handler.code = qs.get("code", [None])[0]
            Handler.error = qs.get("error", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"YouTube CLI authorized. You can close this tab.")

    eprint("Opening browser for YouTube OAuth consent...")
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", port), Handler) as server:
        server.timeout = 180
        while Handler.code is None and Handler.error is None:
            server.handle_request()

    if Handler.error:
        raise SystemExit(f"OAuth failed: {Handler.error}")
    if not Handler.code:
        raise SystemExit("OAuth timed out without a code")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": Handler.code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    token_data = request_json("POST", TOKEN_URL, form=payload)
    token_data["created_at"] = int(time.time())
    token_path.write_text(json.dumps(token_data, indent=2))
    return token_data["access_token"]


def load_token(token_path: Path) -> str | None:
    if not token_path.exists():
        return None
    data = json.loads(token_path.read_text())
    expires_at = data.get("created_at", 0) + data.get("expires_in", 0) - 60
    if data.get("access_token") and time.time() < expires_at:
        return data["access_token"]
    if data.get("refresh_token"):
        client_id = data.get("client_id")
        client_secret = data.get("client_secret", "")
        if client_id:
            refreshed = request_json(
                "POST",
                TOKEN_URL,
                form={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": data["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
            data.update(refreshed)
            data["created_at"] = int(time.time())
            token_path.write_text(json.dumps(data, indent=2))
            return data["access_token"]
    return None


def api_token(args: argparse.Namespace) -> str:
    token = os.environ.get("YOUTUBE_ACCESS_TOKEN")
    if token:
        return token
    if not args.credentials:
        raise SystemExit(
            "Need OAuth. Set YOUTUBE_ACCESS_TOKEN or pass --credentials credentials.json"
        )
    token_path = Path(args.token)
    access = token_from_credentials(Path(args.credentials), token_path)
    data = json.loads(token_path.read_text())
    client_id, client_secret = read_oauth_client(Path(args.credentials))
    data.setdefault("client_id", client_id)
    data.setdefault("client_secret", client_secret)
    token_path.write_text(json.dumps(data, indent=2))
    return access


def list_uploads(token: str) -> list[dict[str, str]]:
    channel = request_json(
        "GET",
        f"{API_ROOT}/channels",
        token=token,
        params={"part": "contentDetails", "mine": "true"},
    )
    items = channel.get("items", [])
    if not items:
        raise SystemExit("No authenticated YouTube channel found for this account")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out: list[dict[str, str]] = []
    page = ""
    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads,
            "maxResults": "50",
        }
        if page:
            params["pageToken"] = page
        data = request_json("GET", f"{API_ROOT}/playlistItems", token=token, params=params)
        for item in data.get("items", []):
            snip = item["snippet"]
            out.append(
                {
                    "video_id": item["contentDetails"]["videoId"],
                    "published_at": snip.get("publishedAt", ""),
                    "current_title": snip.get("title", ""),
                }
            )
        page = data.get("nextPageToken", "")
        if not page:
            return out


def optimize_title(title: str) -> str:
    title = re.sub(r"#\w+", "", title)
    title = re.sub(r"\((?:English|Urdu|Hindi)\)", "", title, flags=re.I)
    title = title.replace("|", ":")
    title = title.replace("&", "and")
    title = re.sub(r"[\U00010000-\U0010ffff]", "", title)
    title = re.sub(r"[💪🚀✨🔥🔒🛡️✅🔧🔑💻🤯]+", "", title)
    title = re.sub(r"\s+", " ", title).strip(" -:|")
    title = re.sub(r"\bkubernetes\b", "Kubernetes", title, flags=re.I)
    title = re.sub(r"\bterraform\b", "Terraform", title, flags=re.I)
    title = re.sub(r"\bterragrunt\b", "Terragrunt", title, flags=re.I)
    title = re.sub(r"\bazure\b", "Azure", title, flags=re.I)
    title = re.sub(r"\baws\b", "AWS", title, flags=re.I)
    title = re.sub(r"\bgcp\b", "GCP", title, flags=re.I)
    title = re.sub(r"\bgke\b", "GKE", title, flags=re.I)
    title = re.sub(r"\beks\b", "EKS", title, flags=re.I)
    title = re.sub(r"\baks\b", "AKS", title, flags=re.I)
    title = re.sub(r"\bdevops\b", "DevOps", title, flags=re.I)
    title = re.sub(r"\bdevsecops\b", "DevSecOps", title, flags=re.I)
    title = re.sub(r"\bistio\b", "Istio", title, flags=re.I)
    title = re.sub(r"\btraefik\b", "Traefik", title, flags=re.I)
    title = re.sub(r"\bhashicorp\b", "HashiCorp", title, flags=re.I)
    title = re.sub(r"\bpostgresql\b", "PostgreSQL", title, flags=re.I)
    title = re.sub(r"\bcloud sql\b", "Cloud SQL", title, flags=re.I)
    title = re.sub(r"\bssl/tls\b", "SSL/TLS", title, flags=re.I)
    title = re.sub(r"\bmtls\b", "mTLS", title, flags=re.I)
    title = re.sub(r"\bai\b", "AI", title, flags=re.I)
    title = re.sub(r"\s+:\s+", ": ", title)
    if len(title) > 95:
        title = title[:95].rsplit(" ", 1)[0].rstrip(" :-")
    return title[:100]


def cmd_export(args: argparse.Namespace) -> None:
    token = api_token(args)
    rows = list_uploads(token)
    Path(args.output).write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"Exported {len(rows)} videos to {args.output}")


def cmd_suggest(args: argparse.Namespace) -> None:
    rows = json.loads(Path(args.input).read_text())
    manual = {
        "jkPk08RmCc0": "Build a Secure Azure AKS Platform: VNet, WAF, Key Vault, Istio, ArgoCD",
        "TCdO8URfpqc": "Docker MCP Server: Build an AI Node.js App with PostgreSQL",
        "fYUkDZID6x4": "Docker MCP Server: Build an AI Agent with PostgreSQL Read-Write Access",
        "5iPWoICzLUk": "Secure GCP Cloud SQL Connection with Encrypted Tunnel",
        "N3hlqVvVO-o": "Free AI Agents for Software Development and Deployments",
        "gKBJqSryvzE": "Kubernetes SSL/TLS Multi-Cluster HA with Cloudflare Tunnels and Traefik",
        "mqTSn9_zoi0": "Secure Kubernetes Internal Apps SSL/TLS with Cloudflare Tunnels",
        "ErqtqKTzEug": "Traefik and Istio Ambient Mesh mTLS L4/L7 Encryption on GKE",
        "CuSCICkCtZA": "Pritunl WireGuard VPN: High-Speed Encrypted Sessions",
        "J2r0q9KTb70": "Live Production GCP Cloud SQL Migration with Local Docker",
        "sKH56SQfKy4": "GCP Cloud SQL Backup and Restore Step-by-Step Guide",
    }
    with Path(args.output).open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["video_id", "current_title", "new_title", "published_at"]
        )
        writer.writeheader()
        for row in rows:
            current = row["current_title"]
            new = manual.get(row["video_id"], optimize_title(current))
            writer.writerow(
                {
                    "video_id": row["video_id"],
                    "current_title": current,
                    "new_title": new,
                    "published_at": row.get("published_at", ""),
                }
            )
    print(f"Wrote title suggestions to {args.output}")


def video_snippet(token: str, video_id: str) -> dict[str, Any]:
    data = request_json(
        "GET",
        f"{API_ROOT}/videos",
        token=token,
        params={"part": "snippet", "id": video_id},
    )
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found or inaccessible: {video_id}")
    return items[0]["snippet"]


def update_title(token: str, video_id: str, new_title: str) -> bool:
    snippet = video_snippet(token, video_id)
    if snippet.get("title") == new_title:
        return False
    snippet["title"] = new_title
    request_json(
        "PUT",
        f"{API_ROOT}/videos",
        token=token,
        params={"part": "snippet"},
        body={"id": video_id, "snippet": snippet},
    )
    return True


def cmd_apply(args: argparse.Namespace) -> None:
    rows = list(csv.DictReader(Path(args.csv).open()))
    rows = [r for r in rows if r["new_title"].strip() and r["new_title"] != r["current_title"]]
    print(f"{'Would update' if args.dry_run else 'Updating'} {len(rows)} videos")
    if args.dry_run:
        for row in rows[: int(args.limit or len(rows))]:
            print(f"{row['video_id']}: {row['current_title']} -> {row['new_title']}")
        return
    token = api_token(args)
    limit = int(args.limit) if args.limit else len(rows)
    updated = 0
    skipped = 0
    for index, row in enumerate(rows[:limit], 1):
        changed = update_title(token, row["video_id"], row["new_title"])
        if changed:
            updated += 1
            print(f"[{index}/{limit}] updated {row['video_id']} -> {row['new_title']}")
        else:
            skipped += 1
            print(f"[{index}/{limit}] skipped {row['video_id']} (already current)")
        time.sleep(float(args.sleep))
    print(f"Done. Updated {updated}; skipped {skipped}.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--credentials", help="OAuth client JSON")
    p.add_argument("--token", default="youtube-token.json")
    sub = p.add_subparsers(required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--output", default="youtube-videos.json")
    exp.set_defaults(func=cmd_export)
    sug = sub.add_parser("suggest")
    sug.add_argument("--input", default="youtube-videos.json")
    sug.add_argument("--output", default="youtube-title-updates.csv")
    sug.set_defaults(func=cmd_suggest)
    app = sub.add_parser("apply")
    app.add_argument("--csv", default="youtube-title-updates.csv")
    app.add_argument("--dry-run", action="store_true")
    app.add_argument("--limit")
    app.add_argument("--sleep", default="0.2")
    app.set_defaults(func=cmd_apply)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
