from contextlib import contextmanager

from langgraph.store.sqlite import SqliteStore


@contextmanager
def get_store(db_path: str = "long_term_memory.sqlite"):
    with SqliteStore.from_conn_string(db_path) as store:
        store.setup()
        yield store