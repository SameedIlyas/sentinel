# Sentinel AI Policy Engine

Backend service for the Sentinel AI governance platform.

## Features

- FastAPI-based REST API
- SQLAlchemy ORM with Alembic migrations
- API key authentication
- Rate limiting
- Structured logging with correlation IDs
- Health check endpoints
- CORS support

## Setup

1. Install dependencies:
```bash
pip install -r policy_engine/requirements.txt
```

2. Copy environment file:
```bash
cp .env.example .env
```

3. Run database migrations:
```bash
alembic upgrade head
```

4. Start the server:
```bash
python run_policy_engine.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Health Checks

- `/health` - General health check
- `/health/ready` - Readiness probe
- `/health/live` - Liveness probe

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migration:
```bash
alembic downgrade -1
```

## Project Structure

```
policy_engine/
├── __init__.py
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── database.py          # Database setup
├── auth/                # Authentication modules
│   ├── api_key.py       # API key validation
├── middleware/          # Custom middleware
│   ├── logging.py       # Request logging
│   ├── error_handler.py # Error handling
│   └── rate_limiter.py  # Rate limiting
├── models/              # SQLAlchemy models
│   ├── agent.py
│   ├── policy.py
│   ├── audit_log.py
│   ├── alert.py
│   └── api_key.py
└── routes/              # API endpoints
    ├── health.py
    ├── agents.py
    ├── policies.py
    ├── audit.py
    └── alerts.py
```

## Requirements

See `requirements.txt` for full list of dependencies.
