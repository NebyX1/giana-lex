def test_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["service"] == "giana-lex-backend"
    assert response.headers["X-Request-ID"]


def test_readiness_checks_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json()["checks"]["database"] == "ok"
