from fastapi.testclient import TestClient

from capoeira_agent.receiver import build_app


def test_receiver_dispatches_payload_to_handler():
    received = []

    def handler(payload):
        received.append(payload)

    client = TestClient(build_app(handler))
    resp = client.post(
        "/api/capoeira/response",
        json={"request_id": "req-1", "model": "gemini-pro", "text": "olá"},
    )

    assert resp.status_code == 200
    assert received == [{"request_id": "req-1", "model": "gemini-pro", "text": "olá"}]


def test_receiver_ignores_non_dict_payload():
    received = []

    def handler(payload):
        received.append(payload)

    client = TestClient(build_app(handler))
    resp = client.post("/api/capoeira/response", json=["não", "é", "dict"])

    assert resp.status_code == 200
    assert received == []
