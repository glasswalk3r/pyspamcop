"""Implement features of the CLI."""

import logging
import os

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from pyspamcop.runner import run_account
from pyspamcop.config import read_config
from pyspamcop.http.client import HTTPClient


def run():
    parser = ArgumentParser(
        prog="pyspamcop",
        description="Web crawler for finishing SpamCop.net reports automatically",
        epilog="Options available here will have precedence of those declared in the configuration file",
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", help="Does nothing, just shows if you have unreported SPAM or not", action="store_true"
    )
    parser.add_argument("--auto-confirm", help="Runs without asking confirmation. Use with care", action="store_true")
    parser.add_argument(
        "--log-level",
        help="Verbosity level of information logged during program execution",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    parser.add_argument("--version", help="Show the program version and exit", action="store_true")
    parser.add_argument(
        "--config",
        help="The path to the configuration file",
        default=os.path.join(os.environ["HOME"], ".pyspamcop.yaml"),
    )
    args = parser.parse_args()

    config = read_config(args.config)

    if args.auto_confirm is not None:
        config.automatic_confirmation = True

    if args.log_level is not None:
        config.verbosity = args.log_level

    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=config.verbosity)

    run_account(client=HTTPClient(), config=config)
