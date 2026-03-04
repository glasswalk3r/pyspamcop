"""Implement features of the CLI."""

import logging

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

parser = ArgumentParser(
    prog="pyspamcop",
    description="Web crawler for finishing SpamCop.net reports automatically",
    epilog="Options available here will have precedence of those declared in the configuration file",
    formatter_class=ArgumentDefaultsHelpFormatter,
)
parser.add_argument(
    "--dry-run", help="Does nothing, just shows if you have unreported SPAM or not", action="store_true"
)
parser.add_argument("--all", help="Run in a loop until all SPAM is reported", action="store_true")
parser.add_argument("--auto-confirm", help="Runs without asking confirmation. Use with care", action="store_true")
parser.add_argument(
    "--log-level",
    help="Verbosity level of information logged during program execution",
    choices=("DEBUG", "INFO", "WARNING", "ERROR"),
)
parser.add_argument("--version", help="Show the program version and exit", action="store_true")
parser.add_argument("--config", help="The path to the configuration file", default="~/.pyspamcop.yaml")
args = parser.parse_args()
logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=args.log_level)
