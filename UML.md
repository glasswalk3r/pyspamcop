# UML Class Diagrams

Class diagrams for every class in `src/pyspamcop/`, grouped by module. Diagrams are kept per-module (rather than one
giant graph) for readability; cross-module relationships are called out in the prose above each diagram.

## Domain model — `Message` hierarchy (`domain.py`)

`Message` is the abstract base for everything parsed off a SpamCop page. It splits into two branches:
`UnrecoverableSpamReportMessage` (skip this report) and `WarningMessage` (report can still complete).

```mermaid
classDiagram
    class Message {
        <<abstract>>
        +messages: tuple~str~
        +__init__(messages: list~str~)
        +complete_message()* str
        +is_related(message: str)* bool
        +__repr__() str
    }
    class UnrecoverableSpamReportMessage
    class WarningMessage
    class MailHostMessage {
        +is_related(message: str) bool
        +complete_message() str
    }
    class EmailAddressBounceMessage {
        +__init__(messages: list~str~)
        +email() str
        +subject() str
        +reason() str
        +complete_message() str
        +is_related(message: str) bool
    }
    class SpamHeaderMessage {
        +is_related(message: str) bool
        +complete_message() str
    }
    class LoginFailedMessage {
        +is_related(message: str) bool
        +complete_message() str
    }
    class ReportsDisabledMessage {
        +is_related(message: str) bool
        +complete_message() str
    }
    class MailhostForgeryMessage {
        +is_related(message: str) bool
        +complete_message() str
    }
    class FreshSpamMessage {
        +is_related(message: str) bool
        +complete_message() str
    }

    Message <|-- UnrecoverableSpamReportMessage
    Message <|-- WarningMessage
    UnrecoverableSpamReportMessage <|-- MailHostMessage
    UnrecoverableSpamReportMessage <|-- EmailAddressBounceMessage
    UnrecoverableSpamReportMessage <|-- SpamHeaderMessage
    UnrecoverableSpamReportMessage <|-- LoginFailedMessage
    UnrecoverableSpamReportMessage <|-- ReportsDisabledMessage
    WarningMessage <|-- MailhostForgeryMessage
    WarningMessage <|-- FreshSpamMessage
```

## Domain model — report data (`domain.py`)

`Summary` aggregates everything collected during one complete SPAM report cycle.

```mermaid
classDiagram
    class MessageAge {
        +amount: int
        +unit: str
    }
    class Receiver {
        +address: str
        +report_id: str
        +devnull: bool
        +disabled: bool
        +id() str
    }
    class EmailHeader {
        +subject: str
        +sender: str
        +mailer: str
        +content_type: str
        +charset: str
        +__init__(sender: str, subject: str, mailer: str, content_type: str, charset: str)
    }
    class Summary {
        +tracking_id: str
        +header: EmailHeader
        +age: MessageAge
        +receivers: list~Receiver~
        +contacts: list~str~
        +tracking_url: str
    }

    Summary "1" o-- "0..1" EmailHeader : header
    Summary "1" o-- "0..1" MessageAge : age
    Summary "1" o-- "*" Receiver : receivers
```

## HTML parsing (`html.py`)

`LoginPage` and `ReportPage` are the parsed representations of the two SpamCop pages `parse_login_page()` and
`parse_report_page()` produce; `parse_confirmation_page()` returns a plain `list[Receiver]` (no dedicated wrapper
class). Both page types are populated with `Message` subclasses and the shared `EmailHeader`/`MessageAge` types from
`domain.py`.

```mermaid
classDiagram
    class LoginPage {
        +errors: list~Message~
        +next_id: str
    }
    class ReportPage {
        +errors: list~Message~
        +warnings: list~Message~
        +header: EmailHeader
        +age: MessageAge
        +contacts: list~str~
        +form: dict~str, str~
    }
    class Message {
        <<abstract>>
    }
    class EmailHeader
    class MessageAge

    LoginPage "1" o-- "*" Message : errors
    ReportPage "1" o-- "*" Message : errors/warnings
    ReportPage "1" o-- "0..1" EmailHeader : header
    ReportPage "1" o-- "0..1" MessageAge : age
```

