"""Transactional mock mailbox; no credentials, network clients, or real delivery."""

import hashlib
from contextlib import contextmanager
import json
import sqlite3
import time
import uuid
from pathlib import Path


INBOX = [
    {"id": "welcome", "from": "organizer@club.example", "subject": "Partnership demo",
     "body": "Synthetic message: please share the club partnership overview."},
    {"id": "follow-up", "from": "partner@company.example", "subject": "Follow-up demo",
     "body": "Synthetic message: can we schedule a conversation next week?"},
]


def fingerprint(arguments):
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate(account, to, subject, body):
    if account != "demo":
        raise ValueError("Only the synthetic demo account exists")
    if not isinstance(to, str) or to.count("@") != 1 or not to.endswith(".example") or any(c.isspace() for c in to):
        raise ValueError("Use one synthetic recipient ending in .example")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 200 or "\n" in subject or "\r" in subject:
        raise ValueError("Subject must be a single line of 1-200 characters")
    if not isinstance(body, str) or not body.strip() or len(body) > 10000:
        raise ValueError("Body must contain 1-10000 characters")
    return {"tool": "send_mock_email", "account": account, "to": to, "subject": subject, "body": body}


class Mailbox:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, arguments TEXT NOT NULL, digest TEXT NOT NULL,
                    expires REAL NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sent (
                    proposal_id TEXT PRIMARY KEY, arguments TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL,
                    event TEXT NOT NULL, proposal_id TEXT, detail TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, db, event, proposal_id, detail):
        db.execute("INSERT INTO audit(created,event,proposal_id,detail) VALUES (?,?,?,?)",
                   (self.clock(), event, proposal_id, json.dumps(detail, sort_keys=True)))

    def propose(self, to, subject, body, account="demo"):
        args = validate(account, to, subject, body)
        proposal_id, expires = uuid.uuid4().hex, self.clock() + 300
        digest = fingerprint(args)
        with self.connect() as db:
            db.execute("INSERT INTO proposals VALUES (?,?,?,?,?)",
                       (proposal_id, json.dumps(args, ensure_ascii=False), digest, expires, "pending"))
            self.record(db, "proposed", proposal_id, {"arguments_sha256": digest})
        return {"proposal_id": proposal_id, "arguments": args, "arguments_sha256": digest,
                "expires_at": expires, "status": "pending"}

    def inspect(self, proposal_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown proposal")
        return {**dict(row), "arguments": json.loads(row["arguments"])}

    def decide(self, proposal_id, digest, approve):
        """Called by the local reviewer CLI; deliberately absent from MCP tools."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if row is None or row["status"] != "pending" or row["expires"] <= self.clock() or row["digest"] != digest:
                self.record(db, "decision_rejected", proposal_id, {"reason": "invalid, expired, or already decided"})
                return {"status": "rejected"}
            status = "approved" if approve else "denied"
            db.execute("UPDATE proposals SET status=? WHERE id=?", (status, proposal_id))
            self.record(db, status, proposal_id, {"arguments_sha256": digest, "reviewer": "local-terminal"})
            return {"status": status}

    def execute(self, proposal_id, to, subject, body, account="demo"):
        try:
            args = validate(account, to, subject, body)
        except ValueError as error:
            with self.connect() as db:
                self.record(db, "execution_rejected", proposal_id, {"reason": str(error)})
            return {"status": "rejected", "reason": str(error)}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if row is None:
                reason = "unknown proposal"
            elif row["expires"] <= self.clock():
                reason = "expired proposal; propose again"
            elif row["status"] != "approved":
                reason = "approval missing, denied, or already consumed"
            elif row["digest"] != fingerprint(args):
                reason = "arguments changed; propose again"
            else:
                db.execute("INSERT INTO sent VALUES (?,?,?)", (proposal_id, row["arguments"], self.clock()))
                db.execute("UPDATE proposals SET status='consumed' WHERE id=?", (proposal_id,))
                self.record(db, "mock_sent", proposal_id, {"arguments_sha256": row["digest"]})
                return {"status": "mock_sent", "proposal_id": proposal_id, "real_delivery": False}
            self.record(db, "execution_rejected", proposal_id, {"reason": reason})
            return {"status": "rejected", "reason": reason}

    def sent(self):
        with self.connect() as db:
            return [{"proposal_id": row["proposal_id"], "arguments": json.loads(row["arguments"])}
                    for row in db.execute("SELECT * FROM sent ORDER BY created, proposal_id")]

    def audit(self):
        with self.connect() as db:
            return [{**dict(row), "detail": json.loads(row["detail"])}
                    for row in db.execute("SELECT * FROM audit ORDER BY sequence")]
