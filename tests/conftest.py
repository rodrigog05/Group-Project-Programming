import pytest


@pytest.fixture(autouse=True)
def isolate_cloud_settings(monkeypatch):
    """Keep AppTest runs independent of the host's Supabase configuration."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
