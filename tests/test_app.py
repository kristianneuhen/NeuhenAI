from app import app


def test_healthcheck():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_consent_is_required_before_second_step():
    client = app.test_client()

    response = client.get("/how-it-works")

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/")


def test_valid_consent_unlocks_the_funnel():
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    response = client.post(
        "/consent",
        data={"agree": "yes", "csrf_token": csrf_token},
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/how-it-works")

    unlocked_page = client.get("/how-it-works")
    assert unlocked_page.status_code == 200


def test_consent_cannot_be_submitted_without_checkbox():
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    response = client.post("/consent", data={"csrf_token": csrf_token})

    assert response.status_code == 400


def test_booking_page_uses_only_google_calendar_urls(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_BOOKING_URL", "https://calendar.app.google/example")
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]
    client.post("/consent", data={"agree": "yes", "csrf_token": csrf_token})

    page = client.get("/book")

    assert b"Open Google Calendar" in page.data


def test_booking_page_rejects_non_google_calendar_urls(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_BOOKING_URL", "https://untrusted.example/book")
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]
    client.post("/consent", data={"agree": "yes", "csrf_token": csrf_token})

    page = client.get("/book")

    assert b"Calendar setup needed" in page.data
