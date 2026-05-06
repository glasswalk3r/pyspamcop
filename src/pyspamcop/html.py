"""HTML parsing."""

import logging
import re
from abc import ABC, abstractmethod, abstractclassmethod
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from typing import Final


MAIL_TOO_OLD_REGEX: Final = re.compile(r"email\sis\stoo\sold")
NOTHING_REGEX: Final = re.compile(r"^Nothing")
SPAM_AGE_REGEX: Final = re.compile(r"^Message\sis\s(\d+)\s(\w+)\sold", re.MULTILINE)


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

    @abstractclassmethod
    def is_related(cls, message: str) -> bool:
        pass

    @abstractclassmethod
    def html_extract(cls, element: Tag) -> "Message":
        """Com um pouco de sorte, somente o div será necessário"""
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

    @classmethod
    def html_extract(cls, element: Tag) -> "Message":
        messages = [element.get_text()]
        current = element.next_sibling

        while current and len(messages) < 3:
            if isinstance(current, NavigableString):
                text = current.strip()
                if text != "":
                    messages.append(text)
            current = current.next_sibling

        return MailHostMessage(messages)

    def complete_message(self) -> str:
        return f"{self.messages[0]}. {self.messages[-1]}"


EMAIL_BOUNCE_REGEX: Final[str] = re.compile(
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

    @classmethod
    def html_extract(cls, element: Tag) -> "Message":
        messages = []
        current = element.next_sibling

        while current and len(messages) < 3:
            if isinstance(current, NavigableString):
                text = current.strip()
                if text != "":
                    messages.append(text)
            current = current.next_sibling

        return EmailAddressBounceMessage(messages)


class SpamHeaderMessage(UnrecoverableSpamReportMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Failed to load spam header")

    @classmethod
    def html_extract(cls, element: Tag) -> "Message":
        return SpamHeaderMessage([element.get_text()])

    def complete_message(self) -> str:
        return self.messages[0]


class WarningMessage(Message):
    """Messages that are only warnings, but SPAM report can be completed."""

    pass


class MailhostForgeryMessage(WarningMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Possible forgery")

    @classmethod
    def html_extract(cls, element: Tag) -> "Message":
        messages = [element.get_text()]
        current = element.next_sibling

        while current and len(messages) < 2:
            if isinstance(current, NavigableString):
                text = current.strip()

                if text != "":
                    messages.append(text)

            current = current.next_sibling

        return MailhostForgeryMessage(messages)

    def complete_message(self) -> str:
        return ". ".join(self.messages)


class FreshSpamMessage(WarningMessage):
    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Yum")

    @classmethod
    def html_extract(cls, element: Tag) -> "Message":
        return FreshSpamMessage([element.get_text()])

    def complete_message(self) -> str:
        return self.messages[0]


def _messages_in(soup: BeautifulSoup, css_class: str, msg_types: list[Message]) -> list[str]:
    all_content = [tag for tag in soup.find_all(name="div", id="content")]
    messages = []

    for content in all_content:
        for tag in content.find_all(name="div", class_=css_class):
            message = tag.get_text()

            for error in msg_types:
                if error.is_related(message):
                    messages.append(error.html_extract(tag))
                    break

    return messages


def _errors_in_response(soup: BeautifulSoup) -> list[str]:
    return _messages_in(soup=soup, css_class="error", msg_types=[MailHostMessage, SpamHeaderMessage])


def _errors_in_form(soup: BeautifulSoup) -> list[str]:
    result = soup.find(name="strong")

    if result is not None and EmailAddressBounceMessage.is_related(result.get_text()):
        return [EmailAddressBounceMessage.html_extract(result)]

    return []


def find_errors(soup: BeautifulSoup) -> list[str]:
    """Tries to find all errors on the HTML, based on CSS classes."""
    errors = _errors_in_response(soup)
    errors.extend(_errors_in_form(soup))
    return errors


@dataclass(slots=True)
class MessageAge:
    amount: int
    unit: str


def find_message_age(soup: BeautifulSoup) -> MessageAge | None:
    match = SPAM_AGE_REGEX.search(soup.get_text())

    if match:
        return MessageAge(int(match.group(1)), match.group(2).rstrip("s"))

    return None


def find_warnings(soup: BeautifulSoup) -> list[str]:
    return _messages_in(soup=soup, css_class="warning", msg_types=[MailhostForgeryMessage, FreshSpamMessage])


def find_next_id(soup: BeautifulSoup) -> str | None:
    """
    Finds the next SPAM ID to be reported.

    It searches for an anchor tag that is a direct child of a strong tag:
    <strong><a href="...?id=VALUE">Report Now</a></strong>

    The function filters for links where the text content is "Report Now"
    (after stripping whitespace). If found, it parses the 'href' attribute
    to extract the value of the 'id' query parameter.
    """
    logger = logging.getLogger(__name__)

    for anchor in soup.select("strong > a"):
        link_text = anchor.get_text(strip=True).replace("\n", " ")

        if link_text == "Report Now":
            href = anchor.get("href")

            if href is None:
                continue

            parsed_url = urlparse(href)
            query_params = parse_qs(parsed_url.query)
            ids = query_params.get("id")

            if ids is not None:
                next_id = ids[0]
                length = len(next_id)
                expected = 45

                if length != expected:
                    logger.warning("Unexpected length for SPAM ID: got %d, expected %d", length, expected)

                return next_id

    return None


def find_header_info(soup: BeautifulSoup) -> dict[str, str | None]:
    """
    Finds information from the e-mail header of the received SPAM.

    It searches for <pre> tags within the <div id="content"> and parses
    headers like 'X-Mailer' and 'Content-Type'.

    Returns:
        A dictionary with keys 'mailer', 'content_type', and 'charset'.
    """
    info: dict[str, str | None] = {"mailer": None, "content_type": None, "charset": None}

    content_div = soup.find("div", id="content")
    if not content_div:
        return info

    # Matches XPath /html/body/div[@id="content"]/pre
    pre_nodes = content_div.find_all("pre", recursive=False)

    for node in pre_nodes:
        for line in node.get_text().splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("X-Mailer:"):
                info["mailer"] = line.split(":", 1)[1].strip()

            elif line.startswith("Content-Type:"):
                value = line.split(":", 1)[1].strip()
                parts = value.split(";")

                if len(parts) > 1:
                    encoding = parts[0].lower().strip()
                    charset_part = parts[1].lower().strip().replace('"', "")

                    info["content_type"] = encoding
                    if charset_part.startswith("boundary"):
                        info["charset"] = None
                    elif "=" in charset_part:
                        info["charset"] = charset_part.split("=", 1)[1].strip()
                else:
                    # Normalization: remove trailing semicolon if present
                    if value.endswith(";"):
                        value = value[:-1]
                    info["content_type"] = value

            # Break early if both primary fields are found
            if info["mailer"] and info["content_type"]:
                return info

    return info
