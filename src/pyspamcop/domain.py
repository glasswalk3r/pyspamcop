from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
from typing import Final
from time import time
from email.header import decode_header, make_header


class Message(ABC):
    """A message parsed from Spamcop webpage."""

    def __init__(self, messages: list[str]) -> None:

        if not isinstance(messages, list):
            raise ValueError(f"The messages parameter must be a list, not {messages.__class__.__name__}")

        self.messages = tuple([msg.strip() for msg in messages])

    @abstractmethod
    def complete_message(self) -> str:
        """A better formatted, single line message from all related messages."""
        pass

    @classmethod
    @abstractmethod
    def is_related(cls, message: str) -> bool:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{self.messages}"


class UnrecoverableSpamReportMessage(Message):
    """A message that represents an irrecoverable error for the SPAM report.

    This means irrecoverable for the SPAM report being attempted. The only logic is to ignore it and move to the next
    pending report available for completion.
    """

    pass


class MailHostMessage(UnrecoverableSpamReportMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Mailhost configuration problem")

    def complete_message(self) -> str:
        return f"{self.messages[0]}. {self.messages[-1]}"


EMAIL_BOUNCE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^Your\semail\saddress,\s([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\shas\sreturned\sa\sbounce"
)


class EmailAddressBounceMessage(UnrecoverableSpamReportMessage):
    def __init__(self, messages: list[str]) -> None:

        if len(messages) != 3:
            raise ValueError("Three messages are required for a bounce notification")

        messages[0] = messages[0].replace(":", "")
        messages[2] = messages[2].replace("'", "")
        super().__init__(messages)

    def email(self) -> str:
        result = re.match(EMAIL_BOUNCE_REGEX, self.messages[0])

        if result is not None:
            return result.group(1).strip()

        raise ValueError(f"{EMAIL_BOUNCE_REGEX} does not match {self.messages[0]}")

    def subject(self) -> str:
        return self.messages[1].split(":")[-1].strip()

    def reason(self) -> str:
        return self.messages[2].split(": ")[-1].strip().lower().replace("dns", "DNS").replace("=", "")

    def complete_message(self) -> str:
        return f"{self.email()} has returned a bounce due {self.reason()}"

    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Bounce error")


class SpamHeaderMessage(UnrecoverableSpamReportMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Failed to load spam header")

    def complete_message(self) -> str:
        return self.messages[0]


class LoginFailedMessage(UnrecoverableSpamReportMessage):
    """Login attempt to SpamCop was rejected — credentials are invalid."""

    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Login failed")

    def complete_message(self) -> str:
        return self.messages[0]


class ReportsDisabledMessage(UnrecoverableSpamReportMessage):
    """SpamCop has disabled reports for a specific address on this report."""

    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Reports disabled for")

    def complete_message(self) -> str:
        return self.messages[0]


class WarningMessage(Message):
    """Messages that are only warnings, but SPAM report can be completed."""

    pass


class MailhostForgeryMessage(WarningMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Possible forgery")

    def complete_message(self) -> str:
        return ". ".join(self.messages)


class FreshSpamMessage(WarningMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Yum")

    def complete_message(self) -> str:
        return self.messages[0]


@dataclass(slots=True)
class MessageAge:
    """
    Represents the age of a spam message as parsed from SpamCop's analysis.

    It is used to determine if a message is still eligible for reporting.
    """

    amount: int
    unit: str


@dataclass(slots=True)
class Receiver:
    """
    Represents a destination or entity that receives a SPAM report.

    It tracks the specific recipient address, the resulting SpamCop report ID,
    and whether the report was successfully sent, blackholed, or if reporting is disabled.
    """

    address: str
    report_id: str | None = None
    devnull: bool = False
    disabled: bool = False

    def id(self) -> str:
        if self.report_id is not None:
            return self.report_id

        return f"N/A-{time()}"


class EmailHeader:
    """Representation of the e-mail header.

    The sender attribute would be probably better if named "from", but this is a reserved word.
    """

    def __init__(
        self, sender: str, subject: str, mailer: str | None, content_type: str | None, charset: str | None
    ) -> None:
        if subject is None or subject == "":
            raise ValueError("The subject parameter must be a non-empty string or a RFC2047 encoded-words")

        if sender is None or sender == "":
            raise ValueError("The sender parameter must be a non-empty string or a RFC2047 encoded-words")

        self.subject = str(make_header(decode_header(subject)))
        self.sender = str(make_header(decode_header(sender)))

        self.mailer = mailer
        self.content_type = content_type
        self.charset = charset


@dataclass
class Summary:
    """Aggregates all metadata collected during one complete SPAM report cycle."""

    tracking_id: str
    header: EmailHeader | None = None
    age: MessageAge | None = None
    receivers: list[Receiver] = field(default_factory=list)
    contacts: list[str] = field(default_factory=list)

    @property
    def tracking_url(self) -> str:
        return f"https://www.spamcop.net/sc?id={self.tracking_id}"
