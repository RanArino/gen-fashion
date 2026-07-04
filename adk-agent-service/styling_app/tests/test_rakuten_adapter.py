"""Rakuten Ichiba adapter tests (MK-3) with mocked HTTP and settings."""

import pytest

import styling_app.adapters.rakuten as rakuten
from styling_app.adapters.rakuten import RakutenUnavailableError, search_items


class Settings:
    rakuten_application_id = "app-id"
    rakuten_access_key = "access-key"
    rakuten_affiliate_id = "affiliate-id"
    rakuten_search_endpoint = (
        "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
    )
    rakuten_application_url = "https://gen-fashion-app.web.app/"
    rakuten_request_timeout_seconds = 10
    rakuten_max_results = 10


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_search_items_sends_credentials_and_maps_format_v2(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse(
            {
                "Items": [
                    {
                        "itemCode": "shop:1001",
                        "itemName": "White T-Shirt",
                        "itemPrice": 2980,
                        "itemUrl": "https://item.rakuten.co.jp/shop/1001",
                        "affiliateUrl": "https://hb.afl.rakuten.co.jp/xyz",
                        "mediumImageUrls": ["https://thumb/1001.jpg"],
                        "shopName": "Shop Name",
                    }
                ]
            }
        )

    monkeypatch.setattr(rakuten, "get_settings", lambda: Settings())
    monkeypatch.setattr(rakuten.httpx, "get", fake_get)

    items = search_items("white t-shirt", limit=5)

    assert captured["url"] == Settings.rakuten_search_endpoint
    assert captured["params"]["applicationId"] == "app-id"
    assert captured["params"]["accessKey"] == "access-key"
    assert captured["params"]["affiliateId"] == "affiliate-id"
    assert captured["params"]["keyword"] == "white t-shirt"
    assert captured["params"]["hits"] == 5
    # The 2026 endpoint 403s (REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING)
    # unless Origin/Referer match the registered application URL.
    assert captured["headers"]["Origin"] == "https://gen-fashion-app.web.app"
    assert captured["headers"]["Referer"] == "https://gen-fashion-app.web.app/"
    assert items == [
        {
            "item_code": "shop:1001",
            "name": "White T-Shirt",
            "price": 2980,
            "image_url": "https://thumb/1001.jpg",
            "external_url": "https://item.rakuten.co.jp/shop/1001",
            "affiliate_url": "https://hb.afl.rakuten.co.jp/xyz",
            "shop_name": "Shop Name",
        }
    ]


def test_search_items_maps_format_v1_item_wrapper(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return FakeResponse(
            {
                "Items": [
                    {
                        "Item": {
                            "itemCode": "shop:2",
                            "itemName": "Black Hat",
                            "itemPrice": 1500,
                            "itemUrl": "https://item.rakuten.co.jp/shop/2",
                            "mediumImageUrls": [{"imageUrl": "https://thumb/2.jpg"}],
                            "shopName": "Hat Shop",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(rakuten, "get_settings", lambda: Settings())
    monkeypatch.setattr(rakuten.httpx, "get", fake_get)

    items = search_items("black hat")

    assert items[0]["item_code"] == "shop:2"
    assert items[0]["image_url"] == "https://thumb/2.jpg"
    assert items[0]["affiliate_url"] is None


def test_search_items_upsizes_default_thumbnails(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return FakeResponse(
            {
                "Items": [
                    {
                        "itemCode": "shop:3",
                        "itemName": "Shirt",
                        "itemPrice": 1000,
                        "itemUrl": "https://item.rakuten.co.jp/shop/3",
                        "mediumImageUrls": [
                            "https://thumb/3.jpg?_ex=128x128"
                        ],
                        "shopName": "Shop",
                    }
                ]
            }
        )

    monkeypatch.setattr(rakuten, "get_settings", lambda: Settings())
    monkeypatch.setattr(rakuten.httpx, "get", fake_get)

    items = search_items("shirt")

    assert items[0]["image_url"] == "https://thumb/3.jpg?_ex=400x400"


def test_search_items_requires_credentials(monkeypatch):
    class NoCreds(Settings):
        rakuten_application_id = None

    monkeypatch.setattr(rakuten, "get_settings", lambda: NoCreds())

    with pytest.raises(RakutenUnavailableError):
        search_items("anything")


def test_search_items_wraps_http_errors(monkeypatch):
    def boom(url, params, headers, timeout):
        raise rakuten.httpx.ConnectError("down")

    monkeypatch.setattr(rakuten, "get_settings", lambda: Settings())
    monkeypatch.setattr(rakuten.httpx, "get", boom)

    with pytest.raises(RakutenUnavailableError):
        search_items("anything")
