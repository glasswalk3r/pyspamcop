import os

import pytest

from pyspamcop.html import find_errors, find_message_age, MessageAge


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
    ),
)
def test_find_errors(filename, messages, formatted):
    with open(os.path.join("tests", "fixtures", filename), "r") as fp:
        result = find_errors(fp.read())

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].messages == messages
    assert result[0].complete_message() == formatted


def read_fixture(filename):
    """Helper para carregar o HTML da fixture."""
    import os

    path = os.path.join("tests", "fixtures", filename)
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()


def test_find_message_age_ok():
    result = find_message_age(read_fixture("sendreport_form_ok.html"))
    assert isinstance(result, MessageAge)
    assert result.amount == 2
    assert result.unit == "hour"


def test_find_message_age_not_found():
    html_empty = "<html><body>No info here</body></html>"
    result = find_message_age(html_empty)
    assert result is None
