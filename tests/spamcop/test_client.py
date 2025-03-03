from pyspamcop.spamcop.client import ClientBase
from inspect import ismethod


def test_instance_attributes():
    instance = ClientBase()
    expected = (
        "name",
        "version",
    )

    for attrib in expected:
        assert hasattr(instance, attrib)


def test_instance_methods():
    instance = ClientBase()
    expected = ("login", "spam_report", "confirm_report")

    for method_name in expected:
        assert ismethod(getattr(instance, method_name))
