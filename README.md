# Company Website

A modular Flask application with Docker support.

## Local Development

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Generate a private key for local development, then run the app:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export PYTHONPATH=src
python wsgi.py
```

`SECRET_KEY` is required; the app stops at startup if it is missing. For Docker Compose, export one in the shell before starting the container:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up --build
```

Never commit a real key or put it in a tracked file.

## Security configuration

- The GitHub Actions secret `APP_SECRET_KEY` supplies the deployed app key. The deploy workflow syncs it into Kubernetes as `company-website-secrets`; do not create a separate copy by hand.
- To configure it in another clone, generate and upload a key with `openssl rand -hex 32 | gh secret set APP_SECRET_KEY --repo ITSX25-Chas/Team3-ThaCompany`. Rotating it signs users out.
- CSRF protection is enabled globally for state-changing requests. Forms include a token, and the email preview request sends it in the `X-CSRFToken` header.
- Session cookies are `HttpOnly` and `SameSite=Lax`. Set `SESSION_COOKIE_SECURE=true` when the site is served over HTTPS. It is currently `false` because the internal ingress uses HTTP.

Or with Flask CLI:

```bash
export PYTHONPATH=src
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
flask --app company_website run --port 7000
```

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

The SQLite database is persisted in a Docker volume (`app-data`).

For Kubernetes (k3s), replace the Docker volume with a PersistentVolumeClaim pointing to `/app/data`.

## Scanner administration

The application deploy identity must not manage workloads in `security-tools`.
Changing a CronJob command can indirectly expose its mounted Discord secret,
even when direct Secret reads are forbidden. Scanner updates are applied by an
administrator on primary after review:

```bash
sudo kubectl apply -f k8s/sbom-scanner/scanner-rbac.yaml
sudo kubectl apply -f k8s/sbom-scanner/trivyignore.yaml
sudo kubectl apply -f k8s/sbom-scanner/scanner-cronjob.yaml
```

The empty legacy scanner Role and RoleBinding deliberately revoke old grants.
The scheduled scanner continues to run with its own service account.

## Tests

Run tests with pytest:

```bash
pytest
```

The test configuration supplies its own test-only `SECRET_KEY`.

## Project Structure

```
.
├── src/
│   └── company_website/
│       ├── __init__.py
│       ├── app.py          # Flask app factory
│       ├── config.py       # Configuration
│       ├── db.py           # Database helpers & migrations
│       ├── models.py       # Data models
│       ├── auth.py         # Authentication blueprint
│       ├── routes.py       # Main blueprint
│       ├── migrations/
│       ├── templates/
│       └── static/
├── tests/
├── wsgi.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
