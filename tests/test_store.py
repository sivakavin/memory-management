from agent.store import get_store


def test_get_store_can_store_and_retrieve_item(tmp_path):
    db_path = str(tmp_path / "long_term_memory.sqlite")

    with get_store(db_path) as store:
        store.put(("user-1", "memories"), "k1", {"text": "hello"})

        item = store.get(("user-1", "memories"), "k1")

    assert item is not None
    assert item.value["text"] == "hello"
    assert item.namespace == ("user-1", "memories")
    assert item.key == "k1"


def test_get_store_persists_data_across_connections(tmp_path):
    db_path = str(tmp_path / "long_term_memory.sqlite")

    with get_store(db_path) as store:
        store.put(("user-1", "memories"), "k1", {"text": "persisted"})

    with get_store(db_path) as store:
        item = store.get(("user-1", "memories"), "k1")

    assert item is not None
    assert item.value["text"] == "persisted"


def test_store_search_returns_items_in_namespace():
    with get_store(":memory:") as store:
        store.put(("user-1", "memories"), "a", {"text": "one"})
        store.put(("user-1", "memories"), "b", {"text": "two"})

        results = store.search(("user-1", "memories"))

    assert {item.value["text"] for item in results} == {"one", "two"}


def test_store_search_isolates_namespaces():
    with get_store(":memory:") as store:
        store.put(("user-1", "memories"), "a", {"text": "one"})
        store.put(("user-2", "memories"), "b", {"text": "two"})

        results = store.search(("user-1", "memories"))

    assert [item.value["text"] for item in results] == ["one"]


def test_store_search_returns_empty_for_unknown_namespace():
    with get_store(":memory:") as store:
        results = store.search(("nobody", "memories"))

    assert results == []


def test_store_delete_removes_item():
    with get_store(":memory:") as store:
        store.put(("user-1", "memories"), "a", {"text": "one"})

        store.delete(("user-1", "memories"), "a")

        assert store.get(("user-1", "memories"), "a") is None


def test_store_put_overwrites_existing_key():
    with get_store(":memory:") as store:
        store.put(("user-1", "memories"), "a", {"text": "one"})
        store.put(("user-1", "memories"), "a", {"text": "updated"})

        item = store.get(("user-1", "memories"), "a")

    assert item.value["text"] == "updated"


def test_store_list_namespaces():
    with get_store(":memory:") as store:
        store.put(("user-1", "memories"), "a", {"text": "one"})
        store.put(("user-2", "memories"), "b", {"text": "two"})

        namespaces = store.list_namespaces()

    assert ("user-1", "memories") in namespaces
    assert ("user-2", "memories") in namespaces
