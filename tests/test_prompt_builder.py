import pytest
from services.ollama_service import build_score_prompt, build_reason_prompt, extract_json


def test_build_score_prompt_con_restricciones():
    product = {"id": 1, "nombre": "Lomo Saltado", "precio": 12.0, "categoria": "COMIDA"}
    prompt = build_score_prompt(product, ["VEGANO"], ["arroz"])
    assert "VEGANO" in prompt
    assert "Lomo Saltado" in prompt
    assert "12.0" in prompt
    assert "0.0" in prompt  # instrucción de descartar


def test_build_score_prompt_sin_restricciones():
    product = {"id": 2, "nombre": "Ensalada", "precio": 8.0, "categoria": "SNACK"}
    prompt = build_score_prompt(product, [], [])
    assert "ninguna" in prompt
    assert "Ensalada" in prompt


def test_build_reason_prompt():
    product = {"id": 1, "nombre": "Pizza", "precio": 10.0, "categoria": "COMIDA"}
    prompt = build_reason_prompt(product, [], ["italiana"])
    assert "Pizza" in prompt
    assert "italiana" in prompt
    assert "4 palabras" in prompt


def test_extract_json_directo():
    text = '{"product_id": 1, "score": 0.9, "reason": "bueno"}'
    result = extract_json(text)
    assert result["product_id"] == 1
    assert result["score"] == 0.9


def test_extract_json_con_markdown():
    text = '```json\n{"product_id": 2, "score": 0.8}\n```'
    result = extract_json(text)
    assert result["product_id"] == 2


def test_extract_json_invalido():
    with pytest.raises(ValueError):
        extract_json("esto no es json para nada")