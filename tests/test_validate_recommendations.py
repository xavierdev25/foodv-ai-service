import pytest
from models.schemas import RecommendationRequest, AvailableProduct
from services.ollama_service import _validate_recommendations


def make_request(products):
    return RecommendationRequest(
        user_id=1,
        restrictions=[],
        preferences=[],
        available_products=products,
        max_recommendations=5,
    )


def test_valida_producto_existente():
    products = [AvailableProduct(id=1, nombre="Arroz", precio=5.0, categoria="COMIDA")]
    request = make_request(products)
    items = [{"product_id": 1, "score": 0.9, "reason": "bueno"}]
    result = _validate_recommendations(items, request)
    assert len(result) == 1
    assert result[0].product_id == 1
    assert result[0].nombre == "Arroz"
    assert result[0].precio == 5.0


def test_descarta_producto_inexistente():
    products = [AvailableProduct(id=1, nombre="Arroz", precio=5.0, categoria="COMIDA")]
    request = make_request(products)
    items = [{"product_id": 99, "score": 0.9, "reason": "alucinado"}]
    result = _validate_recommendations(items, request)
    assert len(result) == 0


def test_corrige_score_fuera_de_rango():
    products = [AvailableProduct(id=1, nombre="Arroz", precio=5.0, categoria="COMIDA")]
    request = make_request(products)
    items = [{"product_id": 1, "score": 1.5, "reason": "ok"}]
    result = _validate_recommendations(items, request)
    assert result[0].score == 1.0


def test_trunca_reason_larga():
    products = [AvailableProduct(id=1, nombre="Arroz", precio=5.0, categoria="COMIDA")]
    request = make_request(products)
    items = [{"product_id": 1, "score": 0.8, "reason": "x" * 200}]
    result = _validate_recommendations(items, request)
    assert len(result[0].reason) <= 80


def test_multiples_productos_mixtos():
    products = [
        AvailableProduct(id=1, nombre="Arroz", precio=5.0, categoria="COMIDA"),
        AvailableProduct(id=2, nombre="Jugo", precio=3.0, categoria="BEBIDA"),
    ]
    request = make_request(products)
    items = [
        {"product_id": 1, "score": 0.9, "reason": "bueno"},
        {"product_id": 99, "score": 0.8, "reason": "no existe"},
        {"product_id": 2, "score": 0.7, "reason": "refrescante"},
    ]
    result = _validate_recommendations(items, request)
    assert len(result) == 2
    assert result[0].product_id == 1
    assert result[1].product_id == 2