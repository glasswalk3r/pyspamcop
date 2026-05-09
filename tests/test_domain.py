import pytest
from pyspamcop.domain import (
    Message,
    UnrecoverableSpamReportMessage,
    MailHostMessage,
    EmailAddressBounceMessage,
    SpamHeaderMessage,
    WarningMessage,
    MailhostForgeryMessage,
    FreshSpamMessage,
    MessageAge,
    Receiver,
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
    ],
)
def test_domain_hierarchy(cls, parent):
    assert issubclass(cls, parent)


def test_message_init_type_error():
    with pytest.raises(ValueError, match="The messages parameter must be a list"):
        MailHostMessage("not a list")


@pytest.mark.parametrize(
    "cls, messages, expected_complete",
    [
        (MailHostMessage, ["Problem", "ignore", "Correct"], "Problem. Correct"),
        (SpamHeaderMessage, ["Failed"], "Failed"),
        (MailhostForgeryMessage, ["Forgery", "Trust"], "Forgery. Trust"),
        (FreshSpamMessage, ["Yum"], "Yum"),
    ],
)
def test_simple_messages(cls, messages, expected_complete):
    obj = cls(messages)
    assert obj.messages == tuple(messages)
    assert obj.complete_message() == expected_complete


@pytest.mark.parametrize(
    "cls, text, expected",
    [
        (MailHostMessage, "Mailhost configuration problem", True),
        (MailHostMessage, "Other", False),
        (EmailAddressBounceMessage, "Bounce error", True),
        (SpamHeaderMessage, "Failed to load spam header", True),
        (MailhostForgeryMessage, "Possible forgery", True),
        (FreshSpamMessage, "Yum", True),
    ],
)
def test_is_related(cls, text, expected):
    assert cls.is_related(text) == expected


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
