"""Unit tests for pure helpers in :mod:`forecast_api.forecaster`.

We only exercise the functions that do not require LLM/HTTP mocking:
  * ``_truncate_article``
  * ``_question_hash``
  * ``_avg``

The full ``run_forecast`` integration path requires Bedrock and live network
and is covered by manual staging smoke tests.
"""

from forecast_api.forecaster import _avg, _question_hash, _truncate_article


class TestTruncateArticle:
    def test_returns_text_unchanged_when_under_cap(self):
        assert _truncate_article("short", 3000) == "short"

    def test_truncates_to_exact_cap(self):
        text = "x" * 5000
        out = _truncate_article(text, 3000)
        assert len(out) == 3000
        assert out == "x" * 3000

    def test_cap_of_zero_disables_truncation(self):
        text = "x" * 10_000
        assert _truncate_article(text, 0) == text

    def test_negative_cap_disables_truncation(self):
        text = "x" * 10_000
        assert _truncate_article(text, -1) == text


class TestQuestionHash:
    def test_is_stable_across_casing_and_whitespace(self):
        assert _question_hash("  Will X happen? ") == _question_hash("will x happen?")

    def test_short_hex_output(self):
        h = _question_hash("anything")
        assert len(h) == 12
        int(h, 16)  # raises if not hex


class TestAvg:
    def test_returns_none_when_no_values_for_key(self):
        assert _avg([{"other": 5}], "missing") is None

    def test_averages_across_entries_with_key(self):
        timings = [
            {"fetch_ms": 100},
            {"fetch_ms": 200},
            {"gate_ms": 50},  # no fetch_ms — skipped
        ]
        assert _avg(timings, "fetch_ms") == 150.0

    def test_ignores_none_values(self):
        timings = [{"fetch_ms": 100}, {"fetch_ms": None}]
        assert _avg(timings, "fetch_ms") == 100.0
