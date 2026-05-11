"""HTML parsing."""

import logging
import re
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from typing import Final
from pyspamcop.domain import (
    Message,
    MailHostMessage,
    SpamHeaderMessage,
    MailhostForgeryMessage,
    FreshSpamMessage,
    MessageAge,
    Receiver,
    EmailAddressBounceMessage,
)
from pyspamcop.exception import UnknownReceiverFormat

TARGET_HTML_FORM = "sendreport"
MAIL_TOO_OLD_REGEX: Final = re.compile(r"email\sis\stoo\sold")
NOTHING_REGEX: Final = re.compile(r"^Nothing")
SPAM_AGE_REGEX: Final = re.compile(r"^Message\sis\s(\d+)\s(\w+)\sold", re.MULTILINE)


def _messages_in(soup: BeautifulSoup, css_class: str, msg_types: list[type[Message]]) -> list[Message]:
    all_content = [tag for tag in soup.find_all(name="div", id="content")]
    messages: list[Message] = []

    for content in all_content:
        for tag in content.find_all(name="div", class_=css_class):
            message = tag.get_text()

            for error in msg_types:
                if error.is_related(message):
                    messages.append(error.html_extract(tag))
                    break

    return messages


def _errors_in_response(soup: BeautifulSoup) -> list[Message]:
    return _messages_in(soup=soup, css_class="error", msg_types=[MailHostMessage, SpamHeaderMessage])


def _errors_in_form(soup: BeautifulSoup) -> list[Message]:
    result = soup.find(name="strong")

    if result is not None and EmailAddressBounceMessage.is_related(result.get_text()):
        return [EmailAddressBounceMessage.html_extract(result)]

    return []


def find_errors(soup: BeautifulSoup) -> list[Message]:
    """Tries to find all errors on the HTML, based on CSS classes."""
    errors = _errors_in_response(soup)
    errors.extend(_errors_in_form(soup))
    return errors


def find_message_age(soup: BeautifulSoup) -> MessageAge | None:
    match = SPAM_AGE_REGEX.search(soup.get_text())

    if match:
        return MessageAge(int(match.group(1)), match.group(2).rstrip("s"))

    return None


def find_warnings(soup: BeautifulSoup) -> list[Message]:
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
            href = anchor.get(key="href", default=None)

            if (href is None) or (not isinstance(href, str)):
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

    if content_div is None:
        return info

    pre_nodes = content_div.find_all("pre", recursive=False)

    for node in pre_nodes:
        for line in node.get_text().splitlines():
            line = line.strip()

            if line == "":
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
                    info["content_type"] = value.rstrip(";")

            # Break early if both primary fields are found
            if info["mailer"] is not None and info["content_type"] is not None:
                return info

    return info


def find_receivers(soup: BeautifulSoup) -> list[Receiver]:
    """
    Finds information about where the SPAM reports were sent from the confirmation page.

    This function parses the post-submission confirmation HTML to extract the actual
    report destinations, unique SpamCop report IDs, and status (e.g., blackholed).
    This is an auditing step, unlike the legacy find_best_contacts which identifies
    reporting candidates on the analysis preview page.

    Args:
        soup: A BeautifulSoup object representing the parsed confirmation HTML page.

    Returns:
        A list of Receiver objects containing the reporting results.
    """
    receivers: list[Receiver] = []
    devnull = "/dev/null'ing"
    report_sent = "Spam report id"
    reports_disabled = "Reports disabled for"
    content_div = soup.find("div", id="content")
    logger = logging.getLogger(__name__)

    if content_div is None:
        return receivers

    for node in content_div.find_all(string=True):
        text = node.get_text(strip=True)

        if text == "":
            continue

        tokens = text.split(" ")

        if text.startswith(devnull):
            address = (tokens[-1].split("@"))[0]
            receivers.append(Receiver(address=address, devnull=True))
        elif text.startswith(report_sent):
            receivers.append(Receiver(address=tokens[6], report_id=tokens[3]))
        elif text.startswith(reports_disabled):
            receivers.append(Receiver(address=tokens[-1], disabled=True))
        else:
            logger.error("Unexpected receivers format: %s", text)
            logger.warning("Logging all HTML for debugging: %s", soup.prettify())
            raise UnknownReceiverFormat()

    return receivers


def find_best_contacts(soup: BeautifulSoup) -> list[str] | None:
    content_div = soup.find("div", id="content")

    if content_div is None:
        return None

    for node in content_div.find_all(string=True):
        text = node.get_text(strip=True)

        if text.startswith("Using best contacts"):
            tokens = text.split(" ")

            if len(tokens) == 0:
                return None

            return tokens[3:]

    return None


def report_form(soup: BeautifulSoup) -> dict[str, str] | None:
    form = soup.find("form", attrs={"name": "sendreport", "action": "/sc", "method": "post"})

    if form is None:
        return None

    data = {}

    for input in form.find_all("input", attrs={"type": "hidden"}):
        data[input["name"]] = input["value"]

    for input in form.find_all("input", attrs={"type": "checkbox"}):
        name = input["name"]

        if input.has_attr("checked"):
            data[name] = "on"
        else:
            data[name] = "off"

    for ta in form.find_all("textarea"):
        name = ta["name"]
        text = ta.string

        if text is None:
            data[name] = ""
        else:
            data[name] = text

    return data
