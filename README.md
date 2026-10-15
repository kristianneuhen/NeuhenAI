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

## Secure contact-form delivery

The Contact Us form submits only to this HTTPS Flask application. It uses CSRF validation, a hidden bot trap, strict field limits, and a short rate limit. The application sends email only through a TLS-protected SMTP connection; it never exposes the recipient address in the Contact Us page.

Production SMTP settings are stored as the encrypted AWS Systems Manager Parameter Store `SecureString` parameter `/neuhenai/prod/contact/smtp`. The EC2 instance role `neuhenAI_CICD` reads that one parameter through its instance credentials and decrypts it with the dedicated KMS key `alias/neuhenai-contact-secrets`. The container does not receive an SMTP password through Docker environment variables or a persistent contact-mail file.

The parameter value is a JSON object containing `host`, `port`, `use_ssl`, `username`, `from`, `recipient`, and `password`. For Gmail, use a provider app password rather than the normal account password.
