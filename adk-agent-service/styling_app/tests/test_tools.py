"""Unit tests for the four M4 tools with mocked Gemini/ES/storage adapters."""

import pytest

from styling_app.tools.analyze_clothing_image import analyze_clothing_image
from styling_app.tools.ask_preference import ask_preference
from styling_app.tools.search_closet import search_closet
from styling_app.tools.search_rakuten import search_rakuten
from styling_app.tools.style_synthesizer import style_synthesizer

ANALYSIS = {
    "category": "shirt",
    "colors": ["navy"],
    "tags": ["casual", "cotton"],
    "season": "spring",
    "style": "casual",
}


# ── analyze_clothing_image (M4-5) ──────────────────────────────────────────────


def test_analyze_clothing_image(monkeypatch):
    import styling_app.tools.analyze_clothing_image as mod

    monkeypatch.setattr(mod.image_storage, "fetch_bytes", lambda url: b"jpegbytes")
    monkeypatch.setattr(mod.gemini, "analyze", lambda data: dict(ANALYSIS))

    result = analyze_clothing_image("http://example.com/shirt.jpg")
    assert result == ANALYSIS


# ── search_closet (M4-6) ───────────────────────────────────────────────────────


def _patch_search(monkeypatch, hits, embed=lambda text: [0.1] * 768):
    import styling_app.tools.search_closet as mod

    captured = {}

    def fake_hybrid_search(**kwargs):
        captured.update(kwargs)
        return hits

    monkeypatch.setattr(mod.gemini, "embed_text", embed)
    monkeypatch.setattr(mod.elasticsearch, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(
        mod.image_storage, "get_download_url", lambda key: f"http://signed/{key}"
    )
    return captured


def test_search_closet_shared_attribution(monkeypatch):
    hits = [{"item_id": "abc", "category": "pants", "tags": ["denim"]}]
    captured = _patch_search(monkeypatch, hits)

    results = search_closet("blue denim pants", "SHARED_CLOSET", "user-1")

    assert captured["user_id"] == "__shared__"
    assert captured["query_vector"] == [0.1] * 768
    assert results == [
        {
            "item_id": "abc",
            "source": "SHARED_CLOSET",
            "image_url": "http://signed/__shared__/closet/abc.jpg",
            "category": "pants",
            "tags": ["denim"],
            "colors": [],
            "season": None,
            "gender": "common",
            "attribution": "Clothing Dataset (CC BY-SA 4.0)",
        }
    ]


def test_search_closet_filters_selected_shared_closet(monkeypatch):
    hits = [{"item_id": "abc", "category": "pants", "tags": ["denim"]}]
    captured = _patch_search(monkeypatch, hits)

    search_closet(
        "blue denim pants",
        "SHARED_CLOSET",
        "user-1",
        shared_closet_id="adult-01",
    )

    assert captured["user_id"] == "__shared__"
    assert captured["closet_id"] == "adult-01"


def test_search_closet_personal_closet(monkeypatch):
    hits = [{"item_id": "i1", "category": "shirt", "tags": []}]
    captured = _patch_search(monkeypatch, hits)

    results = search_closet("white shirt", "CLOSET", "user-1", category="shirt")

    assert captured["user_id"] == "user-1"
    assert captured["category"] == "shirt"
    assert results[0]["attribution"] is None
    assert results[0]["image_url"] == "http://signed/user-1/closet/i1.jpg"


def test_search_closet_normalizes_bottom_category(monkeypatch):
    hits = [{"item_id": "i1", "category": "Pants", "tags": ["pants"]}]
    captured = _patch_search(monkeypatch, hits)

    search_closet("blue pants", "SHARED_CLOSET", "user-1", category="bottom")

    assert captured["category"] == ["Pants", "Shorts", "Skirt"]


def test_search_closet_embedding_failure_is_fail_soft(monkeypatch):
    def boom(text):
        raise RuntimeError("embedding down")

    captured = _patch_search(monkeypatch, [], embed=boom)
    assert search_closet("anything", "SHARED_CLOSET", "u") == []
    assert captured["query_vector"] is None


def test_search_closet_rejects_rakuten(monkeypatch):
    with pytest.raises(ValueError):
        search_closet("dress", "RAKUTEN", "user-1")


# ── search_rakuten (MK-3) ──────────────────────────────────────────────────────


def _patch_rakuten(monkeypatch, items):
    import styling_app.tools.search_rakuten as mod

    captured = {}

    def fake_search_items(keyword, *, limit=None):
        captured["keyword"] = keyword
        captured["limit"] = limit
        return items

    monkeypatch.setattr(mod.rakuten, "search_items", fake_search_items)
    return captured


def test_search_rakuten_maps_candidate_fields(monkeypatch):
    captured = _patch_rakuten(
        monkeypatch,
        [
            {
                "item_code": "shop:1001",
                "name": "White T-Shirt",
                "price": 2980,
                "image_url": "https://thumbnail.image.rakuten.co.jp/1001.jpg",
                "external_url": "https://item.rakuten.co.jp/shop/1001",
                "affiliate_url": "https://hb.afl.rakuten.co.jp/xyz",
                "shop_name": "Shop Name",
            }
        ],
    )

    results = search_rakuten("white t-shirt", category="top", colors=["white"])

    assert captured["keyword"] == "white t-shirt white"
    assert results == [
        {
            "item_id": "rakuten:shop:1001",
            "source": "RAKUTEN",
            "name": "White T-Shirt",
            "image_url": "https://thumbnail.image.rakuten.co.jp/1001.jpg",
            "price": 2980,
            "category": "top",
            "tags": ["white"],
            "external_url": "https://item.rakuten.co.jp/shop/1001",
            "affiliate_url": "https://hb.afl.rakuten.co.jp/xyz",
            "shop_name": "Shop Name",
            "attribution": "Rakuten Ichiba",
        }
    ]


def test_search_rakuten_skips_items_without_image_or_code(monkeypatch):
    _patch_rakuten(
        monkeypatch,
        [
            {"item_code": "a", "image_url": None},
            {"item_code": None, "image_url": "http://img"},
            {"item_code": "b", "image_url": "http://img/b.jpg"},
        ],
    )

    results = search_rakuten("black hat")

    assert [item["item_id"] for item in results] == ["rakuten:b"]


def test_search_rakuten_rejects_empty_query(monkeypatch):
    _patch_rakuten(monkeypatch, [])
    with pytest.raises(ValueError):
        search_rakuten("   ")


def test_search_rakuten_propagates_unavailable(monkeypatch):
    import styling_app.tools.search_rakuten as mod
    from styling_app.adapters.rakuten import RakutenUnavailableError

    def boom(keyword, *, limit=None):
        raise RakutenUnavailableError("no credentials")

    monkeypatch.setattr(mod.rakuten, "search_items", boom)
    with pytest.raises(RakutenUnavailableError):
        search_rakuten("bag")


# ── style_synthesizer (M4-7) ───────────────────────────────────────────────────


def _patch_synth(monkeypatch, generate):
    import styling_app.tools.style_synthesizer as mod

    stored = {}

    def fake_put_bytes(key, data, content_type="image/jpeg"):
        stored["key"] = key
        stored["data"] = data
        return f"http://signed/{key}"

    monkeypatch.setattr(mod.image_storage, "fetch_bytes", lambda url: b"garment")
    monkeypatch.setattr(mod.image_storage, "put_bytes", fake_put_bytes)
    monkeypatch.setattr(mod.image_generation, "generate", generate)
    monkeypatch.setattr(
        mod.image_generation, "build_collage", lambda images: b"collage"
    )
    return stored


def test_style_synthesizer_generated(monkeypatch):
    stored = _patch_synth(monkeypatch, lambda images, desc: b"generated")

    result = style_synthesizer("user-1", ["u1.jpg", "u2.jpg"], "casual spring")

    assert stored["key"].startswith("user-1/coordinates/")
    assert stored["data"] == b"generated"
    assert result["coordinate_image_url"] == f"http://signed/{stored['key']}"
    assert result["items"] == ["u1.jpg", "u2.jpg"]
    assert result["model_used"] == "gemini-2.5-flash-image"


def test_style_synthesizer_collage_fallback(monkeypatch):
    def boom(images, desc):
        raise RuntimeError("model unavailable")

    stored = _patch_synth(monkeypatch, boom)

    result = style_synthesizer("user-1", ["u1.jpg"], "")

    assert stored["data"] == b"collage"
    assert result["model_used"] == "collage-fallback"


def test_style_synthesizer_prompt_includes_child_and_gender(monkeypatch):
    captured = {}

    def generate(images, description):
        captured["description"] = description
        return b"generated"

    _patch_synth(monkeypatch, generate)
    result = style_synthesizer(
        "user-1",
        ["u1.jpg"],
        "casual spring",
        gender="female",
        wearer_age="child",
    )

    assert "child female wearer" in captured["description"]
    assert result["generation_prompt"] == captured["description"]


# ── ask_preference (M4-8) ──────────────────────────────────────────────────────


def test_ask_preference_normalizes():
    assert ask_preference(occasion=" office ", season="", style=None) == {
        "occasion": "office",
        "season": None,
        "style": None,
        "color_preference": None,
        "gender": None,
    }


def test_ask_preference_echoes_full_preference():
    prefs = {
        "occasion": "date",
        "season": "summer",
        "style": "casual",
        "color_preference": "earth tones",
        "gender": "female",
    }
    assert ask_preference(**prefs) == prefs


def test_fetch_bytes_uses_storage_client_for_own_presigned_url(monkeypatch):
    import styling_app.adapters.image_storage as mod

    class Settings:
        r2_public_endpoint_url = "http://localhost:9000"
        r2_endpoint_url = "http://minio:9000"
        r2_bucket_name = "gen-fashion-images"

    class Body:
        def read(self):
            return b"stored-image"

    class Client:
        def get_object(self, Bucket, Key):
            assert Bucket == "gen-fashion-images"
            assert Key == "__shared__/closet/item 1.jpg"
            return {"Body": Body()}

    monkeypatch.setattr(mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(mod, "_clients", lambda: (Client(), object()))

    result = mod.fetch_bytes(
        "http://localhost:9000/gen-fashion-images/__shared__/closet/item%201.jpg"
        "?X-Amz-Signature=abc"
    )

    assert result == b"stored-image"
