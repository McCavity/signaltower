import logging
import logging.config

from signaltower.app import log_config

FAKE_KEY = "not-a-real-key-fake"


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
