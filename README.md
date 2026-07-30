# Billson's Tasks

A modern, self-hosted task management platform built as part of the Billson Stack.

Billson's Tasks provides structured task management for organisations, allowing administrators and managers to organise work into companies, sections and task lists while maintaining a complete audit trail.

---

# Features

## Planned

- Multiple companies
- Company isolation
- Sections
- Task lists
- Tasks with priorities
- Multiple assignees
- Comments
- Due dates
- Task history
- Audit log
- Notification outbox
- Administrator dashboard
- Manager dashboard
- Employee dashboard
- User management
- Company management
- Section management
- Global application settings
- Printable reports
- REST API

---

# Technology Stack

- Python 3.13
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL 17
- Jinja2
- Docker
- Traefik

---

# Project Structure

```
.
├── alembic/
├── app/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── web/
│   └── main.py
├── backups/
├── data/
├── docs/
├── scripts/
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

# Roles

## Global Roles

- Administrator
- User

## Company Roles

- Manager
- Employee

---

# Data Hierarchy

```
Company
└── Section
    └── List
        └── Task
```

---

# Development

## Clone

```bash
git clone https://github.com/dhbillson/billsons-tasks.git

cd billsons-tasks
```

---

## Configure

Copy the example configuration.

```bash
cp .env.example .env
```

Update the values inside `.env`.

---

## Start

```bash
docker compose up -d --build
```

---

## Check

```bash
docker compose ps
```

Health endpoint:

```
http://localhost:8000/health
```

---

# Database

## Generate a Migration

```bash
docker compose exec app \
    alembic revision --autogenerate -m "migration_name"
```

## Apply Migrations

```bash
docker compose exec app \
    alembic upgrade head
```

## Roll Back

```bash
docker compose exec app \
    alembic downgrade -1
```

---

# Initial Setup

Seed the application settings.

```bash
docker compose exec app \
    python scripts/seed_settings.py
```

Create the initial administrator.

```bash
docker compose exec app \
    python scripts/create_initial_admin.py
```

---

# Backup

Database backups are performed using the helper scripts.

```
scripts/
    backup_database.sh
    restore_database.sh
```

---

# Coding Standards

- Python 3.13
- SQLAlchemy 2 style
- Type annotations throughout
- Repository / Service architecture
- UTC storage
- Alembic for schema changes
- Ruff formatting and linting

---

# Security

- Passwords stored using bcrypt
- Server-side permission enforcement
- Company data isolation
- Immutable audit log
- Soft deletion where appropriate
- UTC timestamps throughout

---

# License

Apache License 2.0

Copyright © Dylan Billson