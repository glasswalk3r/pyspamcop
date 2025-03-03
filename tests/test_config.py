from pyspamcop.config import read_config, MissingAccountCfgError, InvalidCfgDirectiveError, Configuration
from tempfile import NamedTemporaryFile
import pytest
from ruamel.yaml import YAML
from io import TextIOWrapper


@pytest.fixture
def sample_cfg_file() -> str:
    return "tests/fixtures/sample_cfg.yaml"


@pytest.fixture
def sample_cfg(sample_cfg_file) -> dict:
    with open(sample_cfg_file, "r") as fp:
        yaml = YAML(typ="safe")
        return yaml.load(fp)


def config_dump(data: dict, fp: TextIOWrapper):
    yaml = YAML(typ="safe")
    yaml.dump(data, fp)
    fp.close()


def test_read_config(sample_cfg_file):
    cfg = read_config(sample_cfg_file)
    assert isinstance(cfg, Configuration)
    assert len(cfg.accounts) == 2


def test_read_config_no_accounts(sample_cfg):
    data = sample_cfg
    data.pop("accounts")

    with NamedTemporaryFile(delete_on_close=False) as fp:
        config_dump(data, fp)
        filename = fp.name

        with pytest.raises(MissingAccountCfgError) as exc_info:
            read_config(filename)

    assert filename in str(exc_info.value)


def test_read_config_invalid_directive(sample_cfg):
    data = sample_cfg
    directive = "foobar"
    data[directive] = None

    with NamedTemporaryFile(delete_on_close=False) as fp:
        config_dump(data, fp)
        filename = fp.name

        with pytest.raises(InvalidCfgDirectiveError) as exc_info:
            read_config(filename)

    assert directive in str(exc_info.value)
