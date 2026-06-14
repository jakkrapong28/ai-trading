"""update-settings must ignore masked values the dashboard echoes back, so a
real API key is never clobbered by its own '****1234' mask (root cause of the
corrupted 8-char keys)."""
from backend.main import _is_masked


def test_masked_values_detected():
    assert _is_masked("****5062") is True
    assert _is_masked("****28fg") is True


def test_real_values_not_masked():
    assert _is_masked("abcd1234efgh5678realkey") is False
    assert _is_masked("") is False
    assert _is_masked("sk-live-XYZ") is False
