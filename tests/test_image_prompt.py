from pathlib import Path


def test_image_prompt_preserves_photo_analysis_rules():
    prompt = (Path(__file__).resolve().parents[1] / "prompts/image.txt").read_text()
    for rule in (
        "учитывай подпись",
        "Если подписи нет",
        "кратко перечисли различимые продукты",
        "перед уточняющим вопросом",
        "неопределённость",
        "Не придумывай скрытые ингредиенты, массу или объём",
        "не выводи общий итог",
        "текстовой истории",
        "медицинские границы",
    ):
        assert rule in prompt or rule in prompt.lower()
