from core.storage.noop_storage import NoopStorage


def test_noop_storage_instantiation() -> None:
    assert isinstance(NoopStorage(), NoopStorage)
