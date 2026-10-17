from agent.checkpointer import get_checkpointer


def test_sqlite_checkpointer_opens(tmp_path):
    db_path = str(tmp_path / "checkpoints.sqlite")

    with get_checkpointer(db_path) as checkpointer:
        assert checkpointer is not None