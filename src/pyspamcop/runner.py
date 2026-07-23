"""Main report-processing loop."""

import logging
from time import sleep

from pyspamcop.config import Configuration
from pyspamcop.db import Recorder
from pyspamcop.domain import LoginFailedMessage, Summary, UnrecoverableSpamReportMessage
from pyspamcop.html import (
    parse_confirmation_page,
    parse_login_page,
    parse_report_page,
)
from pyspamcop.spamcop.client import ClientBase, LoginFailedError

logger = logging.getLogger(__name__)

NO_MORE_SPAM = -1
REPORT_ERROR = 0
REPORT_SUCCESS = 1

DELAY = 5


def main_loop(client: ClientBase, email: str, password: str, config: Configuration) -> int:
    """
    Runs one complete login → analyse → (optionally submit) cycle.

    Returns:
        REPORT_SUCCESS (1)  — a report was processed.
        REPORT_ERROR   (0)  — an error occurred; caller may continue to the next report.
        NO_MORE_SPAM   (-1) — no pending SPAM found; caller should stop looping.
    """
    logger = logging.getLogger(__name__)
    login_page = parse_login_page(client.login(email, password))

    for error in login_page.errors:
        if isinstance(error, LoginFailedMessage):
            raise LoginFailedError(error.complete_message())
        logger.error(error.complete_message())

    if login_page.next_id is None:
        logger.info("No unreported SPAM found for %s.", email)
        return NO_MORE_SPAM

    logger.info("Found pending SPAM ID: %s", login_page.next_id)
    logger.info("Sleeping for %s", DELAY)
    sleep(DELAY)

    report_page = parse_report_page(client.spam_report(login_page.next_id))

    for error in report_page.errors:
        logger.error(error.complete_message())

    if any(isinstance(e, UnrecoverableSpamReportMessage) for e in report_page.errors):
        logger.warning("Skipping report %s due to unrecoverable error.", login_page.next_id)
        return REPORT_ERROR

    for warning in report_page.warnings:
        logger.warning(warning.complete_message())

    if report_page.header:
        logger.info("From: %s | Subject: %s", report_page.header.sender, report_page.header.subject)

    if report_page.age:
        logger.info("Message age: %d %s(s)", report_page.age.amount, report_page.age.unit)

    if report_page.form is None:
        logger.error("Could not find the sendreport form for %s.", login_page.next_id)
        return REPORT_ERROR

    if config.dry_run:
        logger.info("Dry-run mode: skipping submission of report %s.", login_page.next_id)
        return REPORT_SUCCESS

    if not config.automatic_confirmation:
        answer = input(f"Submit SPAM report {login_page.next_id}? [y/N] ").strip().lower()
        if answer != "y":
            logger.info("Report %s cancelled by user.", login_page.next_id)
            return REPORT_ERROR

    logger.info("Sleeping for %s", DELAY)
    sleep(DELAY)

    receivers = parse_confirmation_page(client.confirm_report(report_page.form))

    for receiver in receivers:
        if receiver.devnull:
            logger.info("Report blackholed for %s", receiver.address)
        elif receiver.disabled:
            logger.info("Reports disabled for %s", receiver.address)
        else:
            logger.info("Report %s sent to %s", receiver.report_id, receiver.address)

    summary = Summary(
        tracking_id=login_page.next_id,
        header=report_page.header,
        age=report_page.age,
        receivers=receivers,
        contacts=report_page.contacts,
    )

    if config.uses_db():
        recorder = Recorder(config.db_path)  # type: ignore[arg-type]
        recorder.init()
        recorder.save(summary)
        logger.info("Summary for %s saved to database.", login_page.next_id)

    return REPORT_SUCCESS


def run_account(client: ClientBase, config: Configuration) -> None:
    """Run reports for a single account, looping if config.all_reports is set."""
    logger = logging.getLogger(__name__)

    for account in config.accounts:
        logger.info("Processing SPAM sent to %s", account.name)
        while True:
            result = main_loop(client, account.email, account.password, config)
            if result == NO_MORE_SPAM:
                break
            if result == REPORT_ERROR:
                logger.warning("Error processing report; moving to next.")

    return result
