from fastapi.testclient import TestClient

from f1_history_agent import __version__
from f1_history_agent.main import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
