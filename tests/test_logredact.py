import logging
import logging.config

import pytest

from signaltower.app import log_config

FAKE_KEY = "not-a-real-key-fake"

_CONFIGURED = ("signaltower", "uvicorn", "uvicorn.access", "uvicorn.error")


@pytest.fixture(autouse=True)
def restore_logging():
    """dictConfig bindet Handler an den capsys-Strom; danach zurückbauen,
    sonst schreiben spätere Tests in einen geschlossenen Strom."""
    yield
    for name in _CONFIGURED:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(logging.NOTSET)


def test_access_log_masks_the_api_key(capsys):
    logging.config.dictConfig(log_config())

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d',
        "198.51.100.7:4711", "GET", f"/lamps?key={FAKE_KEY}&x=1", "1.1", 200,
    )

    out = capsys.readouterr()
    logged = out.out + out.err
    assert "/lamps?key=***&x=1" in logged
    assert FAKE_KEY not in logged
