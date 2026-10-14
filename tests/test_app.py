from app import app


def test_healthcheck():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_hello_endpoint_returns_a_click_count():
    client = app.test_client()
    response = client.post("/api/hello")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Hello from the Python container!"
    assert isinstance(payload["click_count"], int)
