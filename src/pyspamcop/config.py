"""Configuration of the application."""

from importlib.metadata import version
from ruamel.yaml import YAML
from dataclasses import dataclass, field
from pyspamcop.exception import BaseExceptionError


def my_version():
    return version("pyspamcop")


@dataclass(slots=True, frozen=True)
class EmailAccount:
    name: str
    email: str
    password: str


@dataclass(slots=True)
class Configuration:
    automatic_confirmation: bool
    dry_run: bool
    verbosity: str
    db_path: str | None
    accounts: list[EmailAccount] = field(default_factory=list)

    def uses_db(self) -> bool:
        if self.db_path is not None and self.db_path != "":
            return True

        return False


class MissingAccountCfgError(BaseExceptionError):
    """Exception when there is no account configuration available."""

    def __init__(self, config_file: str):
        super().__init__(f"There is no configuration available in the {config_file} configuration file")


class InvalidCfgDirectiveError(BaseExceptionError):
    """Exception when an invalid configuration directive is used."""

    def __init__(self, directive: str):
        super().__init__(f"The directive '{directive}' is invalid, check documentation")


class MissingAccountCfgPropertyError(BaseExceptionError):
    """Exception when there is a missing account configuration option."""

    def __init__(self, option: str, provider: str):
        super().__init__(f"The option {option} is missing in the '{provider}' provider block")


class MissingCfgKeyError(BaseExceptionError):
    """Exception when a required configuration key is missing."""

    def __init__(self, key: str):
        super().__init__(f"The '{key}' key is missing from the configuration file")


def _validate_directives(data: dict) -> None:
    expected = set(["execution_options", "accounts"])

    for first_level_key in data:
        if first_level_key not in expected:
            raise InvalidCfgDirectiveError(first_level_key)

    expected = set(["automatic_confirmation", "dry_run", "verbosity", "database"])

    for exec_opt in data["execution_options"]:
        if exec_opt not in expected:
            raise InvalidCfgDirectiveError(exec_opt)


def read_config(config_file: str) -> Configuration:
    with open(config_file, "r") as fp:
        yaml = YAML(typ="safe")
        data = yaml.load(fp)

    try:
        _validate_directives(data)
    except KeyError as e:
        raise MissingCfgKeyError(e.args[0]) from e

    try:
        accounts_cfg = data["accounts"]
    except KeyError as e:
        raise MissingAccountCfgError(config_file) from e

    if not accounts_cfg:
        raise MissingAccountCfgError(config_file)

    accounts = []

    for provider in accounts_cfg:
        try:
            accounts.append(
                EmailAccount(
                    name=provider, email=accounts_cfg[provider]["email"], password=accounts_cfg[provider]["password"]
                ),
            )
        except KeyError as e:
            raise MissingAccountCfgPropertyError(option=str(e), provider=provider) from e

    try:
        exec_opts = data["execution_options"]
        database_cfg = exec_opts["database"]

        if database_cfg["enabled"] and database_cfg["path"] != "":
            db_path = database_cfg["path"]
        else:
            db_path = None

        config = Configuration(
            automatic_confirmation=exec_opts["automatic_confirmation"],
            dry_run=exec_opts["dry_run"],
            verbosity=exec_opts["verbosity"],
            db_path=db_path,
            accounts=accounts,
        )
    except KeyError as e:
        raise MissingCfgKeyError(e.args[0]) from e

    return config