## Configuration (`config.py`)

```mermaid
classDiagram
    class EmailAccount {
        +name: str
        +email: str
        +password: str
    }
    class Configuration {
        +automatic_confirmation: bool
        +dry_run: bool
        +verbosity: str
        +db_path: str
        +accounts: list~EmailAccount~
        +uses_db() bool
    }

    Configuration "1" o-- "*" EmailAccount : accounts
```

## SpamCop client abstraction (`spamcop/client.py`, `http/client.py`)

```mermaid
classDiagram
    class ClientBase {
        <<abstract>>
        +name: str
        +version: str
        +__init__()
        +login(email: str, password: str)* str
        +is_authenticated()* bool
        +spam_report(report_id: str)* str
        +confirm_report(form_data: dict~str, str~)* str
        +last_response()* str
    }
    class HTTPClient {
        +code_login_param: str
        +report_param: str
        +report_path: str
        +domain: str
        +form_login_path: str
        -__client: httpx.Client
        -__cookies: httpx.Cookies
        -__last_response: str
        +user_agent() str
        +login(email: str, password: str) str
        +is_authenticated() bool
        +spam_report(report_id: str) str
        +confirm_report(form_data: dict~str, str~) str
        +last_response() str
    }

    ClientBase <|-- HTTPClient
```

## Persistence (`db.py`)

`Recorder` persists a `Summary` to SQLite, normalizing repeated string values into small lookup tables. `LookupTable` is
a plain `(name, column)` pair; the module-level `_LOOKUP_TABLES` tuple of them drives both the schema DDL and the
runtime column lookup, so it is not tied to a single `Recorder` instance.

```mermaid
classDiagram
    class LookupTable {
        +name: str
        +column: str
    }
    class Recorder {
        -_db_path: str
        -_created: int
        -_conn: sqlite3.Connection
        +__init__(db_path: str, created: int)
        +init() bool
        +save(summary: Summary) bool
    }
    class Summary

    Recorder ..> Summary : save()
    Recorder ..> LookupTable : schema/lookups
```

## Report result (`runner.py`)

`ReportResult` is returned by `main_loop()` and `run_account()`, and consumed by `main.py` to print the outcome of
processing an account.


```mermaid
classDiagram
    class ReportResult {
        <<enumeration>>
        NO_MORE_SPAM
        REPORT_ERROR
        REPORT_SUCCESS
    }
```

## Exceptions (cross-cutting)

All custom exceptions in the package derive from `BaseExceptionError` (`exception.py`).

```mermaid
classDiagram
    class Exception
    class BaseExceptionError
    class UnknownReceiverFormat {
        +__init__()
    }
    class MissingAccountCfgError {
        +__init__(config_file: str)
    }
    class InvalidCfgDirectiveError {
        +__init__(directive: str)
    }
    class MissingAccountCfgPropertyError {
        +__init__(option: str, provider: str)
    }
    class MissingCfgKeyError {
        +__init__(key: str)
    }
    class LoginFailedError {
        +details: str
        +__init__(details: str)
    }
    class InvalidEmailError {
        +__init__()
    }
    class InvalidPasswordError {
        +__init__()
    }

    Exception <|-- BaseExceptionError
    BaseExceptionError <|-- UnknownReceiverFormat
    BaseExceptionError <|-- MissingAccountCfgError
    BaseExceptionError <|-- InvalidCfgDirectiveError
    BaseExceptionError <|-- MissingAccountCfgPropertyError
    BaseExceptionError <|-- MissingCfgKeyError
    BaseExceptionError <|-- LoginFailedError
    BaseExceptionError <|-- InvalidEmailError
    BaseExceptionError <|-- InvalidPasswordError
```

Defined in: `UnknownReceiverFormat` — `exception.py`; `MissingAccountCfgError`, `InvalidCfgDirectiveError`,
`MissingAccountCfgPropertyError`, `MissingCfgKeyError` — `config.py`; `LoginFailedError` — `spamcop/client.py`;
`InvalidEmailError`, `InvalidPasswordError` — `http/client.py`.
