#!/usr/bin/env python3
"""
One-shot Linear session snapshot for the use-linear skill.

Reads API key from repo-root .mcp.json (Authorization: Bearer ...) or LINEAR_API_KEY.
Emits compact pipe-delimited sections to stdout. Exits 0 always; on failure prints
# bootstrap: <reason> so the skill can fall back to MCP list_* tools.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LINEAR_URL = "https://api.linear.app/graphql"
ISSUE_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")
LINEAR_TRAILER_RE = re.compile(
    r"^\s*Linear:\s*([A-Z][A-Z0-9]*-\d+(?:\s*,\s*[A-Z][A-Z0-9]*-\d+)*)",
    re.IGNORECASE | re.MULTILINE,
)


def repo_root() -> Path:
    p = Path(__file__).resolve()
    # skills/use-linear/scripts/bootstrap.py -> parents[3] = repo root
    return p.parents[3]


def read_token() -> str | None:
    key = os.environ.get("LINEAR_API_KEY") or os.environ.get("LINEAR_TOKEN")
    if key:
        return key.strip()
    mcp = repo_root() / ".mcp.json"
    if not mcp.is_file():
        return None
    try:
        raw = mcp.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'Authorization:\s*Bearer\s+(\S+)', raw, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip('",')
    try:
        data = json.loads(raw)
        for srv in data.get("mcpServers", {}).values():
            args = srv.get("args") or []
            for i, a in enumerate(args):
                if a == "--header" and i + 1 < len(args):
                    hm = re.match(
                        r"Authorization:\s*Bearer\s+(\S+)", args[i + 1], re.I
                    )
                    if hm:
                        return hm.group(1).strip()
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


def read_default_team() -> str | None:
    ctx = repo_root() / ".agents" / "use-linear" / "context.yaml"
    if not ctx.is_file():
        return None
    try:
        text = ctx.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^team:\s*(.+)$", text, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    if v.startswith("["):
        return None
    return v.strip("\"'")


def pipe_escape(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).replace("|", " ").replace("\n", " ").strip()


def git_hints(root: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and (b := r.stdout.strip()):
            out.append(("branch", b))
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-n",
                "20",
                "--pretty=%B",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if r.returncode == 0 and r.stdout:
            trailers = LINEAR_TRAILER_RE.findall(r.stdout)
            if trailers:
                ids = []
                for t in trailers[:3]:
                    ids.extend(
                        x.strip() for x in re.split(r",\s*", t) if x.strip()
                    )
                seen: set[str] = set()
                for iid in ids:
                    if iid.upper() not in seen:
                        seen.add(iid.upper())
                        out.append(("linear_trailer", iid))
                        if len(seen) >= 3:
                            break
            else:
                for m in ISSUE_ID_RE.finditer(r.stdout):
                    out.append(("issue_id_hint", m.group(1)))
                    if len(out) >= 5:
                        break
    except (OSError, subprocess.TimeoutExpired):
        pass
    # de-dupe keys keeping order
    seen_k: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for k, v in out:
        tag = f"{k}:{v}"
        if tag not in seen_k:
            seen_k.add(tag)
            deduped.append((k, v))
    return deduped[:8]


def authorization_value(token: str) -> str:
    """
    Personal API keys (lin_api_...) must be sent without a Bearer prefix.
    OAuth access tokens use Bearer. See Linear GraphQL auth docs.
    """
    t = token.strip()
    if t.startswith("lin_api_") or t.startswith("lin_oauth_"):
        return t
    return f"Bearer {t}"


def graphql(token: str, query: str) -> dict:
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        LINEAR_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": authorization_value(token),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


QUERY = """
query Bootstrap {
  viewer {
    displayName
    email
    assignedIssues(
      first: 50
      filter: { state: { type: { nin: ["completed", "canceled"] } } }
    ) {
      nodes {
        identifier
        title
        state { name type }
        team { key }
        project { name }
        cycle { name endsAt }
      }
    }
  }
  teams(first: 20) {
    nodes {
      key
      cycles(first: 1, filter: { isActive: { eq: true } }) {
        nodes {
          name
          endsAt
        }
      }
      states {
        nodes {
          name
          type
        }
      }
    }
  }
  projects(first: 25, filter: { state: { in: ["started", "planned", "paused"] } }) {
    nodes {
      name
      state
      targetDate
    }
  }
}
"""


def main() -> int:
    root = repo_root()
    token = read_token()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    default_team = read_default_team()

    if not token:
        print("# bootstrap: no token (.mcp.json Authorization Bearer or LINEAR_API_KEY)")
        return 0

    try:
        data = graphql(token, QUERY)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            parsed = json.loads(err_body)
            msgs = parsed.get("errors") or []
            m0 = (msgs[0] or {}).get("message") if msgs else err_body[:200]
            print(f"# bootstrap: http {e.code} {m0}")
        except (json.JSONDecodeError, OSError, TypeError, IndexError):
            print(f"# bootstrap: http {e.code}")
        return 0
    except urllib.error.URLError as e:
        print(f"# bootstrap: network {e.reason!s}")
        return 0
    except (json.JSONDecodeError, OSError) as e:
        print(f"# bootstrap: {e!s}")
        return 0

    errs = data.get("errors")
    if errs:
        msgs = "; ".join(str(e.get("message", e)) for e in errs[:3])
        print(f"# bootstrap: graphql {msgs}")
        # partial data may still exist
    payload = data.get("data") or {}
    viewer = payload.get("viewer") or {}

    v_email = pipe_escape(viewer.get("email"))
    v_name = pipe_escape(viewer.get("displayName"))
    team_hint = pipe_escape(default_team) or ""
    print(f"# linear snapshot {ts} | viewer: {v_email} | name: {v_name} | default_team: {team_hint}")

    issues = (viewer.get("assignedIssues") or {}).get("nodes") or []
    print("## issues (id|state|title|project|cycle)")
    for issue in issues:
        ident = pipe_escape(issue.get("identifier"))
        st = pipe_escape((issue.get("state") or {}).get("name"))
        title = pipe_escape(issue.get("title"))
        proj = pipe_escape((issue.get("project") or {}).get("name"))
        cyc = issue.get("cycle") or {}
        cyc_name = pipe_escape(cyc.get("name"))
        print(f"{ident}|{st}|{title}|{proj}|{cyc_name}")

    teams = (payload.get("teams") or {}).get("nodes") or []
    print("## cycles (team|name|ends)")
    for team in teams:
        key = pipe_escape(team.get("key"))
        cnodes = (team.get("cycles") or {}).get("nodes") or []
        if not cnodes:
            print(f"{key}||")
            continue
        c0 = cnodes[0]
        ends = c0.get("endsAt") or ""
        if ends and "T" in str(ends):
            ends = str(ends).split("T")[0]
        print(f"{key}|{pipe_escape(c0.get('name'))}|{pipe_escape(str(ends))}")

    print("## states (team|state_name|state_type)")
    for team in teams:
        key = pipe_escape(team.get("key"))
        snodes = (team.get("states") or {}).get("nodes") or []
        if not snodes:
            print(f"{key}||")
            continue
        for st in snodes[:12]:
            print(
                f"{key}|{pipe_escape(st.get('name'))}|{pipe_escape(st.get('type'))}"
            )

    projects = (payload.get("projects") or {}).get("nodes") or []
    print("## projects (name|state|target)")
    for pr in projects:
        print(
            f"{pipe_escape(pr.get('name'))}|{pipe_escape(pr.get('state'))}|{pipe_escape(str(pr.get('targetDate') or ''))}"
        )

    print("## git (key|value)")
    for k, v in git_hints(root):
        print(f"{k}|{pipe_escape(v)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
