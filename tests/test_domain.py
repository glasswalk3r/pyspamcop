import pytest
from pyspamcop.domain import (
    Message,
    UnrecoverableSpamReportMessage,
    MailHostMessage,
    EmailAddressBounceMessage,
    SpamHeaderMessage,
    LoginFailedMessage,
    ReportsDisabledMessage,
    WarningMessage,
    MailhostForgeryMessage,
    FreshSpamMessage,
    MessageAge,
    Receiver,
    Summary,
)


@pytest.mark.parametrize(
    "cls, parent",
    [
        (UnrecoverableSpamReportMessage, Message),
        (MailHostMessage, UnrecoverableSpamReportMessage),
        (EmailAddressBounceMessage, UnrecoverableSpamReportMessage),
        (SpamHeaderMessage, UnrecoverableSpamReportMessage),
        (WarningMessage, Message),
        (MailhostForgeryMessage, WarningMessage),
        (FreshSpamMessage, WarningMessage),
        (LoginFailedMessage, UnrecoverableSpamReportMessage),
        (ReportsDisabledMessage, UnrecoverableSpamReportMessage),
    ],
)
def test_domain_hierarchy(cls, parent):
    assert issubclass(cls, parent)


def test_message_init_type_error():
    with pytest.raises(ValueError, match="The messages parameter must be a list"):
        MailHostMessage("not a list")


def _padded(messages):
    """Same messages surrounded by the kind of whitespace left over from HTML parsing."""
    return [f"  \n\t{msg} \n " for msg in messages]


# Fragments extracted from tests/fixtures/mailhost_problem.html
MAILHOST_MESSAGES = [
    "Mailhost configuration problem, identified internal IP as source",
    "Mailhost:",
    "Please correct this situation - register every email address where you receive spam",
]


@pytest.mark.parametrize("messages", [MAILHOST_MESSAGES, _padded(MAILHOST_MESSAGES)], ids=["fixture", "padded"])
def test_mailhost_message(messages):
    obj = MailHostMessage(messages)
    assert obj.messages == tuple(MAILHOST_MESSAGES)
    assert obj.complete_message() == (
        "Mailhost configuration problem, identified internal IP as source. "
        "Please correct this situation - register every email address where you receive spam"
    )


# Fragment extracted from tests/fixtures/failed_load_header.html
SPAM_HEADER_MESSAGES = ["Failed to load spam header: 64446486 / cebd6f7e464abe28f4afffb9d"]


@pytest.mark.parametrize("messages", [SPAM_HEADER_MESSAGES, _padded(SPAM_HEADER_MESSAGES)], ids=["fixture", "padded"])
def test_spam_header_message(messages):
    obj = SpamHeaderMessage(messages)
    assert obj.messages == tuple(SPAM_HEADER_MESSAGES)
    assert obj.complete_message() == "Failed to load spam header: 64446486 / cebd6f7e464abe28f4afffb9d"


# Fragments extracted from tests/fixtures/mailhost_problem.html (also in sendreport_form_ok.html)
FORGERY_MESSAGES = [
    "Possible forgery. Supposed receiving system not associated with any of your mailhosts",
    "Will not trust this Received line.",
]


@pytest.mark.parametrize("messages", [FORGERY_MESSAGES, _padded(FORGERY_MESSAGES)], ids=["fixture", "padded"])
def test_mailhost_forgery_message(messages):
    obj = MailhostForgeryMessage(messages)
    assert obj.messages == tuple(FORGERY_MESSAGES)
    assert obj.complete_message() == (
        "Possible forgery. Supposed receiving system not associated with any of your mailhosts. "
        "Will not trust this Received line."
    )


# Fragment extracted from tests/fixtures/sendreport_form_ok.html (also in missing_sendreport_form.html)
FRESH_SPAM_MESSAGES = ["Yum, this spam is fresh!"]


@pytest.mark.parametrize("messages", [FRESH_SPAM_MESSAGES, _padded(FRESH_SPAM_MESSAGES)], ids=["fixture", "padded"])
def test_fresh_spam_message(messages):
    obj = FreshSpamMessage(messages)
    assert obj.messages == tuple(FRESH_SPAM_MESSAGES)
    assert obj.complete_message() == "Yum, this spam is fresh!"


@pytest.mark.parametrize(
    "cls, text, expected",
    [
        (MailHostMessage, "Mailhost configuration problem", True),
        (MailHostMessage, "Other", False),
        (EmailAddressBounceMessage, "Bounce error", True),
        (SpamHeaderMessage, "Failed to load spam header", True),
        (MailhostForgeryMessage, "Possible forgery", True),
        (FreshSpamMessage, "Yum", True),
        (LoginFailedMessage, "Login failed, please try again", True),
        (LoginFailedMessage, "Something else", False),
        (ReportsDisabledMessage, "Reports disabled for user@example.com", True),
        (ReportsDisabledMessage, "Something else", False),
    ],
)
def test_is_related(cls, text, expected):
    assert cls.is_related(text) == expected


def test_login_failed_message():
    obj = LoginFailedMessage(["Login failed, please try again (is your caps-lock on?)"])
    assert obj.complete_message() == "Login failed, please try again (is your caps-lock on?)"


def test_reports_disabled_message():
    obj = ReportsDisabledMessage(["Reports disabled for user@example.com"])
    assert obj.complete_message() == "Reports disabled for user@example.com"


def test_summary_defaults():
    s = Summary(tracking_id="abc123")
    assert s.header is None
    assert s.age is None
    assert s.receivers == []
    assert s.contacts == []


def test_summary_tracking_url():
    s = Summary(tracking_id="z6731356012zdc1bc09296ac2635b0861f61911073e5z")
    assert s.tracking_url == "https://www.spamcop.net/sc?id=z6731356012zdc1bc09296ac2635b0861f61911073e5z"


def test_email_bounce_message():
    msgs = [
        "Your email address, user@example.com has returned a bounce:",
        "Subject: Test",
        "Reason: '5.0.0 dns Soft Error='",
    ]
    obj = EmailAddressBounceMessage(msgs)
    assert obj.email() == "user@example.com"
    assert obj.subject() == "Test"
    assert obj.reason() == "5.0.0 DNS soft error"
    assert obj.complete_message() == "user@example.com has returned a bounce due 5.0.0 DNS soft error"


def test_email_bounce_errors():
    with pytest.raises(ValueError, match="Three messages are required"):
        EmailAddressBounceMessage(["one", "two"])
    obj = EmailAddressBounceMessage(["Invalid", "Subject: x", "Reason: y"])
    with pytest.raises(ValueError, match="does not match"):
        obj.email()


def test_message_age():
    age = MessageAge(amount=10, unit="days")
    assert age.amount == 10
    assert age.unit == "days"


def test_receiver():
    r1 = Receiver(address="admin@example.com", report_id="999")
    assert r1.address == "admin@example.com"
    assert r1.report_id == "999"
    assert r1.id() == "999"
    r2 = Receiver(address="blackhole", devnull=True)
    assert r2.devnull is True
    assert r2.id().startswith("N/A-")
