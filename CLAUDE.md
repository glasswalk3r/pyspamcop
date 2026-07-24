# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

pyspamcop is a Python web crawler that automates finishing [SpamCop.net](https://www.spamcop.net) spam reports. It logs into the SpamCop website, fetches pending reports, parses the HTML, and submits confirmations — sequentially, with forced delays to be polite.

The project is a rewrite of the Perl-based [App-SpamcupNG](https://github.com/glasswalk3r/App-SpamcupNG). The original Perl code is kept under `legacy/` for reference.

## Environment setup

Uses `uv` for dependency management and Python 3.12.

```bash
make init      # create venv and install all deps (uv venv && uv sync)
```

## Commands

```bash
make lint           # ruff check --fix && ruff format && mypy
make unit           # pytest (excluding integration tests)
make integration    # pytest -m integration
make coverage       # pytest --cov=pyspamcop tests/
make clean          # remove build/test/cache artifacts
```

Run a single test file:
```bash
python -m pytest tests/test_html_parser.py -v
```

Run a single test by name:
```bash
python -m pytest tests/test_html_parser.py -k "test_find_errors" -v
```

## Architecture

```
src/pyspamcop/
  main.py          # CLI entry point (argparse); entrypoint is pyspamcop:main; log_config() sets up logging
  runner.py        # main_loop()/run_account(): the login -> analyse -> confirm -> record cycle
  db.py            # Recorder: SQLite persistence of Summary objects (see Key design patterns)
  config.py        # YAML config loading; Configuration + EmailAccount dataclasses
  domain.py        # All domain models: Message hierarchy, Receiver, EmailHeader, MessageAge, Summary
  html.py          # BeautifulSoup HTML parsers: find_errors, find_warnings, find_receivers,
                   # find_next_id, find_header, find_best_contacts, report_form
  exception.py     # BaseExceptionError and UnknownReceiverFormat
  http/client.py   # HTTPClient: concrete httpx-based implementation of ClientBase
  spamcop/client.py # ClientBase: abstract base class for the SpamCop HTTP session
```

### Key design patterns

**Message hierarchy** (`domain.py`): `Message` is an abstract base class with two branches — `UnrecoverableSpamReportMessage` (skip this report, move on) and `WarningMessage` (report can still complete). Concrete types include `MailHostMessage`, `EmailAddressBounceMessage`, `SpamHeaderMessage`, `MailhostForgeryMessage`, and `FreshSpamMessage`. Each implements `is_related(text)`, `extract(tag)`, and `complete_message()`.

**HTML parsing** (`html.py`): All SpamCop page parsing lives here as standalone functions taking a `BeautifulSoup` object. Tests use HTML fixtures from `tests/fixtures/` rather than live HTTP calls. `find_best_contacts` identifies reporting candidates on the analysis preview page; `find_receivers` parses the post-submission confirmation page.

**Client abstraction** (`spamcop/client.py` + `http/client.py`): `ClientBase` defines the abstract interface (`login`, `is_authenticated`, `spam_report`, `confirm_report`, `last_response`). `HTTPClient` extends it using `httpx`. Several methods on `HTTPClient` are still stubs (`spam_report`, `confirm_report`, `last_response`).

**Lookup-table registry** (`db.py`): `Recorder` persists a `Summary` to SQLite, normalizing repeated string values (email content type, spam age unit, charset, mailer, receiver address) into small reference tables via a get-or-create pattern (`_upsert_lookup`, using `INSERT OR IGNORE` + `SELECT` against each table's `UNIQUE` column). The table/column pairs are declared exactly once, in the `_LOOKUP_TABLES` tuple of `LookupTable(name, column)` — both the `CREATE TABLE` DDL (`_SCHEMA`) and the runtime column lookup (`_LOOKUP_COLUMN`) are derived from it, so schema and code can't drift apart. Add a new lookup table by adding one `LookupTable` entry, not by editing DDL and code separately.

### Configuration file

Default path: `~/.pyspamcop.yaml` (override with `--config`). Schema documented in `README.md`. Parsed by `read_config()` in `config.py`.

### Test conventions

- Unit tests use HTML fixtures in `tests/fixtures/` loaded via `read_fixture()` helper.
- Integration tests are marked `@pytest.mark.integration` and excluded from `make unit`.
- Tests run from the project root; fixture paths are relative (`tests/fixtures/...`).
