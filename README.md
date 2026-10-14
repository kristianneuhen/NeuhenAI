# Clinic Neuhen deployment starter

A deliberately small Python/Flask application packaged for Docker. The page's button calls a Python endpoint, so a successful response proves that the browser can reach the containerized application.

## Run locally with Docker

```powershell
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). Click **Test the Python response**; the page should display a response and a click count.

Stop it with:

```powershell
docker compose down
```

## Run tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Deploy later to EC2

This starter exposes port `8000` only for local learning. In production, keep port `8000` private and put Caddy in front of it. Caddy should expose ports `80` and `443` and route `clinicsneuhen.com` to this container.

The click count is intentionally stored only in memory. It resets on deployment or restart. Replace it with proper analytics or persistent storage when you build the real funnel.
