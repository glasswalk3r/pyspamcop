import os

import pytest

from pyspamcop.html import find_errors


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
