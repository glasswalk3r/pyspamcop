from pyspamcop.config import read_config
from pyspamcop.http.client import HTTPClient
import os
import pytest


@pytest.mark.integration
def test_client():
    file_path = os.path.join(os.environ["HOME"], ".spamcop.yaml")
    cfg = read_config(file_path)
    client = HTTPClient()

    for account in cfg.accounts:
        content = client.login(email=account.email, password=account.password)
        assert content != ""
