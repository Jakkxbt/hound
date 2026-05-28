# HOUND — Operational Guide
**Email OSINT | Account Discovery**
*CobraSEC Internal — GhostWire-0*

---

## What It Does

HOUND takes an email address and checks 27+ platforms to find which ones have an account registered to it. Runs all checks concurrently — full scan completes in ~10–15 seconds.

Two modes:
- **CLI** — terminal tool, coloured output, JSON export
- **Web app** — browser UI, live streaming results as they come in

---

## Installation

```bash
# Clone
git clone https://github.com/Jakkxbt/hound
cd hound

# Install (Kali / system Python)
pip3 install -r requirements.txt --break-system-packages
pip3 install -e . --break-system-packages
```

Once installed, `hound` is available system-wide as a command.

---

## CLI Usage

### Basic scan — all platforms
```bash
hound target@example.com
```
Checks all 27 platforms. Found accounts show at the top in green.

---

### Found accounts only
```bash
hound target@example.com --found-only
# or
hound target@example.com -f
```
Hides "not found" and "unknown" — clean output showing only hits.

---

### Check specific platforms
```bash
hound target@example.com --only github
hound target@example.com --only github --only discord --only spotify
# or short form
hound target@example.com -o github -o discord -o spotify
```
Site names (lowercase, no spaces):
`duolingo` `github` `gitlab` `spotify` `twitter` `instagram` `discord`
`reddit` `tumblr` `patreon` `dropbox` `pinterest` `wordpress` `bugcrowd`
`roblox` `twitch` `adobe` `protonmail` `lastpass` `fiverr` `airbnb`
`kickstarter` `ebay` `samsung` `linktree` `snapchat` `stackoverflow`

---

### JSON output
```bash
hound target@example.com --json
hound target@example.com --json > results.json
hound target@example.com --json | jq '.[] | select(.found == true)'
```
Output format per entry:
```json
{
  "name": "GitHub",
  "url": "https://github.com",
  "found": true,
  "error": null
}
```
`found` values:
- `true` — account confirmed
- `false` — no account found
- `null` — rate limited, ambiguous response, or site unreachable

---

### Adjust timeout and concurrency
```bash
# Slower sites — increase timeout (default: 12s)
hound target@example.com --timeout 20

# Reduce concurrency if hitting rate limits (default: 10)
hound target@example.com --concurrency 5

# Both together
hound target@example.com -t 20 -c 5
```

---

### Combine flags
```bash
# Found only, JSON, specific sites
hound target@example.com -f --json -o github -o discord -o reddit

# Full scan, found only, save to file
hound target@example.com -f --json > ~/bughunt/target/recon/emails.json

# Slow/careful scan — lower concurrency, longer timeout
hound target@example.com -c 3 -t 20
```

---

## Web App

```bash
python3 -m hound.web
```
Opens on **http://localhost:5100**

- Enter email → click HUNT
- Results stream in live as each check completes
- Found accounts bubble to the top (green)
- Unknown/ambiguous shown in amber
- Click any URL to open the site directly

To run on a different port:
```bash
python3 -c "from hound.web import run; run(port=8080)"
```

---

## Result Status Guide

| Status | Meaning |
|--------|---------|
| `● FOUND` (green) | Account confirmed on that platform |
| `○ not found` (grey) | No account for that email |
| `? ambiguous` (amber) | Site responded but result unclear — rate limit, CAPTCHA, or changed API |
| `? error: ...` (amber) | Network error, timeout, or connection refused |

**Note on ambiguous results:** Some platforms (HackerOne, Discord) obscure their responses for security — they return the same message whether an account exists or not. These will always show as unknown.

---

## Adding New Sites

Edit `hound/modules.py` — add one async function:

```python
async def check_mysite(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "MySite", "https://mysite.com"
    try:
        r = await client.post(
            "https://mysite.com/api/forgot-password",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=10
        )
        text = r.text.lower()
        if "email sent" in text or "check your inbox" in text:
            return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))
```

Then add it to `ALL_MODULES` at the bottom of the file:
```python
ALL_MODULES = [
    ...
    check_mysite,  # ← add here
]
```

The CLI `--only` flag picks it up automatically using the function name:
`check_mysite` → `--only mysite`

---

## Detection Methods Used

| Method | How it works |
|--------|-------------|
| **Forgot password** | POST email to reset endpoint — "check your email" = found, "no account" = not found |
| **Registration check** | POST to signup — "email already taken" = found |
| **JSON API** | Direct availability endpoint (e.g. Duolingo, Spotify, ProtonMail) |
| **CSRF + forgot** | GET page → extract token → POST (GitHub, GitLab, Bugcrowd) |

---

## Files

```
hound/
├── hound/
│   ├── __init__.py     version
│   ├── cli.py          CLI entry point (click + rich)
│   ├── engine.py       async runner (httpx + asyncio)
│   ├── modules.py      all 27 site check functions
│   └── web.py          Flask web app + frontend
├── pyproject.toml      package config
├── requirements.txt    dependencies
└── README.md           GitHub readme
```

---

## Repo

**https://github.com/Jakkxbt/hound**

---

*HOUND — CobraSEC*
*WDNL.*
