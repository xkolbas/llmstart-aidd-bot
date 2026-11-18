import pytest

from bot.history_store import HistoryStore


@pytest.mark.parametrize("exchanges", [1, 10])
def test_each_message_evicts_only_the_oldest_after_limit(exchanges, tmp_path):
    store = HistoryStore(exchanges, tmp_path)
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
        for index in range(exchanges * 2 + 3)
    ]
    for index, message in enumerate(messages):
        store.append(1, message)
        assert store.get(1) == messages[max(0, index + 1 - exchanges * 2) : index + 1]


def test_histories_and_clear_are_independent_for_each_user(tmp_path):
    store = HistoryStore(10, tmp_path)
    first = {"role": "user", "content": "Первый"}
    second = {"role": "user", "content": "Второй"}
    store.append(1, first)
    store.append(2, second)
    store.clear(1)
    store.clear(3)
    assert store.get(1) == []
    assert store.get(2) == [second]
    assert store.get(3) == []


def test_history_is_independent_of_caller_and_restored_by_new_instance(tmp_path):
    store = HistoryStore(10, tmp_path)
    message = {"role": "user", "content": "Факт"}
    store.append(1, message)
    message["content"] = "Изменён"
    snapshot = store.get(1)
    snapshot[0]["content"] = "Изменён снаружи"
    assert store.get(1) == [{"role": "user", "content": "Факт"}]
    assert HistoryStore(10, tmp_path).get(1) == [{"role": "user", "content": "Факт"}]


def test_exchange_is_preserved_when_replace_fails(tmp_path, monkeypatch):
    store = HistoryStore(10, tmp_path)
    store.append_exchange(1, "Вопрос", "Ответ")
    previous = (tmp_path / "1.json").read_bytes()

    def fail(*args):
        raise OSError("disk error")

    monkeypatch.setattr("bot.history_store.os.replace", fail)
    with pytest.raises(OSError):
        store.append_exchange(1, "Следующий", "Ответ")
    assert (tmp_path / "1.json").read_bytes() == previous
    assert list(tmp_path.iterdir()) == [tmp_path / "1.json"]


def test_corrupt_file_is_not_overwritten(tmp_path):
    path = tmp_path / "1.json"
    path.write_text("broken", encoding="utf-8")
    store = HistoryStore(10, tmp_path)
    with pytest.raises(ValueError):
        store.append_exchange(1, "Вопрос", "Ответ")
    assert path.read_text(encoding="utf-8") == "broken"


def test_clear_remains_effective_after_restart(tmp_path):
    store = HistoryStore(10, tmp_path)
    store.append_exchange(1, "Вопрос", "Ответ")
    store.clear(1)
    assert not (tmp_path / "1.json").exists()
    assert HistoryStore(10, tmp_path).get(1) == []
