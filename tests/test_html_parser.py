import os

import pytest

from bs4 import BeautifulSoup

from pyspamcop.html import (
    find_errors,
    find_message_age,
    MessageAge,
    find_warnings,
    find_next_id,
    find_header_info,
    find_receivers,
    Receiver,
    find_best_contacts,
)


def read_fixture(filename):
    path = os.path.join("tests", "fixtures", filename)
    with open(path, "r", encoding="utf-8") as fp:
        return BeautifulSoup(fp.read(), "html.parser")


@pytest.mark.parametrize(
    "filename, messages, formatted",
    (
        (
            "failed_load_header.html",
            ("Failed to load spam header: 64446486 / cebd6f7e464abe28f4afffb9d",),
            "Failed to load spam header: 64446486 / cebd6f7e464abe28f4afffb9d",
        ),
        (
            "mailhost_problem.html",
            (
                "Mailhost configuration problem, identified internal IP as source",
                "Mailhost:",
                "Please correct this situation - register every email address where you receive spam",
            ),
            "Mailhost configuration problem, identified internal IP as source. Please correct this situation - register every email address where you receive spam",
        ),
        (
            "bounce_error.html",
            (
                "Your email address, glasswalk3r@yahoo.com.br has returned a bounce",
                "Subject: Delivery Status Notification (Failure)",
                "Reason: 5.4.7 - Delivery expired (message too old) DNS Soft Error looking up yahoo=",
            ),
            "glasswalk3r@yahoo.com.br has returned a bounce due 5.4.7 - delivery expired (message too old) DNS soft error looking up yahoo",
        ),
    ),
)
def test_find_errors(filename, messages, formatted):
    result = find_errors(read_fixture(filename))
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].messages == messages
    assert result[0].complete_message() == formatted


def test_find_message_age_ok():
    result = find_message_age(read_fixture("sendreport_form_ok.html"))
    assert isinstance(result, MessageAge)
    assert result.amount == 2
    assert result.unit == "hour"


def test_find_message_age_not_found():
    html_empty = "<html><body>No info here</body></html>"
    result = find_message_age(BeautifulSoup(html_empty, "html.parser"))
    assert result is None


def test_find_warnings_success():
    result = find_warnings(read_fixture("sendreport_form_ok.html"))
    assert len(result) == 2
    assert result[0].messages == (
        "Possible forgery. Supposed receiving system not associated with any of your mailhosts",
        "Will not trust this Received line.",
    )

    assert result[1].messages == ("Yum, this spam is fresh!",)


@pytest.mark.parametrize(
    "expected_id, filename",
    (("z6444645586z5cebd61f7e0464abe28f045afff01b9dz", "after_login.html"), (None, "failed_load_header.html")),
)
def test_find_next_id(expected_id, filename):
    result = find_next_id(read_fixture(filename))

    if expected_id is None:
        assert result is None
        return

    assert result == expected_id


@pytest.mark.parametrize(
    "filename, expected",
    (
        ("sendreport_form_ok.html", {"mailer": "Smart_Send_4_4_2", "content_type": "multipart/mixed", "charset": None}),
        ("missing_sendreport_form.html", {"mailer": None, "content_type": "multipart/alternative", "charset": "utf-8"}),
        ("boundary.html", {"mailer": None, "content_type": "multipart/alternative", "charset": None}),
    ),
)
def test_find_header_info(filename, expected):
    result = find_header_info(read_fixture(filename))
    assert isinstance(result, dict)

    for key in ("mailer", "content_type", "charset"):
        if expected[key] is None:
            assert result[key] is None
            continue

        assert result[key] == expected[key]


def test_find_receivers():
    result = find_receivers(read_fixture("post_reporting.html"))
    assert isinstance(result, list)
    assert len(result) == 4
    assert result == [
        Receiver(address="google-abuse-bounces-reports", devnull=True),
        Receiver(address="dl_security_whois@navercorp.com", report_id="7151980235"),
        Receiver(address="deliverabilityteam#epsilon.com", devnull=True),
        Receiver(address="johndoe@foobar.net", disabled=True),
    ]


@pytest.mark.parametrize(
    "filename, expected",
    (("sendreport_form_ok.html", None), ("missing_sendreport_form.html", ["abuse@ovh.net", "noc@ovh.net"])),
)
def test_find_best_contacts(filename, expected):
    result = find_best_contacts(read_fixture(filename))

    if expected is None:
        assert result is None
    else:
        assert result == expected
