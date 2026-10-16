"""Unit tests for qac.py. Run: python -m unittest discover -s tests"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "quota-aware-continuation", "scripts"))
import qac  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "skills", "quota-aware-continuation", "templates", "CHECKPOINT.md")


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = qac.main(list(argv))
    return code, buf.getvalue()


class DecideTest(unittest.TestCase):
    def reset_in(self, minutes):
        return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")

    def test_below_threshold_continues(self):
        code, out = run("decide", "--percent", "40", "--resets-at", self.reset_in(60))
        self.assertEqual(json.loads(out)["action"], "continue")

    def test_at_threshold_pauses_and_resumes_after_reset(self):
        reset = self.reset_in(60)
        code, out = run("decide", "--percent", "95", "--resets-at", reset, "--delay-minutes", "5")
        d = json.loads(out)
        self.assertEqual(d["action"], "pause")
        fire = qac.parse_iso(d["fire_at"])
        self.assertIsNotNone(fire.utcoffset())
        delta = (fire - qac.parse_iso(reset)).total_seconds()
        self.assertTrue(5 * 60 <= delta < 6 * 60, delta)

    def test_reads_get_usage_json_and_picks_5_hour_window(self):
        usage = {"plan": {"status": "ok", "windows": [
            {"label": "Weekly · all models", "percentUsed": 99, "resetsAt": self.reset_in(3000)},
            {"label": "5-hour limit", "percentUsed": 10, "resetsAt": self.reset_in(60)}]}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(usage, f)
        try:
            code, out = run("decide", "--usage-json", f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(json.loads(out)["action"], "continue")

    def test_unavailable_usage_is_unknown(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"plan": {"status": "not_applicable"}}, f)
        try:
            code, out = run("decide", "--usage-json", f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(json.loads(out)["action"], "unknown")

    def test_past_reset_still_schedules_in_future(self):
        code, out = run("decide", "--percent", "99", "--resets-at", self.reset_in(-30))
        fire = qac.parse_iso(json.loads(out)["fire_at"])
        self.assertGreater(fire, datetime.now(timezone.utc) + timedelta(minutes=1))

    def test_hide_percent(self):
        code, out = run("decide", "--percent", "99", "--hide-percent")
        self.assertNotIn("percent\"", out)


class CheckpointTest(unittest.TestCase):
    def test_template_reports_placeholders(self):
        code, out = run("validate", TEMPLATE)
        self.assertEqual(code, 1)
        self.assertIn("placeholder", out)

    def test_filled_checkpoint_is_valid(self):
        text = open(TEMPLATE, encoding="utf-8").read()
        text = text.replace("<FILL ISO 8601 with offset, e.g. 2026-10-16T23:40:00+08:00>", "2026-10-16T23:40:00+08:00")
        text = qac.PLACEHOLDER.sub("filled", text)
        self.assertEqual(qac.validate_text(text), [])
        self.assertTrue(qac.validate_text(text.replace("## Next action", "## Later")))

    def test_atomic_write_replaces_file(self):
        d = tempfile.mkdtemp()
        target = os.path.join(d, "sub", "f.txt")
        old_stdin = sys.stdin
        try:
            for content in (b"one", b"two"):
                sys.stdin = io.TextIOWrapper(io.BytesIO(content))
                run("write", target)
        finally:
            sys.stdin = old_stdin
        self.assertEqual(open(target, "rb").read(), b"two")
        self.assertEqual(os.listdir(os.path.dirname(target)), ["f.txt"])


class ScheduleTest(unittest.TestCase):
    def test_heartbeat_is_date_bound(self):
        code, out = run("heartbeat", "--every", "30", "--days", "2")
        cron = json.loads(out)["cron"].split()
        self.assertEqual(cron[0], "*/30")
        self.assertNotEqual(cron[2], "*")
        self.assertNotEqual(cron[3], "*")

    def write_checkpoint(self, status, minutes_ago):
        updated = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
        f = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        f.write("status: %s\nupdated: %s\n" % (status, updated))
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def tick(self, status, minutes_ago):
        code, out = run("tick", self.write_checkpoint(status, minutes_ago))
        return json.loads(out)["action"]

    def test_tick_actions(self):
        self.assertEqual(self.tick("done", 0), "done")
        self.assertEqual(self.tick("in_progress", 3), "busy")
        self.assertEqual(self.tick("in_progress", 45), "go")
        self.assertEqual(self.tick("paused", 1), "go")


if __name__ == "__main__":
    unittest.main()
