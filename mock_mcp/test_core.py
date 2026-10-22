import concurrent.futures
import tempfile
import unittest
from pathlib import Path

from .core import Mailbox


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.now = 1000
        self.box = Mailbox(Path(self.folder.name) / "state.sqlite3", clock=lambda: self.now)
        self.args = {"to": "partner@company.example", "subject": "Club partnership", "body": "Synthetic invitation."}
        self.proposal = self.box.propose(**self.args)
        self.pid = self.proposal["proposal_id"]

    def approve(self):
        return self.box.decide(self.pid, self.proposal["arguments_sha256"], True)

    def execute(self, **changes):
        return self.box.execute(self.pid, **(self.args | changes))

    def test_missing_approval_blocks_send(self):
        self.assertEqual(self.execute()["status"], "rejected")
        self.assertEqual(self.box.sent(), [])

    def test_approval_allows_exactly_one_send(self):
        self.approve()
        self.assertEqual(self.execute()["status"], "mock_sent")
        self.assertEqual(self.execute()["status"], "rejected")
        self.assertEqual(len(self.box.sent()), 1)

    def test_denial_cannot_be_reapproved(self):
        self.box.decide(self.pid, self.proposal["arguments_sha256"], False)
        self.assertEqual(self.approve()["status"], "rejected")
        self.assertEqual(self.execute()["status"], "rejected")

    def test_changed_arguments_require_new_proposal(self):
        self.approve()
        for change in [{"to": "other@company.example"}, {"subject": "Changed"}, {"body": "Changed"}, {"account": "other"}]:
            self.assertEqual(self.execute(**change)["status"], "rejected")
        self.assertEqual(self.box.sent(), [])

    def test_expired_approval_cannot_execute(self):
        self.approve()
        self.now += 300
        self.assertEqual(self.execute()["status"], "rejected")

    def test_expired_proposal_cannot_be_approved(self):
        self.now += 300
        self.assertEqual(self.approve()["status"], "rejected")

    def test_wrong_digest_cannot_approve(self):
        self.assertEqual(self.box.decide(self.pid, "wrong", True)["status"], "rejected")

    def test_unknown_proposal_is_audited(self):
        self.assertEqual(self.box.execute("missing", **self.args)["status"], "rejected")
        self.assertEqual(self.box.audit()[-1]["event"], "execution_rejected")

    def test_real_addresses_are_rejected(self):
        with self.assertRaises(ValueError):
            self.box.propose(**(self.args | {"to": "someone@gmail.com"}))

    def test_audit_survives_restart(self):
        self.approve()
        self.execute()
        reopened = Mailbox(self.box.path)
        self.assertEqual([r["event"] for r in reopened.audit()], ["proposed", "approved", "mock_sent"])
        self.assertEqual(len(reopened.sent()), 1)

    def test_concurrent_execution_cannot_duplicate_send(self):
        self.approve()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: self.execute()["status"], range(4)))
        self.assertEqual(statuses.count("mock_sent"), 1)
        self.assertEqual(statuses.count("rejected"), 3)

    def test_audit_failure_rolls_back_send_and_consumption(self):
        self.approve()
        original = self.box.record
        def fail(*args):
            raise OSError("simulated audit failure")
        self.box.record = fail
        with self.assertRaises(OSError):
            self.execute()
        self.box.record = original
        self.assertEqual(self.box.sent(), [])
        self.assertEqual(self.box.inspect(self.pid)["status"], "approved")


if __name__ == "__main__":
    unittest.main()
