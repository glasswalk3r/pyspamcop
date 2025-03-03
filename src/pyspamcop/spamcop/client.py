"""Base classes for interaction with SpamCop."""

from dataclasses import dataclass
from abc import abstractmethod
from pyspamcop.exception import BaseExceptionError


class LoginFailedError(BaseExceptionError):
    """Representation of a login attempt that failed.

    A login failed means there is a problem with your Spamcop account credentials.
    """

    def __init__(self, details: str) -> None:
        super().__init__(f"Your login attempt to SpamCop failed: {details}")
        self.details = details


@dataclass()
class ClientBase:
    name: str = "pyspamcop version"
    version: str = "0.1.0"

    @abstractmethod
    def login(self, email: str, password: str) -> str:
        """Login into the SpamCop website."""
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return if the instance is authenticated against SpamCop or not."""
        pass

    @abstractmethod
    def spam_report(self, report_id: str):
        """Retrieves a SPAM report.

        Expects as parameter a report ID."""
        pass

    @abstractmethod
    def confirm_report(self):
        """Complete the SPAM report, by confirming it's information is OK."""
        pass

    @abstractmethod
    def last_response(self) -> str:
        """Return the response data from the last interfaction with SpamCop."""
        pass
