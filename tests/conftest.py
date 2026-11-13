import pytest

from hpscan import i18n


@pytest.fixture(autouse=True)
def english():
    """Every test starts in the default language, whatever the previous one selected."""
    i18n.set_language("en")
    yield
    i18n.set_language("en")
