# Billson's Tasks — Database Design

## 1. Purpose

This document describes the relational database design used by Billson's
Tasks.

The application uses:

- PostgreSQL 17
- SQLAlchemy 2
- Alembic migrations
- Integer primary keys
- Timezone-aware timestamps
- Database-backed authentication sessions
- Soft deletion where historical recovery is required
- Foreign keys and uniqueness constraints for structural integrity

Application services remain responsible for permission checks and higher-level
business rules. Database constraints protect the relationships and invariants
that can be enforced safely at the persistence layer.

---

## 2. Naming and common columns

All tables use snake_case names.

Primary keys are integer columns named:

```text
id