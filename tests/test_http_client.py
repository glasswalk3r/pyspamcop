from pyspamcop.config import read_config
from pyspamcop.http.client import HTTPClient
import os
import pytest


@pytest.fixture(scope="session")
def instance():
    return HTTPClient()


@pytest.mark.integration
def test_client(instance):
    file_path = os.path.join(os.environ["HOME"], ".spamcop.yaml")
    cfg = read_config(file_path)

    for account in cfg.accounts:
        content = instance.login(email=account.email, password=account.password)
        assert content != ""
