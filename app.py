from __future__ import annotations

import hmac
import json
import os
import secrets
import re
import smtplib
import ssl
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from email.message import EmailMessage
from functools import wraps
from urllib.parse import parse_qs, urlparse

from flask import Flask, abort, redirect, render_template, request, session, url_for
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from video_settings import VIDEO_URLS


# Google Calendar Appointment Schedule shown on Step 3. Replace this URL if
# you create a different booking schedule. A deployment environment variable
# named GOOGLE_CALENDAR_EMBED_URL can override it without changing this file.
DEFAULT_GOOGLE_CALENDAR_EMBED_URL = (
    "https://calendar.google.com/calendar/appointments/schedules/"
    "AcZssZ0kyAF2ng41OkPpoNiav4ojHqQYUikX6HAuvZ1OpjgNTirfJ4WHRnzucY1bv6MdgayC8-7N7idi?gv=true"
)

CONTACT_RATE_LIMIT_SECONDS = 600
CONTACT_RATE_LIMIT_MAX_SUBMISSIONS = 3
CONTACT_SSM_PARAMETER_NAME = os.environ.get(
    "CONTACT_SSM_PARAMETER_NAME", "/neuhenai/prod/contact/smtp"
).strip()
_contact_submissions: dict[str, deque[float]] = defaultdict(deque)
_contact_submissions_lock = threading.Lock()


def _secret_key() -> str:
    configured_key = os.environ.get("FLASK_SECRET_KEY")
    if configured_key:
        return configured_key

    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("FLASK_SECRET_KEY must be configured in production.")

    # Local development and tests only. Production receives a persistent secret
    # from the deployment workflow and must never use this fallback.
    return "local-development-key-not-for-production"


def _trusted_google_calendar_url(variable_name: str, default: str = "") -> str | None:
    candidate = os.environ.get(variable_name, default).strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    trusted_hosts = {"calendar.google.com", "calendar.app.google"}
    if parsed.scheme != "https" or parsed.hostname not in trusted_hosts:
        return None
    return candidate


