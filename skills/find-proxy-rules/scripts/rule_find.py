#!/usr/bin/env python3
"""
ios-rule-finder: Query blackmatrix7/ios_rule_script for proxy routing rules.

All commands output JSON to stdout for programmatic consumption.
Errors go to stderr; exit code is non-zero on failure.

Cache: ~/.cache/ios-rule-finder/ (TTL 1 hour, override with --no-cache).
Auth: set IOS_RULE_GITHUB_TOKEN or GITHUB_TOKEN to lift the 60 req/hr anonymous limit.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "blackmatrix7/ios_rule_script"
BRANCH = "master"
PLATFORMS = ["AdGuard", "Clash", "Loon", "QuantumultX", "Shadowrocket", "Surge"]
DEFAULT_PLATFORM = "Clash"
CACHE_DIR = Path.home() / ".cache" / "ios-rule-finder"
CACHE_TTL_SECONDS = 3600

API_BASE = "https://api.github.com"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
TREE_URL = f"https://github.com/{REPO}/tree/{BRANCH}"


def _gh_request(api_path: str) -> dict | list:
    url = f"{API_BASE}/repos/{REPO}/{api_path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("IOS_RULE_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        if e.code == 403 and "rate limit" in body.lower():
            return {
                "_error": "rate_limited",
                "_hint": "Anonymous GitHub API allows 60 req/hr. Set IOS_RULE_GITHUB_TOKEN or GITHUB_TOKEN env var to raise the limit to 5000 req/hr.",
            }
        if e.code == 404:
            return {"_error": "not_found", "_url": url}
        return {"_error": f"http_{e.code}", "_url": url, "_body": body[:200]}
    except urllib.error.URLError as e:
        return {"_error": "network", "_reason": str(e.reason)}


def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", key)
    return CACHE_DIR / f"{safe}.json"


def _read_cache(key: str) -> object | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(key: str, data: object) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(json.dumps(data), encoding="utf-8")


def list_services(platform: str, no_cache: bool = False) -> list[str] | dict:
    key = f"services_{platform}"
    if not no_cache:
        cached = _read_cache(key)
        if cached is not None:
            return cached
    data = _gh_request(f"contents/rule/{platform}?ref={BRANCH}")
    if isinstance(data, dict) and "_error" in data:
        return data
    if not isinstance(data, list):
        return {"_error": "unexpected_response"}
    services = sorted(item["name"] for item in data if item.get("type") == "dir")
    _write_cache(key, services)
    return services


def list_files(platform: str, service: str, no_cache: bool = False) -> list[str] | dict:
    key = f"files_{platform}_{service}"
    if not no_cache:
        cached = _read_cache(key)
        if cached is not None:
            return cached
    data = _gh_request(f"contents/rule/{platform}/{service}?ref={BRANCH}")
    if isinstance(data, dict) and "_error" in data:
        return data
    if not isinstance(data, list):
        return {"_error": "unexpected_response"}
    files = sorted(item["name"] for item in data if item.get("type") == "file")
    _write_cache(key, files)
    return files


def raw_url(platform: str, service: str, filename: str) -> str:
    return f"{RAW_BASE}/rule/{platform}/{service}/{filename}"


def _classify_file(name: str) -> str:
    """Heuristic classification for downstream consumers (mihomo behavior, etc.)."""
    lower = name.lower()
    if name.endswith(".yaml"):
        if "_ip" in lower:
            return "ipcidr"
        if "_classical" in lower:
            return "classical"
        return "domain"
    if name.endswith(".list"):
        return "list"
    if name.endswith(".txt"):
        return "text"
    if lower == "readme.md":
        return "readme"
    return "other"


def _pick_default_file(files: list[str], service: str, platform: str) -> str | None:
    """Pick the most generally useful single file for the service.

    Preference (Clash): plain `<Service>.yaml` (rule-providers compatible).
    Falls back to any .yaml, then .list, then .txt.
    """
    if platform in ("Clash", "Loon", "Stash"):
        plain_yaml = f"{service}.yaml"
        if plain_yaml in files:
            return plain_yaml
        for f in files:
            if f.endswith(".yaml") and "_no_resolve" not in f.lower() and "_ip" not in f.lower():
                return f
        for f in files:
            if f.endswith(".yaml"):
                return f
    plain_list = f"{service}.list"
    if plain_list in files:
        return plain_list
    for ext in (".yaml", ".list", ".txt"):
        for f in files:
            if f.endswith(ext) and not f.lower().startswith("readme"):
                return f
    return None


def _emit(payload: object, pretty: bool) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if pretty else None)
    sys.stdout.write("\n")


def _bail(payload: dict, pretty: bool) -> None:
    _emit(payload, pretty)
    sys.exit(1)


def cmd_search(args) -> None:
    services = list_services(args.platform, args.no_cache)
    if isinstance(services, dict):
        _bail(services, args.pretty)

    q = args.query.lower()
    if args.exact:
        matches = [s for s in services if s.lower() == q]
    else:
        matches = [s for s in services if q in s.lower()]
    matches = matches[: args.limit]

    results = []
    for svc in matches:
        results.append({
            "service": svc,
            "platform": args.platform,
            "directory_url": f"{TREE_URL}/rule/{args.platform}/{svc}",
            "inferred_default_url": raw_url(args.platform, svc, f"{svc}.yaml" if args.platform in ("Clash", "Loon", "Stash") else f"{svc}.list"),
        })

    _emit({
        "query": args.query,
        "platform": args.platform,
        "match_count": len(results),
        "total_services_in_platform": len(services),
        "results": results,
        "next_step": "Use 'files <service>' to confirm available files and pick the right URL.",
    }, args.pretty)


def cmd_files(args) -> None:
    files = list_files(args.platform, args.service, args.no_cache)
    if isinstance(files, dict):
        _bail(files, args.pretty)

    filtered = files
    if args.filter:
        f = args.filter.lower()
        filtered = [name for name in files if f in name.lower()]

    file_objs = [
        {
            "name": name,
            "url": raw_url(args.platform, args.service, name),
            "type": _classify_file(name),
        }
        for name in filtered
    ]

    default = _pick_default_file(files, args.service, args.platform)

    _emit({
        "service": args.service,
        "platform": args.platform,
        "directory_url": f"{TREE_URL}/rule/{args.platform}/{args.service}",
        "default_url": raw_url(args.platform, args.service, default) if default else None,
        "default_file": default,
        "file_count": len(file_objs),
        "files": file_objs,
    }, args.pretty)


def cmd_platforms(args) -> None:
    _emit({
        "platforms": PLATFORMS,
        "default": DEFAULT_PLATFORM,
    }, args.pretty)


def cmd_cache_clear(args) -> None:
    cleared = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
            cleared += 1
    _emit({"status": "ok", "cache_dir": str(CACHE_DIR), "files_cleared": cleared}, args.pretty)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rule-find",
        description="Query blackmatrix7/ios_rule_script for proxy routing rules. JSON output.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Fuzzy-search service names within a platform.")
    p_search.add_argument("query", help="Keyword (case-insensitive substring match).")
    p_search.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORMS,
                          help=f"Target platform (default: {DEFAULT_PLATFORM}).")
    p_search.add_argument("--limit", type=int, default=20, help="Max matches to return (default 20).")
    p_search.add_argument("--exact", action="store_true", help="Require exact (case-insensitive) match.")
    p_search.add_argument("--no-cache", action="store_true", help="Bypass local cache and re-fetch.")
    p_search.set_defaults(func=cmd_search)

    p_files = sub.add_parser("files", help="List all files (with raw URLs) under a specific service.")
    p_files.add_argument("service", help="Exact service directory name (case-sensitive on GitHub).")
    p_files.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORMS,
                         help=f"Target platform (default: {DEFAULT_PLATFORM}).")
    p_files.add_argument("--filter", help="Substring filter for filenames (e.g. 'No_Resolve').")
    p_files.add_argument("--no-cache", action="store_true", help="Bypass local cache.")
    p_files.set_defaults(func=cmd_files)

    p_plat = sub.add_parser("platforms", help="List all supported client platforms.")
    p_plat.set_defaults(func=cmd_platforms)

    p_cc = sub.add_parser("cache-clear", help="Clear the local cache directory.")
    p_cc.set_defaults(func=cmd_cache_clear)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
