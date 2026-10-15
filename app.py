from __future__ import annotations

import hmac
import os
import secrets
import re
from datetime import timedelta
from functools import wraps
from urllib.parse import parse_qs, urlparse

from flask import Flask, abort, redirect, render_template, request, session, url_for
from video_settings import VIDEO_URLS


def _secret_key() -> str:
    configured_key = os.environ.get("FLASK_SECRET_KEY")
    if configured_key:
        return configured_key

    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("FLASK_SECRET_KEY must be configured in production.")

    # Local development and tests only. Production receives a persistent secret
    # from the deployment workflow and must never use this fallback.
    return "local-development-key-not-for-production"


def _trusted_google_calendar_url(variable_name: str) -> str | None:
    candidate = os.environ.get(variable_name, "").strip()
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
        "img-src 'self' data:; "
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
    embed_url = _trusted_google_calendar_url("GOOGLE_CALENDAR_EMBED_URL")
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


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
