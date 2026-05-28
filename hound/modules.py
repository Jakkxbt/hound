"""
Site check modules. Each module is an async function:
    async def check_<site>(client, email) -> dict

Return dict keys:
    name  : str   display name
    url   : str   profile/site URL
    found : bool | None  (None = rate-limited / unknown)
    error : str | None
"""
import re
import asyncio
import httpx

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def _r(name, url, found, error=None):
    return {"name": name, "url": url, "found": found, "error": error}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csrf_from_html(html: str, field: str = "csrf-token") -> str:
    """Extract CSRF meta tag or input value from HTML."""
    m = re.search(rf'<meta[^>]+name=["\']?{field}["\']?[^>]+content=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    m = re.search(rf'name=["\']?{field}["\']?[^>]+value=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    m = re.search(rf'value=["\']([^"\']+)["\'][^>]+name=["\']?{field}["\']?', html)
    if m:
        return m.group(1)
    return ""


# ── Modules ───────────────────────────────────────────────────────────────────

async def check_duolingo(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Duolingo", "https://www.duolingo.com"
    try:
        r = await client.get(
            f"https://www.duolingo.com/2017-06-30/users",
            params={"email": email, "fields": "email"},
            headers=HEADERS, timeout=10
        )
        data = r.json()
        found = bool(data.get("users"))
        return _r(name, url, found)
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_github(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "GitHub", "https://github.com"
    try:
        g = await client.get("https://github.com/password_reset", headers=HEADERS, timeout=10)
        token = _csrf_from_html(g.text, "csrf-token")
        if not token:
            m = re.search(r'name="authenticity_token"\s+value="([^"]+)"', g.text)
            token = m.group(1) if m else ""
        r = await client.post(
            "https://github.com/password_reset",
            data={"authenticity_token": token, "email": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://github.com/password_reset"},
            timeout=10
        )
        text = r.text.lower()
        if "check your email" in text or "we'll send" in text or "sent you an email" in text:
            return _r(name, url, True)
        if "no user with" in text or "can't find" in text or "couldn't find" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_spotify(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Spotify", "https://www.spotify.com"
    try:
        r = await client.get(
            "https://spclient.wg.spotify.com/signup/public/v1/account",
            params={"validate": "1", "email": email},
            headers={**HEADERS, "App-Platform": "WebPlayer"},
            timeout=10
        )
        data = r.json()
        status = data.get("status", 0)
        if status == 20:
            return _r(name, url, True)
        if status == 1:
            return _r(name, url, False)
        return _r(name, url, None, f"unknown status {status}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_twitter(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Twitter / X", "https://x.com"
    try:
        r = await client.get(
            "https://api.twitter.com/i/users/email_available.json",
            params={"email": email},
            headers={**HEADERS, "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"},
            timeout=10
        )
        data = r.json()
        # valid=false means it's taken (account exists)
        if "valid" in data:
            return _r(name, url, not data["valid"])
        return _r(name, url, None, "unexpected response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_instagram(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Instagram", "https://www.instagram.com"
    try:
        g = await client.get("https://www.instagram.com/accounts/password/reset/", headers=HEADERS, timeout=10)
        token = ""
        m = re.search(r'"csrf_token":"([^"]+)"', g.text)
        if m:
            token = m.group(1)
        r = await client.post(
            "https://www.instagram.com/api/v1/web/users/lookup/",
            data={"email": email},
            headers={**HEADERS,
                     "X-CSRFToken": token,
                     "X-Instagram-AJAX": "1",
                     "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://www.instagram.com/accounts/password/reset/"},
            timeout=10
        )
        data = r.json()
        if data.get("user_found") is True:
            return _r(name, url, True)
        if data.get("user_found") is False:
            return _r(name, url, False)
        if "email_is_taken" in str(data):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_discord(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Discord", "https://discord.com"
    try:
        r = await client.post(
            "https://discord.com/api/v9/auth/forgot",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://discord.com",
                     "Referer": "https://discord.com/login"},
            timeout=10
        )
        # 200 = email sent (account exists), other = no account or rate limited
        if r.status_code == 200:
            return _r(name, url, True)
        if r.status_code == 400:
            data = r.json()
            if "email" in data:
                return _r(name, url, False)
        if r.status_code == 429:
            return _r(name, url, None, "rate limited")
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_reddit(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Reddit", "https://www.reddit.com"
    try:
        g = await client.get(
            "https://www.reddit.com/login",
            headers=HEADERS, timeout=10
        )
        token = ""
        m = re.search(r'"token":"([^"]+)"', g.text)
        if m:
            token = m.group(1)
        r = await client.post(
            "https://www.reddit.com/api/v1/register/check_username",
            json={"user": email},
            headers={**HEADERS, "Authorization": f"Bearer {token}" if token else "",
                     "Content-Type": "application/json"},
            timeout=10
        )
        # Try forgot password flow instead - more reliable
        r2 = await client.post(
            "https://www.reddit.com/api/forgot_password",
            data={"email": email, "api_type": "json"},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Modhash": ""},
            timeout=10
        )
        data = r2.json()
        errors = data.get("json", {}).get("errors", [])
        if not errors:
            return _r(name, url, True)
        err_str = str(errors).lower()
        if "email" in err_str or "not found" in err_str:
            return _r(name, url, False)
        return _r(name, url, True)  # no errors = email accepted = account exists
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_tumblr(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Tumblr", "https://www.tumblr.com"
    try:
        r = await client.post(
            "https://www.tumblr.com/api/v2/user/check_email",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://www.tumblr.com"},
            timeout=10
        )
        data = r.json()
        if data.get("meta", {}).get("status") == 200:
            return _r(name, url, data.get("response", {}).get("exists", None))
        return _r(name, url, None, "unexpected response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_patreon(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Patreon", "https://www.patreon.com"
    try:
        r = await client.post(
            "https://www.patreon.com/api/auth",
            json={"data": {"type": "user", "attributes": {"email": email, "password": "x"}}},
            params={"include": "null"},
            headers={**HEADERS, "Content-Type": "application/vnd.api+json",
                     "Origin": "https://www.patreon.com"},
            timeout=10
        )
        text = r.text.lower()
        if "incorrect password" in text or "invalid password" in text:
            return _r(name, url, True)
        if "email address is not registered" in text or "no account" in text:
            return _r(name, url, False)
        if r.status_code == 401:
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_dropbox(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Dropbox", "https://www.dropbox.com"
    try:
        r = await client.post(
            "https://www.dropbox.com/forgot_password_ajax",
            data={"email": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.dropbox.com/forgot"},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "ok" or data.get("success"):
            return _r(name, url, True)
        if "no account" in str(data).lower() or data.get("status") == "error":
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_pinterest(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Pinterest", "https://www.pinterest.com"
    try:
        r = await client.post(
            "https://www.pinterest.com/resource/UserPasswordResetResource/create/",
            data={"data": f'{{"options":{{"email":"{email}"}},"context":{{}}}}',
                  "source_url": "/password/reset/", "_pinterest_source_url": "/password/reset/"},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.pinterest.com/password/reset/"},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "success":
            return _r(name, url, True)
        if data.get("status") == "failure":
            msg = str(data.get("message", "")).lower()
            if "not found" in msg or "no account" in msg:
                return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_wordpress(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "WordPress.com", "https://wordpress.com"
    try:
        r = await client.post(
            "https://wordpress.com/wp-login.php",
            params={"action": "lostpassword"},
            data={"user_login": email, "redirect_to": "", "action": "lostpassword"},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://wordpress.com/wp-login.php?action=lostpassword"},
            timeout=10
        )
        text = r.text.lower()
        if "check your email" in text or "we've just sent" in text or "a link has been" in text:
            return _r(name, url, True)
        if "no user is registered" in text or "there is no user" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_hackerone(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "HackerOne", "https://hackerone.com"
    try:
        g = await client.get("https://hackerone.com/users/password/new", headers=HEADERS, timeout=10)
        token = _csrf_from_html(g.text, "csrf-token")
        r = await client.post(
            "https://hackerone.com/users/password",
            data={"user[email]": email, "authenticity_token": token},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://hackerone.com/users/password/new"},
            timeout=10
        )
        text = r.text.lower()
        if "if your email address exists" in text or "email has been sent" in text or r.status_code in (200, 302):
            # H1 always says "if your email exists" for security — try to detect differently
            return _r(name, url, None, "H1 obscures result for security")
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_bugcrowd(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Bugcrowd", "https://bugcrowd.com"
    try:
        g = await client.get("https://bugcrowd.com/user/password/new", headers=HEADERS, timeout=10)
        token = _csrf_from_html(g.text, "csrf-token")
        r = await client.post(
            "https://bugcrowd.com/user/password",
            data={"user[email]": email, "authenticity_token": token},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://bugcrowd.com/user/password/new"},
            timeout=10
        )
        text = r.text.lower()
        if "you will receive an email" in text or "instructions" in text:
            return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_roblox(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Roblox", "https://www.roblox.com"
    try:
        r = await client.post(
            "https://auth.roblox.com/v1/usernames/validate",
            json={"username": email, "birthday": "1990-01-01"},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://www.roblox.com"},
            timeout=10
        )
        # Try email check via signup
        r2 = await client.post(
            "https://auth.roblox.com/v2/signup",
            json={"username": "TestUser99x", "password": "TestPass99!", "gender": 1,
                  "birthday": "1990-01-01T00:00:00.000Z", "email": email, "isTosAgreementBoxChecked": True},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://www.roblox.com",
                     "Referer": "https://www.roblox.com/"},
            timeout=10
        )
        text = r2.text.lower()
        if "email already in use" in text or "email is taken" in text or "email_already_used" in text:
            return _r(name, url, True)
        if "account" in text and ("already" in text or "taken" in text):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_twitch(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Twitch", "https://www.twitch.tv"
    try:
        r = await client.get(
            "https://passport.twitch.tv/register",
            params={"email": email},
            headers={**HEADERS, "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko"},
            timeout=10
        )
        # Try registration check endpoint
        r2 = await client.post(
            "https://passport.twitch.tv/register/check",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
                     "Origin": "https://www.twitch.tv"},
            timeout=10
        )
        text = r2.text.lower()
        if "taken" in text or "already" in text or r2.status_code == 409:
            return _r(name, url, True)
        if r2.status_code == 200 and "available" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_adobe(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Adobe", "https://www.adobe.com"
    try:
        r = await client.get(
            "https://auth.services.adobe.com/en_US/index.html",
            headers=HEADERS, timeout=10
        )
        r2 = await client.post(
            "https://ims-na1.adobelogin.com/ims/check_token/v2",
            json={"email": email, "client_id": "IMSBrowser"},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://auth.services.adobe.com"},
            timeout=10
        )
        text = r2.text.lower()
        if r2.status_code == 200:
            data = r2.json()
            if data.get("result") == "not_found" or "notFound" in str(data):
                return _r(name, url, False)
            if data.get("result") == "found":
                return _r(name, url, True)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_protonmail(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "ProtonMail", "https://proton.me"
    try:
        r = await client.post(
            "https://account.proton.me/api/core/v4/users/available",
            json={"Email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "X-Pm-Apiversion": "3",
                     "Origin": "https://account.proton.me"},
            timeout=10
        )
        data = r.json()
        code = data.get("Code", 0)
        if code == 1000:
            return _r(name, url, False)  # available = not taken
        if code in (2500, 12011, 12060):
            return _r(name, url, True)   # not available = taken
        return _r(name, url, None, f"code {code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_lastpass(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "LastPass", "https://www.lastpass.com"
    try:
        r = await client.post(
            "https://lastpass.com/ajax/forgotpassword_email.php",
            data={"username": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://lastpass.com/forgot.php"},
            timeout=10
        )
        text = r.text.lower()
        if "sent" in text or "check your email" in text or r.status_code == 200:
            return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_fiverr(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Fiverr", "https://www.fiverr.com"
    try:
        r = await client.post(
            "https://www.fiverr.com/login_/forgot_password",
            data={"email_or_username": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.fiverr.com/login"},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "success" or data.get("success"):
            return _r(name, url, True)
        text = str(data).lower()
        if "not found" in text or "no user" in text or "doesn't exist" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_airbnb(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Airbnb", "https://www.airbnb.com"
    try:
        r = await client.post(
            "https://www.airbnb.com/api/v2/authentications",
            json={"email": email, "type": "email"},
            params={"_format": "for_auth_modal", "key": "d306zoyjsyarp7ifhu67rjxn52tv0t20"},
            headers={**HEADERS, "Content-Type": "application/json",
                     "X-Airbnb-Api-Key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",
                     "Origin": "https://www.airbnb.com"},
            timeout=10
        )
        data = r.json()
        if data.get("login") or data.get("user"):
            return _r(name, url, True)
        if data.get("signup"):
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_kickstarter(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Kickstarter", "https://www.kickstarter.com"
    try:
        r = await client.post(
            "https://www.kickstarter.com/forgot",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "X-Requested-With": "XMLHttpRequest",
                     "Origin": "https://www.kickstarter.com"},
            timeout=10
        )
        text = r.text.lower()
        if "if there's a kickstarter account" in text or "sent" in text:
            return _r(name, url, True)
        if "not found" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_ebay(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "eBay", "https://www.ebay.com"
    try:
        r = await client.post(
            "https://signin.ebay.com/ws/eBayISAPI.dll",
            data={"siteid": "0", "co_partnerId": "0", "UsingSSL": "1", "ru": "",
                  "userid": email, "pageName": "SignIn", "pp": "", "pa1": "", "pa2": "",
                  "pa3": "", "i1": "-1", "inputIMEINumber": "", "signbttn": "Sign+in"},
            params={"SignIn": ""},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn"},
            timeout=10
        )
        text = r.text.lower()
        if "the email address or username you entered" in text and "doesn't match" in text:
            return _r(name, url, True)   # email recognised, password wrong
        if "we don't recognise" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_samsung(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Samsung", "https://account.samsung.com"
    try:
        r = await client.post(
            "https://account.samsung.com/membership/checkEmailAddrV2.do",
            data={"emailAddress": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest"},
            timeout=10
        )
        data = r.json()
        result = data.get("resultCode", "")
        if result == "1":
            return _r(name, url, True)
        if result == "0":
            return _r(name, url, False)
        return _r(name, url, None, f"resultCode={result}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_gitlab(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "GitLab", "https://gitlab.com"
    try:
        g = await client.get("https://gitlab.com/users/password/new", headers=HEADERS, timeout=10)
        token = _csrf_from_html(g.text, "csrf-token")
        r = await client.post(
            "https://gitlab.com/users/password",
            data={"user[email]": email, "authenticity_token": token},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://gitlab.com/users/password/new"},
            timeout=10
        )
        text = r.text.lower()
        if "if your email address exists" in text or "sent you an email" in text:
            return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        # GitLab redirects on success
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_linktree(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Linktree", "https://linktr.ee"
    try:
        r = await client.post(
            "https://api.linktr.ee/api/auth/forgot-password",
            json={"email": email},
            headers={**HEADERS, "Content-Type": "application/json",
                     "Origin": "https://linktr.ee"},
            timeout=10
        )
        if r.status_code == 200:
            return _r(name, url, True)
        if r.status_code == 404:
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_snapchat(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Snapchat", "https://www.snapchat.com"
    try:
        r = await client.post(
            "https://accounts.snapchat.com/accounts/forgot_password/send_code",
            data={"email": email, "source": "web"},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://accounts.snapchat.com",
                     "Referer": "https://accounts.snapchat.com/accounts/password_recovery_email"},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "OK" or data.get("status_code") == 200:
            return _r(name, url, True)
        if "not found" in str(data).lower() or data.get("status") == "ERROR":
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_stackoverflow(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Stack Overflow", "https://stackoverflow.com"
    try:
        r = await client.post(
            "https://stackoverflow.com/users/account-recovery",
            data={"Email": email},
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://stackoverflow.com/users/account-recovery"},
            timeout=10
        )
        text = r.text.lower()
        if "if there is an account" in text or "sent you an email" in text:
            return _r(name, url, True)
        if "not find" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous response")
    except Exception as e:
        return _r(name, url, None, str(e))


# Registry — all available modules
ALL_MODULES = [
    check_duolingo,
    check_github,
    check_gitlab,
    check_spotify,
    check_twitter,
    check_instagram,
    check_discord,
    check_reddit,
    check_tumblr,
    check_patreon,
    check_dropbox,
    check_pinterest,
    check_wordpress,
    check_bugcrowd,
    check_roblox,
    check_twitch,
    check_adobe,
    check_protonmail,
    check_lastpass,
    check_fiverr,
    check_airbnb,
    check_kickstarter,
    check_ebay,
    check_samsung,
    check_linktree,
    check_snapchat,
    check_stackoverflow,
]

SITE_NAMES = {f.__name__.replace("check_", ""): f for f in ALL_MODULES}
