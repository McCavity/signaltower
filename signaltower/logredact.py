"""Keep the API key out of the access log.

Clients may pass the key as ``?key=…``; uvicorn's access log prints the full
path, so every request used to write the key into the journal.
"""

import logging
import re

_KEY_IN_QUERY = re.compile(r"([?&]key=)[^&\s]+")


def redact(text: str) -> str:
    return _KEY_IN_QUERY.sub(r"\1***", text)


class RedactKeyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True
