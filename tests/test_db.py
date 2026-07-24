import sqlite3

import pytest

from pyspamcop.db import Recorder, _upsert_lookup
from pyspamcop.domain import EmailHeader, MessageAge, Receiver, Summary


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE mailer (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    yield connection
    connection.close()


@pytest.fixture
def recorder():
    rec = Recorder(":memory:", created=1_700_000_000)
    rec.init()
    return rec


@pytest.fixture
def header() -> EmailHeader:
    return EmailHeader(
        sender="reporter@example.com",
        subject="Fresh spam",
        mailer="Some MTA",
        content_type="text/plain",
        charset="utf-8",
    )


@pytest.fixture
def summary(header) -> Summary:
    return Summary(
        tracking_id="TRACK123",
        header=header,
        age=MessageAge(amount=5, unit="hours"),
        receivers=[
            Receiver(address="abuse@example.com", report_id="REPORT1"),
            Receiver(address="abuse@example.net", report_id="REPORT2"),
        ],
    )


def test_upsert_lookup_inserts_new_row(conn):
    result_id = _upsert_lookup(conn, table="mailer", value="Postfix")
    row = conn.execute("SELECT id, name FROM mailer WHERE id = ?", (result_id,)).fetchone()
    assert row == (result_id, "Postfix")


def test_upsert_lookup_is_idempotent(conn):
    first_id = _upsert_lookup(conn, table="mailer", value="Postfix")
    second_id = _upsert_lookup(conn, table="mailer", value="Postfix")
    assert first_id == second_id
    count = conn.execute("SELECT COUNT(*) FROM mailer WHERE name = 'Postfix'").fetchone()[0]
    assert count == 1


@pytest.mark.parametrize(
    "table, column, value",
    [
        ("email_content_type", "name", "text/plain"),
        ("spam_age_unit", "name", "hours"),
        ("email_charset", "name", "utf-8"),
        ("mailer", "name", "Postfix"),
        ("receiver", "email", "abuse@example.com"),
    ],
)
def test_upsert_lookup_for_every_lookup_table(recorder, table, column, value):
    conn = recorder._conn
    result_id = _upsert_lookup(conn, table, value)
    row = conn.execute(f"SELECT id, {column} FROM {table} WHERE id = ?", (result_id,)).fetchone()
    assert row == (result_id, value)

    # calling it again with the same value must not create a duplicate row
    assert _upsert_lookup(conn, table, value) == result_id
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert count == 1


def test_recorder_init_creates_schema():
    rec = Recorder(":memory:")
    assert rec.init() is True

    tables = {row[0] for row in rec._conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    assert tables == {
        "email_content_type",
        "spam_age_unit",
        "email_charset",
        "mailer",
        "receiver",
        "summary",
        "summary_receiver",
        "sqlite_sequence",
    }


def test_recorder_save_before_init_raises():
    rec = Recorder(":memory:")
    with pytest.raises(RuntimeError, match=r"Recorder\.init\(\) must be called before save\(\)"):
        rec.save(Summary(tracking_id="TRACK123"))


def test_recorder_save_full_summary(recorder, summary):
    assert recorder.save(summary) is True

    conn = recorder._conn
    row = conn.execute(
        """
        SELECT tracking_id, created, charset_id, content_type_id, age, age_unit_id, mailer_id
        FROM summary WHERE tracking_id = ?
        """,
        (summary.tracking_id,),
    ).fetchone()
    assert row[0] == "TRACK123"
    assert row[1] == 1_700_000_000
    assert row[4] == 5

    charset = conn.execute("SELECT name FROM email_charset WHERE id = ?", (row[2],)).fetchone()[0]
    content_type = conn.execute("SELECT name FROM email_content_type WHERE id = ?", (row[3],)).fetchone()[0]
    age_unit = conn.execute("SELECT name FROM spam_age_unit WHERE id = ?", (row[5],)).fetchone()[0]
    mailer = conn.execute("SELECT name FROM mailer WHERE id = ?", (row[6],)).fetchone()[0]
    assert charset == "utf-8"
    assert content_type == "text/plain"
    assert age_unit == "hours"
    assert mailer == "Some MTA"

    receivers = conn.execute(
        """
        SELECT r.email, sr.report_id
        FROM summary_receiver sr
        JOIN receiver r ON r.id = sr.receiver_id
        JOIN summary s ON s.id = sr.summary_id
        WHERE s.tracking_id = ?
        ORDER BY r.email
        """,
        (summary.tracking_id,),
    ).fetchall()
    assert receivers == [("abuse@example.com", "REPORT1"), ("abuse@example.net", "REPORT2")]


def test_recorder_save_minimal_summary(recorder):
    minimal = Summary(tracking_id="TRACKMIN")

    assert recorder.save(minimal) is True

    conn = recorder._conn
    row = conn.execute(
        """
        SELECT tracking_id, charset_id, content_type_id, age, age_unit_id, mailer_id
        FROM summary WHERE tracking_id = ?
        """,
        (minimal.tracking_id,),
    ).fetchone()
    assert row == ("TRACKMIN", None, None, None, None, None)

    receiver_count = conn.execute(
        """
        SELECT COUNT(*) FROM summary_receiver sr
        JOIN summary s ON s.id = sr.summary_id
        WHERE s.tracking_id = ?
        """,
        (minimal.tracking_id,),
    ).fetchone()[0]
    assert receiver_count == 0


def test_recorder_save_is_idempotent(recorder, summary):
    assert recorder.save(summary) is True
    assert recorder.save(summary) is True

    conn = recorder._conn
    summary_count = conn.execute(
        "SELECT COUNT(*) FROM summary WHERE tracking_id = ?", (summary.tracking_id,)
    ).fetchone()[0]
    assert summary_count == 1

    receiver_rows = conn.execute("SELECT COUNT(*) FROM summary_receiver").fetchone()[0]
    assert receiver_rows == 2

    email_count = conn.execute("SELECT COUNT(*) FROM receiver WHERE email = 'abuse@example.com'").fetchone()[0]
    assert email_count == 1


def test_recorder_save_shares_receiver_across_summaries(recorder, header):
    first = Summary(tracking_id="TRACK1", header=header, receivers=[Receiver(address="abuse@example.com")])
    second = Summary(tracking_id="TRACK2", header=header, receivers=[Receiver(address="abuse@example.com")])

    recorder.save(first)
    recorder.save(second)

    conn = recorder._conn
    receiver_ids = conn.execute("SELECT id FROM receiver WHERE email = 'abuse@example.com'").fetchall()
    assert len(receiver_ids) == 1

    summary_receiver_count = conn.execute("SELECT COUNT(*) FROM summary_receiver").fetchone()[0]
    assert summary_receiver_count == 2
