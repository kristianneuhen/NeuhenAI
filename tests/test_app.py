from pathlib import Path

from app import app


def test_healthcheck():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_docker_image_includes_video_settings_module():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY video_settings.py ./" in dockerfile


def test_funnel_pages_use_the_shared_frame_with_the_ambient_background():
    client = app.test_client()

    response = client.get("/")

    assert b'class="site-frame"' in response.data
    assert b'class="site-frame__canvas"' in response.data
    assert b'id="ambient-background"' in response.data
    assert b"background.js" in response.data


def test_global_neuhen_brand_label_is_removed_from_the_funnel_header():
    client = app.test_client()

    response = client.get("/")

    assert b'class="brand"' not in response.data


def test_terms_page_contains_the_supplied_terms_and_contact_details():
    client = app.test_client()

    response = client.get("/terms")

    assert response.status_code == 200
    assert b"1. Use of Our Website and Services" in response.data
    assert b"12. Contact Us" in response.data
    assert b"kristianneuhen@gmail.com" in response.data


def test_privacy_page_contains_the_supplied_policy_and_contact_details():
    client = app.test_client()

    response = client.get("/privacy")

    assert response.status_code == 200
    assert b"1. Introduction" in response.data
    assert b"10. Contact Us" in response.data
    assert b"14.10.2026" in response.data
    assert b"kristianneuhen@gmail.com" in response.data


def test_legal_pages_link_to_the_main_page_without_a_header_logo():
    client = app.test_client()

    for path in ("/terms", "/privacy"):
        response = client.get(path)

        assert response.status_code == 200
        assert b"Main page" in response.data
        assert b'legal-logo' not in response.data
        assert b"return back" not in response.data
        assert b"Return back to client acquisition" not in response.data
        assert b'href="/"' in response.data


def test_contact_page_has_the_requested_secure_form_and_static_map():
    client = app.test_client()

    response = client.get("/contact")

    assert response.status_code == 200
    assert b'action="/contact"' in response.data
    assert b"mailto:" not in response.data
    assert b'name="phone"' in response.data
    assert b'name="company"' not in response.data
    assert b"contact-map__beacon" not in response.data
    assert b'contact-mail-icon' in response.data
    assert b'contact-form__pattern' in response.data
    assert b"We are here" not in response.data
    assert b"kristianneuhen@gmail.com" not in response.data


def test_contact_submission_requires_csrf_protection():
    client = app.test_client()

    response = client.post(
        "/contact",
        data={"name": "Visitor", "email": "visitor@example.com", "message": "Hello"},
    )

    assert response.status_code == 400


def test_contact_submission_sends_validated_fields(monkeypatch):
    client = app.test_client()
    client.get("/contact")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    delivered = {}

    def send_email(submission):
        delivered.update(submission)
        return True

    monkeypatch.setattr("app._send_contact_email", send_email)
    response = client.post(
        "/contact",
        data={
            "csrf_token": csrf_token,
            "name": "Visitor Name",
            "email": "visitor@example.com",
            "phone": "+48 123 456 789",
            "message": "I would like to learn more.",
        },
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/contact?sent=1")
    assert delivered == {
        "name": "Visitor Name",
        "email": "visitor@example.com",
        "phone": "+48 123 456 789",
        "message": "I would like to learn more.",
    }


def test_contact_mail_settings_reads_parameter_store(monkeypatch):
    class FakeSsm:
        def get_parameter(self, **kwargs):
            assert kwargs == {
                "Name": "/neuhenai/prod/contact/smtp",
                "WithDecryption": True,
            }
            return {
                "Parameter": {
                    "Value": (
                        '{"host":"smtp.gmail.com","port":465,"use_ssl":true,'
                        '"username":"sender@example.com","from":"sender@example.com",'
                        '"recipient":"recipient@example.com","password":"app-password"}'
                    )
                }
            }

    monkeypatch.delenv("CONTACT_SMTP_HOST", raising=False)
    monkeypatch.delenv("CONTACT_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("CONTACT_SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("CONTACT_RECIPIENT", raising=False)
    monkeypatch.setattr("app.boto3.client", lambda service, region_name=None: FakeSsm())

    from app import _contact_mail_settings

    assert _contact_mail_settings() == {
        "host": "smtp.gmail.com",
        "username": "sender@example.com",
        "password": "app-password",
        "recipient": "recipient@example.com",
        "from_address": "sender@example.com",
        "port": "465",
        "use_ssl": "True",
    }


def test_video_settings_are_rendered_as_safe_youtube_embeds():
    client = app.test_client()

    client.get("/")
    with client.session_transaction() as session:
        session["terms_accepted"] = True
        session["booking_complete"] = True

    for path in ("/", "/how-it-works", "/thanks"):
        page = client.get(path)

        assert page.status_code == 200
        assert b"https://www.youtube.com/embed/1kJ8IUANR8s?rel=0" in page.data
        assert b"Open video on YouTube" not in page.data


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
    assert b"Go back" in unlocked_page.data


def test_consent_cannot_be_submitted_without_checkbox():
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    response = client.post("/consent", data={"csrf_token": csrf_token})

    assert response.status_code == 400


def test_booking_page_embeds_configured_google_calendar_schedule():
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        session["terms_accepted"] = True

    page = client.get("/book")

    assert b"calendar.google.com/calendar/appointments/schedules/AcZssZ0k" in page.data
    assert b"Google Calendar booking page" in page.data
    assert b"calendar-frame--muted" in page.data


def test_booking_page_uses_only_google_calendar_urls(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_BOOKING_URL", "https://calendar.app.google/example")
    monkeypatch.setenv("GOOGLE_CALENDAR_EMBED_URL", "")
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]
    client.post("/consent", data={"agree": "yes", "csrf_token": csrf_token})

    page = client.get("/book")

    assert b"Open Google Calendar" in page.data


def test_booking_page_rejects_non_google_calendar_urls(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_BOOKING_URL", "https://untrusted.example/book")
    monkeypatch.setenv("GOOGLE_CALENDAR_EMBED_URL", "https://untrusted.example/embed")
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]
    client.post("/consent", data={"agree": "yes", "csrf_token": csrf_token})

    page = client.get("/book")

    assert b"Calendar setup needed" in page.data
    assert b"Continue to the next step" in page.data
