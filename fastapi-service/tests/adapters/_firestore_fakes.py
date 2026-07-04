class FakeQuery:
    def __init__(self, snapshots=None):
        self.snapshots = snapshots or []
        self.calls = []

    def where(self, field, operator, value):
        self.calls.append(("where", field, operator, value))
        return self

    def order_by(self, field, direction=None):
        self.calls.append(("order_by", field, direction))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    async def stream(self):
        for snapshot in self.snapshots:
            yield snapshot


class FakeClient:
    def __init__(self, query, collection_name="sessions"):
        self.query = query
        self.collection_name = collection_name

    def collection(self, name):
        assert name == self.collection_name
        return self.query
