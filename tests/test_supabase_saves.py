from collections import defaultdict
from io import BytesIO
from time import time
from urllib.error import HTTPError

import pytest
from streamlit.testing.v1 import AppTest

import exchange
from browser_game import advance_clock
from supabase_saves import CloudSave, SaveConflict, SignupError, Supabase, SupabaseError
from tycoon import Order, Town


@pytest.fixture
def cloud(monkeypatch):
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
    for _ in range(121):
        advance_clock(town, 1)
    assert town.day == 2
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
    assert restored.elapsed == restored.market_elapsed == 121
    assert restored.day == 2
    assert counts["POST", "/auth/v1/token"] == 3
    assert second.load()[0].cash == 60


def click(app, value):
    next(button for button in app.button if button.label == value).click().run()
    assert not app.exception


def submit_account(app, email, button="Sign in"):
    next(field for field in app.text_input if field.label == "Email").set_value(email)
    next(field for field in app.text_input if field.label == "Password").set_value("test-password")
    click(app, button)


def sign_in(app, email):
    submit_account(app, email)


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
    app.session_state.town.cash = 96
    click(app, "Save progress")
    app.session_state.town.cash = 99
    click(app, "Reload cloud progress")
    assert app.metric[0].value == "$96"
    reopened = AppTest.from_file("../streamlit_app.py").run()
    sign_in(reopened, "player1@example.test")
    click(reopened, "Continue")
    assert reopened.metric[0].value == "$96"
    click(reopened, "Start menu")
    click(reopened, "Sign out")
    sign_in(reopened, "player2@example.test")
    assert reopened.session_state.revision == 0
    click(reopened, "New Game")
    assert reopened.metric[0].value == "$60"
    assert CloudSave(api, api.sign_in("player1@example.test", "test-password")).load()[0].cash == 96


def test_cloud_save_settles_retired_machinery_once_and_keeps_stock_holdings(cloud):
    api, _ = cloud
    email = "player1@example.test"
    store = CloudSave(api, api.sign_in(email, "test-password"))
    old_save = Town()
    assert exchange.buy_shares(old_save, "BELEM", 1)
    old_save.tier2_goods = 1
    old_save.tier2_order = Order(2, 20)
    old_save.tier2_price = 70
    expected_cash = old_save.cash + 210
    assert store.save(old_save, 0) == 1

    app = AppTest.from_file("../streamlit_app.py").run()
    sign_in(app, email)
    click(app, "Continue")
    assert app.metric[0].value == f"${expected_cash:,}"
    assert app.metric[1].value == "0 / 12"
    click(app, "Reload cloud progress")
    assert app.session_state.town.cash == expected_cash
    click(app, "Save progress")

    persisted, revision = store.load()
    assert revision == 2
    assert (persisted.cash, persisted.tier2_goods, persisted.tier2_order) == (expected_cash, 0, None)
    assert persisted.exchange == old_save.exchange
    reopened = AppTest.from_file("../streamlit_app.py").run()
    sign_in(reopened, email)
    assert reopened.session_state.town.cash == expected_cash


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


@pytest.mark.parametrize("confirm_email", [True, False])
def test_account_creation_handles_both_confirmation_settings(cloud, monkeypatch, confirm_email):
    request = Supabase.request

    def signup_request(self, method, path, **options):
        if path == "/auth/v1/signup":
            assert method == "POST" and options["body"]["email"] == "player1@example.test"
            if confirm_email:
                return {"id": "00000000-0000-4000-8000-000000000001"}
            return request(self, "POST", "/auth/v1/token", query={"grant_type": "password"},
                           body=options["body"])
        return request(self, method, path, **options)

    monkeypatch.setattr(Supabase, "request", signup_request)
    app = AppTest.from_file("../streamlit_app.py").run()
    submit_account(app, "player1@example.test", "Create account")
    if confirm_email:
        assert "confirmation email" in app.success[0].value
        with pytest.raises(KeyError):
            app.session_state["cloud_session"]
    else:
        assert app.session_state["cloud_session"].user_id.endswith("1")
        assert not app.success


def test_signup_returns_safe_message_for_default_email_provider(monkeypatch):
    class RejectedSignup:
        def open(self, request, timeout):
            assert request.get_method() == "POST"
            assert request.full_url.endswith("/auth/v1/signup")
            data = BytesIO(b'{"error_code":"email_address_not_authorized","msg":"private response"}')
            raise HTTPError(request.full_url, 403, "Forbidden", {}, data)

    monkeypatch.setattr("supabase_saves.build_opener", lambda *_: RejectedSignup())
    api = Supabase("https://example.supabase.co", "sb_publishable_test")
    with pytest.raises(SignupError, match="configure an email provider") as error:
        api.sign_up("player1@example.test", "test-password")
    assert "private response" not in str(error.value)
