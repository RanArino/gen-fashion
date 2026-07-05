"""image_generation adapter tests (MO-1/MO-2).

Verifies that generate() labels each reference image with its category
before the image part, so the model can be told which item to extract from
a photo that is not a plain garment shot (docs/local/
20260704_styling_image_generation_issue.md, Phase 1).
"""

from styling_app.adapters import image_generation


class _FakePart:
    def __init__(self, text=None, inline_data=None):
        self.text = text
        self.inline_data = inline_data


class _FakeInlineData:
    def __init__(self, data):
        self.data = data


class _FakeContent:
    def __init__(self, parts):
        self.parts = parts


class _FakeCandidate:
    def __init__(self, parts):
        self.content = _FakeContent(parts)


class _FakeResponse:
    def __init__(self, parts):
        self.candidates = [_FakeCandidate(parts)]


class _FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse([_FakePart(inline_data=_FakeInlineData(b"generated"))])


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_generate_labels_each_image_with_its_category(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(image_generation, "_client", lambda: fake_client)

    items = [
        {"bytes": b"top-bytes", "category": "top", "note": None},
        {"bytes": b"bag-bytes", "category": None, "note": None},
    ]

    result = image_generation.generate(items, "casual spring")

    assert result == b"generated"
    contents = fake_client.models.calls[0]["contents"]

    # Each image part is preceded by its own labeled text part.
    top_index = next(
        i for i, part in enumerate(contents) if getattr(part, "inline_data", None)
    )
    assert contents[top_index - 1].text == "Reference photo 1: top."

    bag_index = next(
        i
        for i, part in enumerate(contents)
        if i > top_index and getattr(part, "inline_data", None)
    )
    assert contents[bag_index - 1].text == "Reference photo 2: item."

    # The final part still carries the style description.
    assert "casual spring" in contents[-1].text
