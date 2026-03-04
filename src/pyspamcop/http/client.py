"""Implementation of the SpamCop client with HTTP."""

from pyspamcop.spamcop.client import ClientBase
import httpx
from pyspamcop.exception import BaseExceptionError


class InvalidEmailError(BaseExceptionError):
    """Exception when a provided email address is invalid."""

    def __init__(self):
        super().__init__("The provided email address in invalid")


class InvalidPasswordError(BaseExceptionError):
    """Exception when a provided password is invalid."""

    def __init__(self):
        super().__init__("The provided password in invalid")


class HTTPClient(ClientBase):
    def __init__(self) -> None:
        super().__init__()
        self.code_login_param: str = "code"
        self.report_param: str = "id"
        self.report_path: str = "sc"
        self.domain: str = "www.spamcop.net"
        self.form_login_path: str = "mcgi"
        self.__client: httpx.Client = httpx.Client(headers={"user-agent": self.user_agent()}, follow_redirects=True)
        self.__cookies: dict[str, str] | None = None

    def user_agent(self) -> str:
        """Return the HTTP user-agent header value used in interactions with SpamCop."""
        return f"{self.name} {self.version}"

    def _login_form(self) -> str:
        return f"https://{self.domain}/{self.form_login_path}"

    def login(self, email: str, password: str) -> str:
        """Overwrite from base class."""

        if password is None or password == "":
            raise InvalidPasswordError

        if email is None or email == "":
            raise InvalidEmailError

        response = self.__client.post(
            self._login_form(),
            data={
                "username": email,
                "password": password,
                "duration": "+12h",
                "action": "cookielogin",
                "returnurl": "/",
            },
        )

        response.raise_for_status()
        self.__cookies = response.cookies
        return response.text

    def is_authenticated(self) -> bool:
        """Overwrite from base class."""
        return self.__cookies is not None

    def spam_report(self, report_id: str):
        """Overwrite from base class."""
        pass

    def confirm_report(self) -> str:
        """Overwrite from base class."""
        pass

    def last_response(self) -> str:
        """Return the response data from the last interaction with SpamCop."""
        pass
