from pathlib import Path


def test_system_prompt_preserves_nutritionist_rules():
    prompt_path = Path(__file__).resolve().parents[1] / "prompts/system.txt"
    prompt = prompt_path.read_text(encoding="utf-8")

    assert "Анализируй рацион" in prompt
    assert "подобрать блюда из имеющихся продуктов" in prompt
    assert "Учитывай цели и ограничения" in prompt
    assert "Перед персональной рекомендацией сначала уточни цель" in prompt
    assert "дождись ответа, прежде чем предлагать варианты" in prompt
    assert "В текстовом диалоге" in prompt
    assert "При запросе по фотографии перед уточняющим вопросом" in prompt
    assert "кратко перечисли различимые продукты" in prompt
    assert "рассчитывай калорийность только по просьбе пользователя" in prompt
    assert "не выводи общий итог до получения всех необходимых уточнений" in prompt
    assert "Продукт — количество — ≈ N ккал" in prompt
    assert "Итого: ≈ N ккал" in prompt
    assert "Расчёт ориентировочный" in prompt
    assert "Не ставь диагнозы и не назначай лечение" in prompt
