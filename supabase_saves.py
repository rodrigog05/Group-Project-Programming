"""Supabase Auth and per-player saves using the public key and the player's token."""

import json
from dataclasses import dataclass, field
from time import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from tycoon import Town, pack_save, unpack_save


class SaveConflict(Exception):
    """The save was updated in another browser session."""


class SupabaseError(OSError):
    """A cloud request failed. Keep response details out of the game UI."""


class SignupError(SupabaseError):
    """An account creation failure with a message safe to show to the player."""


SIGNUP_MESSAGES = {
    "weak_password": "Supabase rejected this password. Choose a stronger one.",
    "email_address_invalid": "Enter a valid email address.",
    "email_address_not_authorized": (
        "Confirmation email is unavailable for this address. The site owner needs to configure "
        "an email provider in Supabase to allow public signups."
    ),
    "email_provider_disabled": "Email sign-up is currently disabled for this game.",
    "signup_disabled": "Account creation is currently disabled for this game.",
    "over_email_send_rate_limit": "Too many confirmation emails were requested. Wait before trying again.",
    "over_request_rate_limit": "Too many requests. Wait before trying again.",
    "unexpected_failure": "The account service could not finish signup. The site owner can check Supabase Auth logs.",
}


def signup_error(error):
    message = {
        401: "The site owner needs to check the Supabase project URL and publishable key.",
        429: "Too many signup requests. Wait before trying again.",
    }.get(error.code, "Could not create an account. Check your email and password or try again.")
    try:
        details = json.loads(error.read(8192))
        if isinstance(details, dict) and isinstance(details.get("error_code"), str):
            message = SIGNUP_MESSAGES.get(details["error_code"], message)
    except (OSError, ValueError):
        pass
    return SignupError(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@dataclass
class CloudSession:
    user_id: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float

    @classmethod
    def from_response(cls, data):
        return cls(
            str(UUID(data["user"]["id"])),
            data["access_token"],
            data["refresh_token"],
            time() + int(data["expires_in"]),
        )


class Supabase:
    def __init__(self, url, public_key):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or (
            parsed.path.rstrip("/") or parsed.query or parsed.fragment
        ):
            raise ValueError("Use the HTTPS Supabase project URL.")
        if not public_key.startswith("sb_publishable_"):
            raise ValueError("Use the Supabase publishable key.")
        self.url = url.rstrip("/")
        self.public_key = public_key

    def request(self, method, path, *, body=None, token=None, query=None, prefer=None):
        url = self.url + path + ("?" + urlencode(query) if query else "")
        headers = {"apikey": self.public_key, "Accept": "application/json"}
        data = None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, allow_nan=False).encode()
        if prefer:
            headers["Prefer"] = prefer
        try:
            with build_opener(NoRedirect()).open(Request(url, data, headers, method=method), timeout=8) as response:
                limit = 1024 * 1024
                content = response.read(limit + 1)
                if len(content) > limit:
                    raise ValueError("Cloud response is too large.")
                return json.loads(content) if content else None
        except HTTPError as error:
            with error:
                if path == "/auth/v1/signup":
                    raise signup_error(error) from None
                raise SupabaseError(f"Cloud request failed ({error.code}).") from None
        except (OSError, ValueError):
            raise SupabaseError("Could not reach cloud saves.") from None

    def sign_in(self, email, password):
        response = self.request(
            "POST", "/auth/v1/token", query={"grant_type": "password"},
            body={"email": email, "password": password},
        )
        return CloudSession.from_response(response)

    def sign_up(self, email, password):
        response = self.request("POST", "/auth/v1/signup", body={"email": email, "password": password})
        if not isinstance(response, dict):
            raise SupabaseError("Invalid signup response.")
        if response.get("access_token"):
            return CloudSession.from_response(response)
        if not (response.get("id") or response.get("user")):
            raise SupabaseError("Invalid signup response.")
        return None

    def refresh(self, session):
        response = self.request(
            "POST", "/auth/v1/token", query={"grant_type": "refresh_token"},
            body={"refresh_token": session.refresh_token},
        )
        updated = CloudSession.from_response(response)
        if updated.user_id != session.user_id:
            raise SupabaseError("Cloud session identity changed.")
        session.access_token = updated.access_token
        session.refresh_token = updated.refresh_token
        session.expires_at = updated.expires_at


class CloudSave:
    path = "/rest/v1/foundry_saves"

    def __init__(self, client, session):
        self.client = client
        self.session = session

    def request(self, method, **options):
        if time() + 30 >= self.session.expires_at:
            self.client.refresh(self.session)
        return self.client.request(method, self.path, token=self.session.access_token, **options)

    def load(self):
        rows = self.request("GET", query={"user_id": "eq." + self.session.user_id, "select": "revision,snapshot"})
        if not rows:
            return Town(), 0
        town, _ = unpack_save(rows[0]["snapshot"])
        return town, rows[0]["revision"]

    def save(self, town, revision):
        body = {"revision": revision + 1, "snapshot": pack_save(town, 0)}
        if revision == 0:
            rows = self.request(
                "POST", body={**body, "user_id": self.session.user_id},
                query={"on_conflict": "user_id"}, prefer="resolution=ignore-duplicates,return=representation",
            )
        else:
            rows = self.request(
                "PATCH", body=body,
                query={"user_id": "eq." + self.session.user_id, "revision": f"eq.{revision}"},
                prefer="return=representation",
            )
        if not rows:
            raise SaveConflict
        return rows[0]["revision"]
