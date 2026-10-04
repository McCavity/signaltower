import importlib

import pytest

from signaltower import state


@pytest.fixture(autouse=True)
def fresh_state():
    """state.py hält modulweite Globals — vor jedem Test frisch laden."""
    importlib.reload(state)
    yield
