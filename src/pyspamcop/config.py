"""Configuration of the application."""

from importlib.metadata import version
from ruamel.yaml import YAML
from dataclasses import dataclass
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
    all_reports: bool
    automatic_confirmation: bool
    dry_run: bool
    verbosity: str
    db_path: str | None
    accounts: list[EmailAccount]

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


def _validate_directives(data: dict) -> None:
    expected = set(["execution_options", "accounts"])

    for first_level_key in data:
        if first_level_key not in expected:
            raise InvalidCfgDirectiveError(first_level_key)

    expected = set(["all_reports", "automatic_confirmation", "dry_run", "verbosity", "database"])

    for exec_opt in data["execution_options"]:
        if exec_opt not in expected:
            raise InvalidCfgDirectiveError(exec_opt)


def read_config(config_file: str) -> Configuration:
    with open(config_file, "r") as fp:
        yaml = YAML(typ="safe")
        data = yaml.load(fp)

    _validate_directives(data)

    accounts_cfg = data.get("accounts", None)

    if accounts_cfg is None or len(accounts_cfg) == 0:
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

    if (
        data.get("database", False)
        and data["database"].get("enabled", False)
        and data["database"].get("path", "") != ""
    ):
        db_path = data["database"]["path"]
    else:
        db_path = None

    config = Configuration(
        all_reports=data.get("all_reports", False),
        automatic_confirmation=data.get("automatic_configuration", False),
        dry_run=data.get("dry_run", False),
        verbosity=data.get("verbosity", "INFO"),
        db_path=db_path,
        accounts=accounts,
    )

    return config
