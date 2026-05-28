"""
Site check modules.
Each module: async def check_<site>(client, email) -> dict
Return: {name, url, found: bool|None, error: str|None}
"""
import re
import httpx

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "*/*"}


def _r(name, url, found, error=None):
    return {"name": name, "url": url, "found": found, "error": error}


def _json(r):
    """Safe JSON parse — returns {} on failure."""
    try:
        return r.json()
    except Exception:
        return {}


def _csrf(html: str, *fields) -> str:
    """Try multiple CSRF field names, return first match."""
    names = fields or ("csrf-token", "authenticity_token", "_token", "csrfmiddlewaretoken")
    for field in names:
        m = re.search(rf'name=["\']?{re.escape(field)}["\']?\s+[^>]*value=["\']([^"\']+)', html)
        if m:
            return m.group(1)
        m = re.search(rf'value=["\']([^"\']+)["\']\s+[^>]*name=["\']?{re.escape(field)}["\']?', html)
        if m:
            return m.group(1)
        m = re.search(rf'<meta[^>]+name=["\']?{re.escape(field)}["\']?[^>]+content=["\']([^"\']+)', html)
        if m:
            return m.group(1)
    return ""


# ── Modules ───────────────────────────────────────────────────────────────────

async def check_duolingo(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Duolingo", "https://www.duolingo.com"
    try:
        r = await client.get(
            "https://www.duolingo.com/2017-06-30/users",
            params={"email": email, "fields": "email"},
            headers=HEADERS, timeout=10
        )
        data = _json(r)
        return _r(name, url, bool(data.get("users")))
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_github(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "GitHub", "https://github.com"
    try:
        g = await client.get("https://github.com/password_reset", headers=HEADERS, timeout=10)
        token = _csrf(g.text, "authenticity_token")
        if not token:
            # fallback: look for any hidden input with token-like value
            m = re.search(r'<input[^>]+type="hidden"[^>]+name="authenticity_token"[^>]+value="([^"]+)"', g.text)
            if m:
                token = m.group(1)
        r = await client.post(
            "https://github.com/password_reset",
            data={"authenticity_token": token, "email": email},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://github.com/password_reset",
                     "Origin": "https://github.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["check your email", "we'll send", "sent you an email", "if your email"]):
            return _r(name, url, True)
        if any(x in text for x in ["no user with", "can't find", "couldn't find", "not found"]):
            return _r(name, url, False)
        # GitHub often returns 200 with a flash message — check for success redirect
        if r.status_code in (302, 303) or "password_reset" not in r.url.path:
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_gitlab(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "GitLab", "https://gitlab.com"
    try:
        g = await client.get("https://gitlab.com/users/password/new", headers=HEADERS, timeout=10)
        token = _csrf(g.text, "authenticity_token")
        r = await client.post(
            "https://gitlab.com/users/password",
            data={"user[email]": email, "authenticity_token": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://gitlab.com/users/password/new",
                     "Origin": "https://gitlab.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["sent you an email", "if your email address exists", "instructions"]):
            return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        # GitLab redirects to sign_in on success
        if r.status_code in (302, 303):
            loc = r.headers.get("location", "")
            if "sign_in" in loc or "users/sign_in" in loc:
                return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
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
        data = _json(r)
        status = data.get("status", -1)
        if status == 20:
            return _r(name, url, True)
        if status == 1:
            return _r(name, url, False)
        return _r(name, url, None, f"status {status}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_twitter(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Twitter / X", "https://x.com"
    try:
        r = await client.get(
            "https://api.twitter.com/i/users/email_available.json",
            params={"email": email},
            headers={**HEADERS,
                     "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"},
            timeout=10
        )
        data = _json(r)
        if "valid" in data:
            return _r(name, url, not data["valid"])
        return _r(name, url, None, "unexpected response")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_instagram(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Instagram", "https://www.instagram.com"
    try:
        # Get the page to extract CSRF token from cookie
        g = await client.get(
            "https://www.instagram.com/accounts/password/reset/",
            headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=10
        )
        # Instagram puts CSRF in cookie and meta tag
        token = ""
        m = re.search(r'"csrf_token"\s*:\s*"([^"]+)"', g.text)
        if m:
            token = m.group(1)
        if not token:
            token = g.cookies.get("csrftoken", "")

        r = await client.post(
            "https://www.instagram.com/api/v1/web/accounts/account_recovery_send_ajax/",
            data={"email_or_username": email},
            headers={**HEADERS,
                     "X-CSRFToken": token,
                     "X-Instagram-AJAX": "1",
                     "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://www.instagram.com/accounts/password/reset/",
                     "Origin": "https://www.instagram.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if data.get("status") == "ok" or "we sent" in text or "check your" in text:
            return _r(name, url, True)
        if data.get("status") == "fail":
            msg = data.get("message", "").lower()
            if "no user" in msg or "not found" in msg or "doesn't exist" in msg:
                return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_reddit(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Reddit", "https://www.reddit.com"
    try:
        # Reddit API requires modhash — use the JSON endpoint which works without auth
        r = await client.post(
            "https://www.reddit.com/api/forgot_password.json",
            data={"email": email, "api_type": "json"},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.reddit.com/login/"},
            timeout=10
        )
        data = _json(r)
        errors = data.get("json", {}).get("errors", [])
        if not errors:
            return _r(name, url, True)
        err_flat = " ".join(str(e) for e in errors).lower()
        if "email" in err_flat or "not found" in err_flat or "unknown" in err_flat:
            return _r(name, url, False)
        return _r(name, url, True)  # no errors = accepted = account exists
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_tumblr(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Tumblr", "https://www.tumblr.com"
    try:
        # Tumblr forgot password via API
        r = await client.post(
            "https://www.tumblr.com/api/v2/user/reset_password",
            json={"email": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://www.tumblr.com",
                     "Referer": "https://www.tumblr.com/login"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        meta = data.get("meta", {})
        status_code = meta.get("status", r.status_code)
        if status_code == 200 or r.status_code == 200:
            return _r(name, url, True)
        if "not found" in text or status_code == 404 or r.status_code == 404:
            return _r(name, url, False)
        if "unauthorized" in text or status_code in (401, 403):
            # Tumblr returns 401 when no account — requires auth for existing accounts
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_patreon(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Patreon", "https://www.patreon.com"
    try:
        r = await client.post(
            "https://www.patreon.com/api/auth",
            json={"data": {"type": "user",
                           "attributes": {"email": email, "password": "wrongpassword123!"}}},
            params={"include": "null"},
            headers={**HEADERS,
                     "Content-Type": "application/vnd.api+json",
                     "Origin": "https://www.patreon.com",
                     "Referer": "https://www.patreon.com/login"},
            timeout=10
        )
        text = r.text.lower()
        data = _json(r)
        errors = data.get("errors", [{}])
        err_str = " ".join(e.get("detail", "") for e in errors).lower() if errors else ""
        # Wrong password = account exists
        if any(x in err_str + text for x in ["incorrect password", "invalid password", "wrong password", "password"]):
            return _r(name, url, True)
        # No account
        if any(x in err_str + text for x in ["no account", "not registered", "email address is not", "couldn't find"]):
            return _r(name, url, False)
        if r.status_code == 401:
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_dropbox(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Dropbox", "https://www.dropbox.com"
    try:
        g = await client.get("https://www.dropbox.com/forgot", headers=HEADERS, timeout=10)
        token = _csrf(g.text, "t", "authenticity_token", "_csrf_token")
        r = await client.post(
            "https://www.dropbox.com/forgot_password_ajax",
            data={"email": email, "t": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.dropbox.com/forgot",
                     "Origin": "https://www.dropbox.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if data.get("status") == "ok" or data.get("success") is True or r.status_code == 200:
            if "not found" not in text and "no account" not in text:
                return _r(name, url, True)
        if "no account" in text or "not found" in text or data.get("status") == "error":
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_pinterest(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Pinterest", "https://www.pinterest.com"
    try:
        g = await client.get("https://www.pinterest.com/password/reset/",
                             headers=HEADERS, timeout=10)
        token = _csrf(g.text, "csrfmiddlewaretoken") or g.cookies.get("csrftoken", "")
        r = await client.post(
            "https://www.pinterest.com/resource/UserPasswordResetResource/create/",
            data={"source_url": "/password/reset/",
                  "data": f'{{"options":{{"email":"{email}"}},"context":{{}}}}'},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-CSRFToken": token,
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.pinterest.com/password/reset/",
                     "Origin": "https://www.pinterest.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        status = data.get("status", "")
        if status == "success" or r.status_code == 200:
            if "not found" not in text and "no account" not in text:
                return _r(name, url, True)
        if status == "failure" or "not found" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_wordpress(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "WordPress.com", "https://wordpress.com"
    try:
        r = await client.post(
            "https://wordpress.com/wp-login.php",
            params={"action": "lostpassword"},
            data={"user_login": email, "redirect_to": "", "action": "lostpassword"},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://wordpress.com",
                     "Referer": "https://wordpress.com/wp-login.php?action=lostpassword"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["check your email", "we've just sent", "a link has been",
                                    "email has been sent", "we will send"]):
            return _r(name, url, True)
        if any(x in text for x in ["no user is registered", "there is no user",
                                    "no account", "not found", "invalid username"]):
            return _r(name, url, False)
        # WordPress.com redirects on success
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_bugcrowd(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Bugcrowd", "https://bugcrowd.com"
    try:
        g = await client.get("https://bugcrowd.com/user/password/new",
                             headers=HEADERS, timeout=10)
        token = _csrf(g.text, "authenticity_token")
        r = await client.post(
            "https://bugcrowd.com/user/password",
            data={"user[email]": email, "authenticity_token": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://bugcrowd.com/user/password/new",
                     "Origin": "https://bugcrowd.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["you will receive", "receive an email", "instructions",
                                    "reset instructions", "if an account"]):
            return _r(name, url, True)
        if any(x in text for x in ["not found", "no account", "email not"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_roblox(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Roblox", "https://www.roblox.com"
    try:
        # Check via signup — email already in use = account exists
        r = await client.post(
            "https://auth.roblox.com/v2/signup",
            json={"username": f"TestUser{hash(email) % 99999}",
                  "password": "TestPass99!Roblox",
                  "gender": 1,
                  "birthday": "1990-01-01T00:00:00.000Z",
                  "email": email,
                  "isTosAgreementBoxChecked": True},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://www.roblox.com",
                     "Referer": "https://www.roblox.com/"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        errors = data.get("errors", [])
        err_str = " ".join(str(e) for e in errors).lower()
        if any(x in err_str + text for x in ["email already", "email is taken",
                                              "email_already_used", "email already in use"]):
            return _r(name, url, True)
        # Code 17 = email taken on Roblox
        if any(e.get("code") == 17 for e in errors if isinstance(e, dict)):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_twitch(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Twitch", "https://www.twitch.tv"
    try:
        # Use Twitch's password reset endpoint
        r = await client.post(
            "https://passport.twitch.tv/forgot_password",
            json={"login": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
                     "Origin": "https://www.twitch.tv",
                     "Referer": "https://www.twitch.tv/"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if r.status_code == 200:
            if "error" not in text and "not found" not in text:
                return _r(name, url, True)
        if r.status_code == 400:
            err = data.get("error", "").lower()
            if "not found" in err or "no account" in err:
                return _r(name, url, False)
        if r.status_code == 404:
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_adobe(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Adobe", "https://www.adobe.com"
    try:
        r = await client.post(
            "https://ims-na1.adobelogin.com/ims/forgot_password/v2",
            data={"email": email,
                  "client_id": "adobedotcom2",
                  "response_type": "token",
                  "redirect_uri": "https://www.adobe.com/"},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://auth.services.adobe.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if r.status_code == 200:
            if "not_found" not in text and "error" not in text.split('"')[0]:
                return _r(name, url, True)
        if "user_not_found" in text or "not_found" in text or r.status_code == 404:
            return _r(name, url, False)
        if r.status_code in (400, 401):
            err = data.get("error", "")
            if "not_found" in err or "unknown" in err:
                return _r(name, url, False)
            return _r(name, url, True)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_lastpass(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "LastPass", "https://www.lastpass.com"
    try:
        r = await client.post(
            "https://lastpass.com/ajax/forgotpassword_email.php",
            data={"username": email},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://lastpass.com/forgot.php"},
            timeout=10
        )
        text = r.text.lower()
        if "sent" in text or "check your email" in text or r.status_code == 200:
            if "not found" not in text and "no account" not in text:
                return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_fiverr(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Fiverr", "https://www.fiverr.com"
    try:
        g = await client.get("https://www.fiverr.com/login", headers=HEADERS, timeout=10)
        token = _csrf(g.text, "authenticity_token", "_fiverr_csrf_token")
        r = await client.post(
            "https://www.fiverr.com/login_/forgot_password",
            data={"email_or_username": email, "authenticity_token": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.fiverr.com/login",
                     "Origin": "https://www.fiverr.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if data.get("status") == "success" or data.get("success") is True:
            return _r(name, url, True)
        if r.status_code == 200 and "not found" not in text and "no user" not in text:
            return _r(name, url, True)
        if any(x in text for x in ["not found", "no user", "doesn't exist", "invalid"]):
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_airbnb(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Airbnb", "https://www.airbnb.com"
    try:
        r = await client.post(
            "https://www.airbnb.com/api/v2/authentications",
            json={"email": email, "type": "email"},
            params={"_format": "for_auth_modal",
                    "key": "d306zoyjsyarp7ifhu67rjxn52tv0t20"},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "X-Airbnb-Api-Key": "d306zoyjsyarp7ifhu67rjxn52tv0t20",
                     "Device-Memory": "8",
                     "Viewport-Width": "1920",
                     "Origin": "https://www.airbnb.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if data.get("login") is not None:
            return _r(name, url, True)
        if data.get("signup") is not None:
            return _r(name, url, False)
        if "authenticationState" in r.text or "login" in r.text:
            return _r(name, url, True)
        if "signup" in r.text or "new_account" in r.text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_kickstarter(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Kickstarter", "https://www.kickstarter.com"
    try:
        g = await client.get("https://www.kickstarter.com/login",
                             headers=HEADERS, timeout=10)
        token = _csrf(g.text, "csrf-token", "authenticity_token")
        r = await client.post(
            "https://www.kickstarter.com/forgot",
            data={"email": email, "authenticity_token": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.kickstarter.com/login",
                     "Origin": "https://www.kickstarter.com"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if r.status_code == 200:
            if any(x in text for x in ["sent", "check your email", "instructions",
                                        "if there's a kickstarter"]):
                return _r(name, url, True)
        if data.get("success") is True or data.get("status") == "success":
            return _r(name, url, True)
        if "not found" in text or r.status_code == 404:
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_ebay(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "eBay", "https://www.ebay.com"
    try:
        # Use signin page — submit email, check response
        r = await client.post(
            "https://signin.ebay.com/ws/eBayISAPI.dll",
            params={"SignIn": ""},
            data={"siteid": "0", "co_partnerId": "0", "UsingSSL": "1",
                  "ru": "", "userid": email, "pass": "wrongpassword123",
                  "keepMeSignInOption": "0"},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn",
                     "Origin": "https://signin.ebay.com"},
            timeout=10
        )
        text = r.text.lower()
        # Email recognised but wrong password = account exists
        if any(x in text for x in ["the password you entered", "password is incorrect",
                                    "sign in to ebay", "wrong password"]):
            return _r(name, url, True)
        # Email not found
        if any(x in text for x in ["we don't recognise", "not recognise",
                                    "no account", "not find"]):
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_snapchat(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Snapchat", "https://www.snapchat.com"
    try:
        r = await client.post(
            "https://accounts.snapchat.com/accounts/get_username_suggestions",
            data={"email": email, "source": "web", "xsrf_token": ""},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://accounts.snapchat.com",
                     "Referer": "https://accounts.snapchat.com/accounts/signup"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if not data:
            # Try alternate endpoint
            r2 = await client.post(
                "https://accounts.snapchat.com/accounts/forgot_password/send_code",
                data={"email": email},
                headers={**HEADERS,
                         "Content-Type": "application/x-www-form-urlencoded",
                         "Origin": "https://accounts.snapchat.com"},
                timeout=10
            )
            data = _json(r2)
            text = r2.text.lower()
            if data.get("status") == "OK" or r2.status_code == 200:
                return _r(name, url, True)
            if r2.status_code == 404:
                return _r(name, url, False)
            if "not found" in text or "no account" in text:
                return _r(name, url, False)
            return _r(name, url, None, f"status {r2.status_code}")
        suggestions = data.get("username_suggestions", [])
        if suggestions:
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_stackoverflow(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Stack Overflow", "https://stackoverflow.com"
    try:
        g = await client.get("https://stackoverflow.com/users/account-recovery",
                             headers=HEADERS, timeout=10)
        token = _csrf(g.text, "fkey", "authenticity_token")
        r = await client.post(
            "https://stackoverflow.com/users/account-recovery",
            data={"Email": email, "fkey": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://stackoverflow.com/users/account-recovery",
                     "Origin": "https://stackoverflow.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["if there is an account", "sent you an email",
                                    "instructions have been sent", "check your email"]):
            return _r(name, url, True)
        if any(x in text for x in ["not find", "no account", "not found"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_tiktok(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "TikTok", "https://www.tiktok.com"
    try:
        r = await client.post(
            "https://www.tiktok.com/passport/web/account/passwd/forget_passwd/send_email_code/",
            json={"email": email, "captcha_ticket": "", "captcha_rand_str": ""},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://www.tiktok.com",
                     "Referer": "https://www.tiktok.com/login/"},
            timeout=10
        )
        data = _json(r)
        if r.status_code == 200 and data.get("message") == "success":
            return _r(name, url, True)
        if r.status_code in (400, 404):
            err = str(data.get("message", "")).lower()
            if any(x in err for x in ["not exist", "not found", "no account"]):
                return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_linkedin(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "LinkedIn", "https://www.linkedin.com"
    try:
        g = await client.get(
            "https://www.linkedin.com/checkpoint/lg/forgot-password",
            headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=10
        )
        token = _csrf(g.text, "csrfToken", "loginCsrfParam")
        if not token:
            m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', g.text)
            if m:
                token = m.group(1)
        r = await client.post(
            "https://www.linkedin.com/checkpoint/lg/forgot-password-submit",
            data={"email": email, "csrfToken": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://www.linkedin.com/checkpoint/lg/forgot-password",
                     "Origin": "https://www.linkedin.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["we've sent", "check your email", "sent you an email",
                                    "password reset email", "email has been sent"]):
            return _r(name, url, True)
        if any(x in text for x in ["couldn't find", "not found", "no account"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_steam(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Steam", "https://store.steampowered.com"
    try:
        r = await client.get(
            "https://store.steampowered.com/join/ajaxcheckemailavail/",
            params={"email": email},
            headers={**HEADERS,
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://store.steampowered.com/join/"},
            timeout=10
        )
        data = _json(r)
        avail = data.get("bAvail")
        if avail is False:
            return _r(name, url, True)
        if avail is True:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_epicgames(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Epic Games", "https://www.epicgames.com"
    try:
        r = await client.post(
            "https://www.epicgames.com/id/api/forgotPassword",
            json={"email": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://www.epicgames.com",
                     "Referer": "https://www.epicgames.com/id/forgotPassword"},
            timeout=10
        )
        if r.status_code == 200:
            return _r(name, url, True)
        if r.status_code == 409:
            return _r(name, url, True)  # 409 Conflict = email already registered
        if r.status_code in (400, 404):
            data = _json(r)
            err = (data.get("errorMessage", "") or data.get("message", "")).lower()
            if any(x in err for x in ["not found", "no account", "doesn't exist"]):
                return _r(name, url, False)
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_microsoft(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Microsoft", "https://account.microsoft.com"
    try:
        r = await client.post(
            "https://login.live.com/GetCredentialType.srf",
            json={"username": email,
                  "uaid": "",
                  "isOtherIdpSupported": True,
                  "checkPhones": False,
                  "isRemoteNGCSupported": False,
                  "isCookieBannerShown": False,
                  "isFidoSupported": False,
                  "originalRequest": ""},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Accept": "application/json",
                     "Origin": "https://login.live.com",
                     "Referer": "https://login.live.com/"},
            timeout=10
        )
        data = _json(r)
        result = data.get("IfExistsResult", -1)
        if result == 0:
            return _r(name, url, True)
        if result == 1:
            return _r(name, url, False)
        if result == 6:
            return _r(name, url, True)  # federated account (work/school)
        # Fallback: enterprise endpoint
        r2 = await client.post(
            "https://login.microsoftonline.com/common/GetCredentialType",
            json={"Username": email, "isOtherIdpSupported": True},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=10
        )
        data2 = _json(r2)
        result2 = data2.get("IfExistsResult", -1)
        if result2 == 0:
            return _r(name, url, True)
        if result2 == 1:
            return _r(name, url, False)
        if result2 == 6:
            return _r(name, url, True)
        return _r(name, url, None, f"IfExistsResult={result}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_gravatar(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Gravatar", "https://gravatar.com"
    try:
        import hashlib
        h = hashlib.md5(email.lower().strip().encode()).hexdigest()
        r = await client.get(
            f"https://www.gravatar.com/{h}.json",
            headers=HEADERS,
            timeout=10
        )
        if r.status_code == 200:
            return _r(name, url, True)
        if r.status_code == 404:
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_fansly(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Fansly", "https://fansly.com"
    try:
        r = await client.post(
            "https://apiv3.fansly.com/api/v1/auth/forgot_password",
            json={"email": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://fansly.com",
                     "Referer": "https://fansly.com/"},
            timeout=10
        )
        if r.status_code == 200:
            return _r(name, url, True)
        if r.status_code in (404, 422):
            return _r(name, url, False)
        text = r.text.lower()
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_chaturbate(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Chaturbate", "https://chaturbate.com"
    try:
        g = await client.get("https://chaturbate.com/auth/password_reset/",
                             headers=HEADERS, timeout=10)
        token = _csrf(g.text, "csrfmiddlewaretoken") or g.cookies.get("csrftoken", "")
        r = await client.post(
            "https://chaturbate.com/auth/password_reset/",
            data={"email": email, "csrfmiddlewaretoken": token},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-CSRFToken": token,
                     "Referer": "https://chaturbate.com/auth/password_reset/",
                     "Origin": "https://chaturbate.com"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["we've emailed", "sent an email", "check your email",
                                    "password reset"]):
            return _r(name, url, True)
        if any(x in text for x in ["not found", "no account", "no user"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_soundcloud(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "SoundCloud", "https://soundcloud.com"
    try:
        r = await client.post(
            "https://soundcloud.com/password/forgot",
            data={"password_recovery[email]": email},
            headers={**HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded",
                     "Origin": "https://soundcloud.com",
                     "Referer": "https://soundcloud.com/forgot-my-password"},
            timeout=10
        )
        text = r.text.lower()
        if any(x in text for x in ["sent you an email", "check your email",
                                    "will receive an email", "reset instructions"]):
            return _r(name, url, True)
        if any(x in text for x in ["not found", "no account", "couldn't find"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_medium(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Medium", "https://medium.com"
    try:
        r = await client.post(
            "https://medium.com/m/signin/email",
            json={"email": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://medium.com",
                     "Referer": "https://medium.com/m/signin/"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if r.status_code == 200:
            if data.get("success") or "check your email" in text or "magic link" in text:
                return _r(name, url, True)
        if "not found" in text or "no account" in text:
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_substack(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Substack", "https://substack.com"
    try:
        r = await client.post(
            "https://substack.com/api/v1/email/subscribe/signin",
            json={"email": email, "captcha_response": None},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://substack.com",
                     "Referer": "https://substack.com/"},
            timeout=10
        )
        data = _json(r)
        if r.status_code == 200 or data.get("email"):
            return _r(name, url, True)
        if r.status_code in (400, 404):
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_deviantart(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "DeviantArt", "https://www.deviantart.com"
    try:
        r = await client.post(
            "https://www.deviantart.com/_napi/shared_api/account/forgot_password",
            json={"email_or_username": email},
            headers={**HEADERS,
                     "Content-Type": "application/json",
                     "Origin": "https://www.deviantart.com",
                     "Referer": "https://www.deviantart.com/users/forgot_password"},
            timeout=10
        )
        text = r.text.lower()
        if r.status_code == 200:
            if any(x in text for x in ["email has been sent", "check your", "we've sent"]):
                return _r(name, url, True)
        if any(x in text for x in ["not found", "no account", "doesn't exist"]):
            return _r(name, url, False)
        if r.status_code in (302, 303):
            return _r(name, url, True)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


async def check_etsy(client: httpx.AsyncClient, email: str) -> dict:
    name, url = "Etsy", "https://www.etsy.com"
    try:
        r = await client.post(
            "https://www.etsy.com/api/v3/ajax/member/send-forgot-password-email",
            params={"email": email},
            headers={**HEADERS,
                     "X-Requested-With": "XMLHttpRequest",
                     "Origin": "https://www.etsy.com",
                     "Referer": "https://www.etsy.com/"},
            timeout=10
        )
        data = _json(r)
        text = r.text.lower()
        if r.status_code == 200:
            if data.get("error") is None or any(x in text for x in ["sent", "check your"]):
                return _r(name, url, True)
        if any(x in text for x in ["not found", "no account", "doesn't exist"]):
            return _r(name, url, False)
        return _r(name, url, None, "ambiguous")
    except Exception as e:
        return _r(name, url, None, str(e))


# ── Registry ──────────────────────────────────────────────────────────────────

ALL_MODULES = [
    check_duolingo,
    check_spotify,
    check_twitter,
    check_tumblr,
    check_bugcrowd,
    check_twitch,
    check_adobe,
    check_lastpass,
    check_fiverr,
    check_ebay,
    check_snapchat,
    check_stackoverflow,
    check_microsoft,
    check_gravatar,
    check_fansly,
    check_substack,
    check_deviantart,
    check_etsy,
]

SITE_NAMES = {f.__name__.replace("check_", ""): f for f in ALL_MODULES}
