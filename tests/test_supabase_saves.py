from collections import defaultdict
from time import time

import pytest
from streamlit.testing.v1 import AppTest

from browser_game import SaveConflict
from supabase_saves import CloudSave, Supabase, SupabaseError
from tycoon import Town


@pytest.fixture
def cloud(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    accounts = {
        f"player{i}@example.test": f"00000000-0000-4000-8000-{i:012d}"
        for i in (1, 2)
    }
    saves = {}
    counts = defaultdict(int)

    def request(self, method, path, *, body=None, token=None, query=None, prefer=None):
        counts[method, path] += 1
        if path == "/auth/v1/token":
            if query == {"grant_type": "refresh_token"}:
                identity = body["refresh_token"].removeprefix("refresh-")
            else:
                identity = accounts.get(body["email"])
                if not identity or body["password"] != "test-password":
                    raise SupabaseError("Invalid credentials")
            return {"user": {"id": identity}, "access_token": identity,
                    "refresh_token": f"refresh-{identity}", "expires_in": 3600}
        assert path == "/rest/v1/foundry_saves"
        assert token in accounts.values()
        if method == "POST":
            assert body["user_id"] == token and query == {"on_conflict": "user_id"}
            assert prefer == "resolution=ignore-duplicates,return=representation"
            if token in saves:
                return []
            saves[token] = body
        else:
            assert query["user_id"] == f"eq.{token}"
            if method == "PATCH":
                assert prefer == "return=representation"
                if query["revision"] != f"eq.{saves[token]['revision']}":
                    return []
                saves[token] = body
        return [saves[token]] if token in saves else []

    monkeypatch.setattr(Supabase, "request", request)
    return Supabase("https://example.supabase.co", "sb_publishable_test"), counts


def test_cloud_save_restore_conflicts_and_token_refresh(cloud):
    api, counts = cloud
    session = api.sign_in("player1@example.test", "test-password")
    first = CloudSave(api, session)
    second = CloudSave(api, api.sign_in("player2@example.test", "test-password"))
    town, rev = first.load()
    town.cash = 87
    assert first.save(town, rev) == 1
    with pytest.raises(SaveConflict):
        first.save(Town(), rev)
    assert second.load()[1] == 0
    assert second.save(Town(), 0) == 1
    assert first.save(town, 1) == 2
    with pytest.raises(SaveConflict):
        first.save(Town(), 1)
    session.expires_at = time() - 1
    restored, rev = first.load()
    assert (restored.cash, rev) == (87, 2)
    assert counts["POST", "/auth/v1/token"] == 3
    assert second.load()[0].cash == 60


def click(app, value):
    next(button for button in app.button if button.label == value).click().run()
    assert not app.exception


def sign_in(app, email):
    next(field for field in app.text_input if field.label == "Email").set_value(email)
    next(field for field in app.text_input if field.label == "Password").set_value("test-password")
    click(app, "Sign in")


def test_cloud_account_can_continue_after_reopening_and_other_player_starts_fresh(cloud):
    api, _ = cloud
    app = AppTest.from_file("../streamlit_app.py").run()
    click(app, "New Game")
    app.session_state.town.cash = 92
    click(app, "Start menu")
    sign_in(app, "player1@example.test")
    assert app.session_state.revision == 1
    click(app, "Continue")
    assert app.metric[0].value == "$92"
    reopened = AppTest.from_file("../streamlit_app.py").run()
    sign_in(reopened, "player1@example.test")
    click(reopened, "Continue")
    assert reopened.metric[0].value == "$92"
    click(reopened, "Start menu")
    click(reopened, "Sign out")
    sign_in(reopened, "player2@example.test")
    assert reopened.session_state.revision == 0
    click(reopened, "New Game")
    assert reopened.metric[0].value == "$60"
    assert CloudSave(api, api.sign_in("player1@example.test", "test-password")).load()[0].cash == 92


def test_rejects_non_https_urls_and_secret_keys():
    with pytest.raises(ValueError):
        Supabase("http://example.supabase.co", "sb_publishable_test")
    with pytest.raises(ValueError):
        Supabase("https://example.supabase.co", "sb_secret_test")


def test_failed_sign_in_keeps_guest_progress(cloud):
    app = AppTest.from_file("../streamlit_app.py").run()
    click(app, "New Game")
    app.session_state.town.cash = 91
    click(app, "Start menu")
    sign_in(app, "unknown@example.test")
    assert app.session_state.town.cash == 91
    with pytest.raises(KeyError):
        app.session_state["cloud_session"]
    assert "Could not sign in" in app.error[0].value
