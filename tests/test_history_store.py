import pytest

from bot.history_store import HistoryStore


@pytest.mark.parametrize("exchanges", [1, 10])
def test_each_message_evicts_only_the_oldest_after_limit(exchanges):
    store = HistoryStore(exchanges)
    messages = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
        for index in range(exchanges * 2 + 3)
    ]
    for index, message in enumerate(messages):
        store.append(1, message)
        assert store.get(1) == messages[max(0, index + 1 - exchanges * 2) : index + 1]


def test_histories_and_clear_are_independent_for_each_user():
    store = HistoryStore(10)
    first = {"role": "user", "content": "Первый"}
    second = {"role": "user", "content": "Второй"}
    store.append(1, first)
    store.append(2, second)
    store.clear(1)
    store.clear(3)
    assert store.get(1) == []
    assert store.get(2) == [second]
    assert store.get(3) == []


def test_history_is_not_shared_with_caller_or_new_instance():
    store = HistoryStore(10)
    message = {"role": "user", "content": "Факт"}
    store.append(1, message)
    message["content"] = "Изменён"
    snapshot = store.get(1)
    snapshot[0]["content"] = "Изменён снаружи"
    assert store.get(1) == [{"role": "user", "content": "Факт"}]
    assert HistoryStore(10).get(1) == []
