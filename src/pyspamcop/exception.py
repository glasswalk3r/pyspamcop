"""Exceptions for the package."""


class BaseExceptionError(Exception):
    """Base class for all exception in the pyspamcop package."""


class UnknownReceiverFormat(BaseExceptionError):
    """Error when the format of a receiver is unknown.

    This means that possibly the SPAM report should be manually reported.
    """

    def __init__(self) -> None:
        super().__init__("Impossible to parse the receivers, try to manually report the SPAM")
