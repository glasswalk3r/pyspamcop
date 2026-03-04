from pyspamcop.spamcop.client import ClientBase


class StubClient(ClientBase):
    def login(self, email: str, password: str) -> str:
        pass

    def is_authenticated(self) -> bool:
        pass

    def spam_report(self, report_id: str):
        pass

    def confirm_report(self):
        pass

    def last_response(self) -> str:
        pass


def test_instance():
    instance = StubClient()

    assert issubclass(StubClient, ClientBase)

    for attrib in ("name", "version"):
        assert hasattr(instance, attrib)
