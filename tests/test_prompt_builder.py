"""Tests del prompt builder (Ollama batch) y extracción de JSON."""

from __future__ import annotations

import pytest

from models.schemas import (
    AvailableProduct,
    DietaryRestriction,
    RecommendationRequest,
)
from services.ollama_service import _build_batch_prompt, extract_json


def _make_request(**overrides):
    base = dict(
        user_id=1,
        restrictions=[DietaryRestriction.VEGANO],
        preferences=["arroz"],
        available_products=[
            AvailableProduct(id=1, nombre="Lomo Saltado", precio=12.0, categoria="COMIDA"),
        ],
        max_recommendations=3,
    )
    base.update(overrides)
    return RecommendationRequest(**base)


def test_batch_prompt_incluye_restricciones():
    prompt = _build_batch_prompt(_make_request())
    assert "VEGANO" in prompt
    assert "Lomo Saltado" in prompt
    assert "12.0" in prompt or "S/.12.00" in prompt


def test_batch_prompt_sin_restricciones_dice_ninguna():
    prompt = _build_batch_prompt(_make_request(restrictions=[], preferences=[]))
    assert "ninguna" in prompt


def test_batch_prompt_no_filtra_user_id_dentro_de_user_data_directamente():
    prompt = _build_batch_prompt(_make_request(user_id=999))
    # El prompt no debe incluir el user_id como identificador (privacy)
    assert "999" not in prompt


def test_batch_prompt_tiene_delimitadores_seguros():
    prompt = _build_batch_prompt(_make_request())
    assert "<USER_DATA>" in prompt
    assert "<PRODUCTS>" in prompt


def test_extract_json_directo():
    text = '{"recommendations": [{"product_id": 1, "score": 0.9}]}'
    result = extract_json(text)
    assert result["recommendations"][0]["product_id"] == 1


def test_extract_json_con_markdown():
    text = '```json\n{"product_id": 2, "score": 0.8}\n```'
    result = extract_json(text)
    assert result["product_id"] == 2


def test_extract_json_invalido():
    with pytest.raises(ValueError):
        extract_json("esto no es json para nada")


def test_extract_json_truncado_se_repara():
    # JSON sin la llave final se repara
    text = '{"product_id": 1, "score": 0.9, "reason": "ok"'
    result = extract_json(text)
    assert result["product_id"] == 1
