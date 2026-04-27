import pytest
from unittest.mock import patch, MagicMock
from services import cache_service


def test_get_cached_retorna_none_si_cache_no_disponible():
    with patch.object(cache_service, 'CACHE_AVAILABLE', False):
        result = cache_service.get_cached(1, [])
        assert result is None


def test_set_cached_no_falla_si_cache_no_disponible():
    with patch.object(cache_service, 'CACHE_AVAILABLE', False):
        cache_service.set_cached(1, [], {"recommendations": []})


def test_get_cached_hit():
    mock_redis = MagicMock()
    mock_redis.get.return_value = '{"user_id": 1, "recommendations": []}'
    with patch.object(cache_service, 'CACHE_AVAILABLE', True), \
         patch.object(cache_service, '_redis', mock_redis):
        result = cache_service.get_cached(1, [{"id": 1}])
        assert result is not None
        assert result["user_id"] == 1


def test_get_cached_miss():
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    with patch.object(cache_service, 'CACHE_AVAILABLE', True), \
         patch.object(cache_service, '_redis', mock_redis):
        result = cache_service.get_cached(1, [{"id": 1}])
        assert result is None