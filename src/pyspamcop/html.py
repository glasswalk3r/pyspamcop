"""HTML parsing."""

import logging
import re
from abc import ABC, abstractmethod, abstractclassmethod
from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import NavigableString
from typing import Final


MAIL_HOST_REGEX: Final = re.compile(r"Mailhost\sconfiguration\sproblem")  # TODO: might be replaced by startwith
BOUNCE_REGEX: Final = re.compile(r"bounce")
LOGIN_FAILED_REGEX: Final = re.compile(r"^Login\sfailed")
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
    def html_extract(cls, element: NavigableString) -> "Message":
        """Com um pouco de sorte, somente o div será necessário"""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{self.messages}"


class ErrorMessage(Message):
    """A message that represents an irrecoverable error.

    This means irrecoverable for the SPAM report being attempted. The only logic is to ignore it and move to the next
    pending report available for completion.
    """

    pass


class MailHostMessage(ErrorMessage):
    def __init__(self, messages: list[str]) -> None:
        super().__init__(messages)

    @classmethod
    def is_related(cls, message: str) -> bool:
        return MAIL_HOST_REGEX.match(message)

    @classmethod
    def html_extract(cls, element: NavigableString) -> "Message":
        messages = [element.get_text()]
        current = element.next_sibling

        while current and len(messages) < 3:
            if isinstance(current, NavigableString):
                text = current.strip()
                if text:
                    messages.append(text)
            current = current.next_sibling

        return MailHostMessage(messages)

    def complete_message(self) -> str:
        return f"{self.messages[0]}. {self.messages[-1]}"


class SpamHeaderMessage(ErrorMessage):
    def __init__(self, messages: list[str]) -> None:
        super().__init__(messages)

    @classmethod
    def is_related(cls, message: str) -> bool:
        return message.startswith("Failed to load spam header")

    @classmethod
    def html_extract(cls, element: NavigableString) -> "Message":
        return SpamHeaderMessage([element.get_text()])

    def complete_message(self) -> str:
        return self.messages[0]


def _messages_in(soup: BeautifulSoup, css_class: str, errors_types: list[ErrorMessage]) -> list[str]:
    logger = logging.getLogger(__name__)
    content = [tag for tag in soup.find_all(name="div", id="content")]

    if len(content) > 1:
        logger.warning("The HTML page should have only content div, but I got %d instead", len(content))
        logger.warning("Only the first result will be used")

    errors = []

    for tag in content[0].find_all(name="div", class_=css_class):
        message = tag.get_text()

        for error in errors_types:
            if error.is_related(message):
                errors.append(error.html_extract(tag))
                break

    return errors


def _errors_in_content(soup: BeautifulSoup) -> list[str]:
    return _messages_in(soup=soup, css_class="error", errors_types=[MailHostMessage, SpamHeaderMessage])


def _warnings_in_content(soup: BeautifulSoup) -> list[str]:
    return _messages_in(soup=soup, css_class="warning")


def _errors_in_form(soup: BeautifulSoup) -> list[str]:
    return []


def find_errors(soup: BeautifulSoup) -> list[str]:
    """Tries to find all errors on the HTML, based on CSS classes."""
    errors = _errors_in_content(soup)
    errors.extend(_errors_in_form(soup))
    return errors


@dataclass(slots=True)
class MessageAge:
    amount: int
    unit: str


def find_message_age(soup: BeautifulSoup) -> MessageAge | None:
    """Extract the spam age and time unit from the HTML content."""
    match = SPAM_AGE_REGEX.search(soup.get_text())

    if match:
        return MessageAge(int(match.group(1)), match.group(2).rstrip("s"))

    return None
