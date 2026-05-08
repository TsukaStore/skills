---
name: ios-rule-finder
description: Query the blackmatrix7/ios_rule_script repository to find, browse, and resolve URLs for proxy routing rules (Clash, Surge, QuantumultX, Loon, etc.). Use this skill whenever the user mentions routing rules, rule sets, rule providers, domain lists, IP-CIDR rules, or needs to add services like Netflix, OpenAI, YouTube, Steam, or any app/site to their proxy configuration. Trigger even if the user does not explicitly name this repository or say "rule" — any discussion about routing traffic, blocking, or splitting by domain is a signal to use this skill. Also trigger when the user wants to discover what rules exist for a given service or region.
---

# ios-rule-finder

A zero-dependency Python CLI that queries the **blackmatrix7/ios_rule_script** GitHub repository for proxy routing rules.

## What it does

The CLI provides three commands:

- `search` — fuzzy-search service names (e.g. `netflix`, `openai`, `steam`)
- `files` — list all files under a service with their `raw.githubusercontent.com` URLs
- `platforms` — list supported client platforms

## When to use this skill

Use this skill whenever the user needs to:
1. Find routing rules for a service (Netflix, OpenAI, Steam, Apple, Google, etc.)
2. Get a raw rule URL to paste into `rule-providers` or a proxy client config
3. Browse what variants exist for a rule (e.g. `No_Resolve`, `Classical`, `IP`)
4. Discover what rules are available for a category like "media" or "game"

## Installation

The CLI is a single Python file. It requires only the Python 3 standard library.

```
python scripts/rule_find.py <command> [options]
```

## Authentication (optional)

GitHub's anonymous API rate limit is 60 requests per hour. To raise it to 5000, set one of these environment variables before running:

```bash
export IOS_RULE_GITHUB_TOKEN=ghp_xxx
# or
export GITHUB_TOKEN=ghp_xxx
```

## Commands

### 1. Search for services

```bash
python scripts/rule_find.py search <keyword> [--platform Clash] [--limit 20] [--exact]
```

- `--platform`: one of `AdGuard`, `Clash`, `Loon`, `QuantumultX`, `Shadowrocket`, `Surge` (default: `Clash`)
- `--limit`: max number of matches (default: 20)
- `--exact`: require exact case-insensitive match instead of substring
- `--no-cache`: bypass the 1-hour local cache

**Output JSON** (example):

```json
{
  "query": "netflix",
  "platform": "Clash",
  "match_count": 1,
  "total_services_in_platform": 668,
  "results": [
    {
      "service": "Netflix",
      "platform": "Clash",
      "directory_url": "https://github.com/.../tree/master/rule/Clash/Netflix",
      "inferred_default_url": "https://raw.githubusercontent.com/.../master/rule/Clash/Netflix/Netflix.yaml"
    }
  ],
  "next_step": "Use 'files <service>' to confirm available files and pick the right URL."
}
```

### 2. List files for a service

```bash
python scripts/rule_find.py files <service> [--platform Clash] [--filter substring]
```

**Output JSON** (example):

```json
{
  "service": "Netflix",
  "platform": "Clash",
  "directory_url": "...",
  "default_url": "https://raw.githubusercontent.com/.../Netflix/Netflix.yaml",
  "default_file": "Netflix.yaml",
  "file_count": 8,
  "files": [
    {"name": "Netflix.yaml", "url": "...", "type": "domain"},
    {"name": "Netflix_Classical.yaml", "url": "...", "type": "classical"},
    {"name": "Netflix_IP.yaml", "url": "...", "type": "ipcidr"},
    {"name": "Netflix_No_Resolve.yaml", "url": "...", "type": "domain"}
  ]
}
```

**File type heuristics** (`type` field):
- `domain` — standard DOMAIN/DOCMAIN-SUFFIX rules (use with `behavior: domain` in Clash/mihomo)
- `classical` — DOMAIN-KEYWORD / IP-CIDR mix (use with `behavior: classical`)
- `ipcidr` — IP-CIDR / IP-CIDR6 only (use with `behavior: ipcidr`)
- `list` — generic `.list` format
- `text` — plain text
- `readme` — documentation

**Picking a file:**
- For most Clash/mihomo use cases, `Netflix.yaml` (type `domain`) is the right default.
- Use the `_No_Resolve` variant if you want to avoid DNS leakage on IP-CIDR rules.
- Use the `_Classical` variant if you need `DOMAIN-KEYWORD` matching.
- Use `_IP` if you only need IP-CIDR ranges (often combined with a domain rule).

### 3. List platforms

```bash
python scripts/rule_find.py platforms
```

Output: `{"platforms": [...], "default": "Clash"}`

## Typical workflow

1. The user says: "Add Netflix routing rules to my Clash config"
2. Run: `python scripts/rule_find.py search netflix`
3. If the result looks right, run: `python scripts/rule_find.py files Netflix`
4. Present the relevant URL(s) to the user and suggest a `rule-providers` entry:

   ```yaml
   rule-providers:
     Netflix:
       type: http
       behavior: domain
       url: "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Netflix/Netflix.yaml"
       path: ./ruleset/Netflix.yaml
       interval: 86400
   ```

## Caching

Results are cached in `~/.cache/ios-rule-finder/` for 1 hour to avoid burning through GitHub API rate limits. Pass `--no-cache` to force a fresh fetch. Run `cache-clear` to wipe the cache manually.
