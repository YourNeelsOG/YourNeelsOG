#!/usr/bin/env python3
"""Refreshes the "stats" block in config/profile.json from the live GitHub
API. Requires a GH_TOKEN env var (any valid token works — these are public
fields, no special scopes needed). Run this before generate_terminal.py.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "profile.json"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
  }
}
"""


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "terminal-profile-stats-fetcher",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(f"GitHub API error: {payload['errors']}")
    return payload["data"]["user"]


def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN not set, skipping stats refresh", file=sys.stderr)
        sys.exit(0)

    cfg = json.loads(CONFIG_PATH.read_text())
    login = cfg["username"]

    data = fetch(login, token)
    stars = sum(r["stargazerCount"] for r in data["repositories"]["nodes"])

    cfg["stats"] = {
        "repositories": data["repositories"]["totalCount"],
        "contributions": data["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "stars": stars,
        "followers": data["followers"]["totalCount"],
    }
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"updated stats: {cfg['stats']}")


if __name__ == "__main__":
    main()
