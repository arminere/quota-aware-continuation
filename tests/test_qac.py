"""Unit tests for qac.py and qac_gate.py. Run: python -m unittest discover -s tests"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills", "quota-aware-continuation", "scripts")
sys.path.insert(0, SCRIPTS)
import qac  # noqa: E402
import qac_gate  # noqa: E402

TEMPLATE = os.path.join(SCRIPTS, "..", "templates", "CHECKPOINT.md")


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = qac.main(list(argv))
    return code, buf.getvalue()


def iso_in(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def temp_file(test, text, suffix=".md"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    test.addCleanup(os.remove, f.name)
    return f.name


class DecideTest(unittest.TestCase):
    def decide(self, *argv):
        code, out = run("decide", *argv)
        return json.loads(out)

    def test_below_threshold_continues(self):
        d = self.decide("--percent", "40", "--resets-at", iso_in(60))
        self.assertEqual(d["action"], "continue")
        self.assertNotIn("resume_after", d)

    def test_five_hour_pause_resumes_after_reset(self):
        reset = iso_in(60)
        d = self.decide("--percent", "95", "--resets-at", reset, "--delay-minutes", "5")
        self.assertEqual(d["action"], "pause")
        delta = (qac.parse_iso(d["resume_after"]) - qac.parse_iso(reset)).total_seconds()
        self.assertTrue(5 * 60 <= delta < 6 * 60, delta)

    def test_weekly_limit_pauses_until_weekly_reset(self):
        weekly_reset = iso_in(3 * 24 * 60)
        d = self.decide("--percent", "20", "--resets-at", iso_in(60),
                        "--weekly-percent", "96", "--weekly-resets-at", weekly_reset)
        self.assertEqual(d["action"], "pause")
        self.assertEqual(d["limited_by"], ["Weekly"])
        self.assertGreater(qac.parse_iso(d["resume_after"]), qac.parse_iso(weekly_reset))

    def test_both_over_uses_latest_reset(self):
        d = self.decide("--percent", "99", "--resets-at", iso_in(60),
                        "--weekly-percent", "99", "--weekly-resets-at", iso_in(600))
        self.assertGreater(qac.parse_iso(d["resume_after"]), qac.parse_iso(iso_in(600)))

    def test_reads_get_usage_json(self):
        usage = {"plan": {"status": "ok", "windows": [
            {"label": "5-hour limit", "percentUsed": 10, "resetsAt": iso_in(60)},
            {"label": "Weekly · all models", "percentUsed": 97, "resetsAt": iso_in(3000)}]}}
        d = self.decide("--usage-json", temp_file(self, json.dumps(usage), ".json"))
        self.assertEqual(d["action"], "pause")
        self.assertEqual(d["limited_by"], ["Weekly · all models"])

    def test_unavailable_usage_is_unknown(self):
        path = temp_file(self, json.dumps({"plan": {"status": "not_applicable"}}), ".json")
        self.assertEqual(self.decide("--usage-json", path)["action"], "unknown")

    def test_past_reset_still_resumes_in_future(self):
        d = self.decide("--percent", "99", "--resets-at", iso_in(-30))
        self.assertGreater(qac.parse_iso(d["resume_after"]), datetime.now(timezone.utc) + timedelta(minutes=1))

    def test_hide_percent(self):
        d = self.decide("--percent", "99", "--hide-percent")
        self.assertNotIn("usage", d)


class GateTest(unittest.TestCase):
    def allow(self, **fields):
        return qac_gate.decide({k: str(v) for k, v in fields.items()}, datetime.now(timezone.utc))[0]

    def test_rules(self):
        self.assertFalse(self.allow(status="done"))
        self.assertFalse(self.allow(status="hold"))
        self.assertFalse(self.allow(status="paused", resume_after=iso_in(30)))
        self.assertTrue(self.allow(status="paused", resume_after=iso_in(-1)))
        self.assertTrue(self.allow(status="paused", resume_after="none"))
        self.assertFalse(self.allow(status="in_progress", updated=iso_in(-3)))
        self.assertTrue(self.allow(status="in_progress", updated=iso_in(-45)))
        self.assertTrue(self.allow(status="in_progress", updated=iso_in(-3), lock_minutes=2))

    def gate(self, prompt):
        old_in, buf = sys.stdin, io.StringIO()
        try:
            sys.stdin = io.StringIO(json.dumps({"prompt": prompt}))
            with redirect_stdout(buf):
                qac_gate.main()
        finally:
            sys.stdin = old_in
        return buf.getvalue()

    def test_hook_blocks_done_tick_and_ignores_other_prompts(self):
        path = temp_file(self, "status: done\nupdated: %s\n" % iso_in(-60))
        self.addCleanup(lambda: os.path.exists(os.path.join(os.path.dirname(path), "gate.log"))
                        and os.remove(os.path.join(os.path.dirname(path), "gate.log")))
        out = self.gate("Continue a long task (%s).\nCheckpoint: %s\n" % (qac_gate.MARKER, path))
        self.assertEqual(json.loads(out)["decision"], "block")
        self.assertEqual(self.gate("hello, Checkpoint: %s" % path), "")

    def test_tick_actions(self):
        cases = {"done": "status: done\n", "hold": "status: hold\n",
                 "wait": "status: paused\nresume_after: %s\n" % iso_in(30),
                 "busy": "status: in_progress\nupdated: %s\n" % iso_in(-1),
                 "go": "status: paused\n"}
        for action, text in cases.items():
            code, out = run("tick", temp_file(self, text))
            self.assertEqual(json.loads(out)["action"], action, text)


class HookInstallTest(unittest.TestCase):
    def test_install_is_idempotent_and_reversible(self):
        original = {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo"}]}]}}
        path = temp_file(self, json.dumps(original), ".json")
        self.addCleanup(lambda: os.path.exists(path + ".qac-backup") and os.remove(path + ".qac-backup"))
        run("install-hook", "--settings", path)
        run("install-hook", "--settings", path)
        data = json.load(open(path, encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["UserPromptSubmit"]), 1)
        self.assertIn("qac_gate.py", data["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"])
        run("uninstall-hook", "--settings", path)
        self.assertEqual(json.load(open(path, encoding="utf-8")), original)


class ScheduleAndCheckpointTest(unittest.TestCase):
    def test_heartbeat_default_is_unbounded(self):
        code, out = run("heartbeat")
        self.assertEqual(json.loads(out)["cron"], "*/30 * * * *")

    def test_heartbeat_can_be_date_bound(self):
        code, out = run("heartbeat", "--every", "5", "--days", "2")
        cron = json.loads(out)["cron"].split()
        self.assertEqual(cron[0], "*/5")
        self.assertNotEqual(cron[2], "*")

    def test_template_reports_placeholders(self):
        code, out = run("validate", TEMPLATE)
        self.assertEqual(code, 1)
        self.assertIn("placeholder", out)

    def test_filled_template_is_valid(self):
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


if __name__ == "__main__":
    unittest.main()
