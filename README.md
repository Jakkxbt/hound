# HOUND

Email OSINT tool. Checks 27+ platforms for accounts registered to an email address.

## Install

```bash
pip install -r requirements.txt
pip install -e .
```

## CLI

```bash
# Check all platforms
hound target@example.com

# Show only found accounts
hound target@example.com --found-only

# Check specific platforms
hound target@example.com --only github --only spotify --only discord

# JSON output
hound target@example.com --json

# Adjust timeout and concurrency
hound target@example.com --timeout 15 --concurrency 5
```

## Web App

```bash
python -m hound.web
# Open http://localhost:5100
```

## Platforms

Duolingo, GitHub, GitLab, Spotify, Twitter/X, Instagram, Discord, Reddit, Tumblr, Patreon, Dropbox, Pinterest, WordPress.com, Bugcrowd, Roblox, Twitch, Adobe, ProtonMail, LastPass, Fiverr, Airbnb, Kickstarter, eBay, Samsung, Linktree, Snapchat, Stack Overflow

## Adding Sites

Add a new async function to `hound/modules.py`:

```python
async def check_mysite(client: httpx.AsyncClient, email: str) -> dict:
    try:
        r = await client.post("https://mysite.com/forgot", data={"email": email}, ...)
        found = "sent" in r.text.lower()
        return _r("MySite", "https://mysite.com", found)
    except Exception as e:
        return _r("MySite", "https://mysite.com", None, str(e))
```

Then add it to `ALL_MODULES` at the bottom of the file.