def _trusted_youtube_video(url: str) -> dict[str, str] | None:
    """Return safe watch and embed URLs for an approved YouTube video."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return None

    host = (parsed.hostname or "").lower()
    video_id = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            video_id = parsed.path.rsplit("/", maxsplit=1)[-1]
    elif host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/", maxsplit=1)[0]

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None

    return {
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0",
    }


def _contact_field(name: str, maximum_length: int, *, required: bool = True) -> str:
    value = request.form.get(name, "").strip()
    if (required and not value) or len(value) > maximum_length or "\x00" in value:
        abort(400)
    return value


def _contact_submission() -> dict[str, str]:
    name = _contact_field("name", 120)
    email = _contact_field("email", 254)
    phone = _contact_field("phone", 50, required=False)
    message = _contact_field("message", 4_000)

    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}", email):
        abort(400)

    return {"name": name, "email": email, "phone": phone, "message": message}


def _contact_submission_allowed() -> bool:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_address = forwarded_for.rsplit(",", maxsplit=1)[-1].strip() or request.remote_addr
    now = time.monotonic()

    with _contact_submissions_lock:
        submissions = _contact_submissions[client_address]
        while submissions and now - submissions[0] >= CONTACT_RATE_LIMIT_SECONDS:
            submissions.popleft()
        if len(submissions) >= CONTACT_RATE_LIMIT_MAX_SUBMISSIONS:
            return False
        submissions.append(now)
    return True


def _contact_mail_settings_from_mapping(values: dict[str, object]) -> dict[str, str] | None:
    host = str(values.get("host", "")).strip()
    username = str(values.get("username", "")).strip()
    password = str(values.get("password", "")).strip()
    recipient = str(values.get("recipient", "")).strip()
    if not all((host, username, password, recipient)):
        return None

    use_ssl_value = values.get("use_ssl", True)
    use_ssl = use_ssl_value is not False and str(use_ssl_value).lower() != "false"
    try:
        port = int(values.get("port", 465 if use_ssl else 587))
    except (TypeError, ValueError):
        return None
    if not 1 <= port <= 65535:
        return None

    return {
        "host": host,
        "username": username,
        "password": password,
        "recipient": recipient,
        "from_address": str(values.get("from", username)).strip() or username,
        "port": str(port),
        "use_ssl": str(use_ssl),
    }


def _contact_mail_settings_from_environment() -> dict[str, str] | None:
    required = {
        "host": os.environ.get("CONTACT_SMTP_HOST", "").strip(),
        "username": os.environ.get("CONTACT_SMTP_USERNAME", "").strip(),
        "password": os.environ.get("CONTACT_SMTP_PASSWORD", "").strip(),
        "recipient": os.environ.get("CONTACT_RECIPIENT", "").strip(),
    }
    if not all(required.values()):
        return None

    return _contact_mail_settings_from_mapping(
        {
            **required,
            "from": os.environ.get("CONTACT_SMTP_FROM", required["username"]),
            "port": os.environ.get("CONTACT_SMTP_PORT", "465"),
            "use_ssl": os.environ.get("CONTACT_SMTP_USE_SSL", "true"),
        }
    )


def _contact_mail_settings_from_parameter_store() -> dict[str, str] | None:
    if not CONTACT_SSM_PARAMETER_NAME:
        return None

    region = (
        os.environ.get("CONTACT_SSM_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
    )
    try:
        client = boto3.client("ssm", region_name=region) if region else boto3.client("ssm")
        response = client.get_parameter(Name=CONTACT_SSM_PARAMETER_NAME, WithDecryption=True)
        values = json.loads(response["Parameter"]["Value"])
    except (BotoCoreError, ClientError, KeyError, TypeError, json.JSONDecodeError):
        return None

    if not isinstance(values, dict):
        return None
    return _contact_mail_settings_from_mapping(values)


def _contact_mail_settings() -> dict[str, str] | None:
    # Environment variables remain useful for local development only. Production
    # deployment intentionally supplies neither a contact env file nor SMTP values.
    return _contact_mail_settings_from_environment() or _contact_mail_settings_from_parameter_store()


def _send_contact_email(submission: dict[str, str]) -> bool:
    settings = _contact_mail_settings()
    if not settings:
        return False

    email = EmailMessage()
    email["Subject"] = "New client acquisition contact request"
    email["From"] = settings["from_address"]
    email["To"] = settings["recipient"]
    email["Reply-To"] = submission["email"]
    email.set_content(
        "New website contact request\n\n"
        f"Name: {submission['name']}\n"
        f"Email: {submission['email']}\n"
        f"Phone: {submission['phone'] or 'Not provided'}\n\n"
        f"Message:\n{submission['message']}\n"
    )

    try:
        if settings["use_ssl"] == "True":
            with smtplib.SMTP_SSL(
                settings["host"], int(settings["port"]), context=ssl.create_default_context(), timeout=10
            ) as client:
                client.login(settings["username"], settings["password"])
                client.send_message(email)
        else:
            with smtplib.SMTP(settings["host"], int(settings["port"]), timeout=10) as client:
                client.starttls(context=ssl.create_default_context())
                client.login(settings["username"], settings["password"])
                client.send_message(email)
    except (OSError, smtplib.SMTPException, ValueError):
        return False
    return True


app = Flask(__name__)
app.config.update(
    SECRET_KEY=_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
)


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf() -> None:
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    if not expected_token or not hmac.compare_digest(submitted_token, expected_token):
        abort(400)


def consent_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("terms_accepted"):
            return redirect(url_for("index"), code=303)
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_template_values():
    videos = {name: _trusted_youtube_video(url) for name, url in VIDEO_URLS.items()}
    return {
        "csrf_token": csrf_token,
        "terms_accepted": session.get("terms_accepted", False),
        "videos": videos,
    }


@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'; "
        "frame-src https://calendar.google.com https://calendar.app.google https://www.youtube.com; "
        "img-src 'self' data: https://assets.aceternity.com; "
        "object-src 'none'; "
        "script-src 'self'; "
        "style-src 'self'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.get("/")
def index():
    return render_template("index.html", step=1)


@app.post("/consent")
def consent():
    validate_csrf()
    if request.form.get("agree") != "yes":
        return render_template("index.html", step=1, consent_error=True), 400

    session.permanent = True
    session["terms_accepted"] = True
    return redirect(url_for("registration"), code=303)


@app.get("/how-it-works")
@consent_required
def registration():
    return render_template("registration.html", step=2)


@app.get("/book")
@consent_required
def book():
    booking_url = _trusted_google_calendar_url("GOOGLE_CALENDAR_BOOKING_URL")
    embed_url = _trusted_google_calendar_url(
        "GOOGLE_CALENDAR_EMBED_URL", DEFAULT_GOOGLE_CALENDAR_EMBED_URL
    )
    return render_template(
        "book.html",
        step=3,
        booking_url=booking_url,
        embed_url=embed_url,
        booking_available=bool(booking_url or embed_url),
    )


@app.post("/booking-complete")
@consent_required
def booking_complete():
    validate_csrf()
    session["booking_complete"] = True
    return redirect(url_for("thanks"), code=303)


@app.get("/thanks")
@consent_required
def thanks():
    if not session.get("booking_complete"):
        return redirect(url_for("book"), code=303)
    return render_template("thanks.html", step=4)


@app.get("/terms")
def terms():
    return render_template("terms.html", step=None)


@app.get("/privacy")
def privacy():
    return render_template("privacy.html", step=None)


@app.get("/faq")
def faq():
    return render_template("faq.html", step=None)


@app.get("/contact")
def contact():
    return render_template("contact.html", step=None, sent=request.args.get("sent") == "1")


@app.post("/contact")
def contact_submit():
    validate_csrf()
    if request.form.get("website", ""):
        abort(400)

    submission = _contact_submission()
    if not _contact_submission_allowed():
        return render_template("contact.html", step=None, contact_error="rate_limited"), 429
    if not _send_contact_email(submission):
        return render_template("contact.html", step=None, contact_error="delivery_failed"), 503
    return redirect(url_for("contact", sent="1"), code=303)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
