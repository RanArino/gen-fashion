"""adapters/elasticsearch.py hybrid_search tests (MR-6) with a mocked ES client.

No existing test exercises this module directly: test_tools.py monkeypatches
hybrid_search itself at the tool boundary, so it never sees the query body
hybrid_search builds internally. Follows the mocking shape in
test_rakuten_adapter.py — monkeypatch the outbound client call and capture its
kwargs — rather than test_tools.py's approach.
"""

import styling_app.adapters.elasticsearch as es_module
from styling_app.adapters.elasticsearch import hybrid_search


class Settings:
    elasticsearch_url = "http://localhost:9200"
    elasticsearch_api_key = None
    elasticsearch_ca_certs = None
    elasticsearch_ssl_assert_fingerprint = None
    clothing_items_index = "clothing_items"
    intent_boost_enabled = True
    intent_boost_weight = 2.0


class FakeClient:
    def __init__(self):
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return {"hits": {"hits": []}}


def _patch(monkeypatch, settings=None):
    fake = FakeClient()
    monkeypatch.setattr(es_module, "get_settings", lambda: settings or Settings())
    monkeypatch.setattr(es_module, "_client", lambda: fake)
    return fake


def test_hybrid_search_adds_boosted_intent_clause_when_enabled(monkeypatch):
    fake = _patch(monkeypatch)

    hybrid_search(user_id="user-1", description="", intent="CONFIDENT")

    query = fake.calls[0]["query"]
    should = query["bool"].get("should", [])
    intent_clauses = [
        clause for clause in should if "intentTags" in clause.get("term", {})
    ]
    assert len(intent_clauses) == 1
    term = intent_clauses[0]["term"]["intentTags"]
    assert term["value"] == "CONFIDENT"
    assert term["case_insensitive"] is True
    assert term["boost"] == 2.0


def test_hybrid_search_omits_intent_clause_when_flag_disabled(monkeypatch):
    class Disabled(Settings):
        intent_boost_enabled = False

    fake = _patch(monkeypatch, Disabled())

    hybrid_search(user_id="user-1", description="", intent="CONFIDENT")

    query = fake.calls[0]["query"]
    should = query["bool"].get("should", [])
    assert not any("intentTags" in clause.get("term", {}) for clause in should)


def test_hybrid_search_omits_intent_clause_when_intent_not_supplied(monkeypatch):
    fake = _patch(monkeypatch)

    hybrid_search(user_id="user-1", description="")

    query = fake.calls[0]["query"]
    should = query["bool"].get("should", [])
    assert not any("intentTags" in clause.get("term", {}) for clause in should)


def test_hybrid_search_intent_clause_never_lands_in_filter(monkeypatch):
    fake = _patch(monkeypatch)

    hybrid_search(user_id="user-1", description="", intent="PROTECTED")

    query = fake.calls[0]["query"]
    filter_clauses = query["bool"].get("filter", [])
    assert not any("intentTags" in clause.get("term", {}) for clause in filter_clauses)
