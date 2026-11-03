"""Practice work never enters permanent logs or the shared hash cache."""
from contextlib import contextmanager
from contextvars import ContextVar

active = ContextVar('assetarium_transient', default=False)


@contextmanager
def work():
    token = active.set(True)
    try:
        yield
    finally:
        active.reset(token)
