# Billson's Tasks — Database Design

## 1. Purpose

This document describes the database architecture used by Billson's Tasks.

Billson's Tasks is designed around a relational PostgreSQL database with a
clear separation between persistence, business logic and permission
enforcement.

The database is responsible for:

- Storing all application data
- Enforcing referential integrity
- Maintaining historical records
- Supporting audit logging
- Supporting soft deletion
- Supporting GDPR anonymisation
- Maintaining authentication sessions

The application layer remains responsible for:

- Authentication
- Permission enforcement
- Business rules
- Validation
- Audit generation
- User lifecycle management

The design intentionally avoids embedding business logic within the database.
All permission checks and workflow decisions are performed by application
services.

---

# 2. Technology Stack

The persistence layer is built using:

- PostgreSQL 17
- SQLAlchemy 2.x ORM
- Alembic database migrations
- Psycopg 3

The application follows a Repository → Service → Route architecture.

```
Web Route
     │
     ▼
Service Layer
     │
     ▼
Repository Layer
     │
     ▼
 PostgreSQL
```

Repositories never contain business logic.

Services never execute raw SQL.

Routes never communicate directly with the database.

---

# 3. Design Principles

The database has been designed around the following principles.

## 3.1 Referential Integrity

Relationships are enforced using foreign keys wherever possible.

Deleting parent records is intentionally restricted for most entities in order
to preserve historical information.

Example:

```
Company
    │
    ├── Sections
    │      │
    │      ├── Lists
    │      │      │
    │      │      └── Tasks
```

A task cannot exist without a list.

A list cannot exist without a section.

A section cannot exist without a company.

---

## 3.2 Soft Deletion

Business entities are never immediately removed.

Instead they become hidden from normal application use.

Examples include:

- Tasks
- Comments
- Companies (archive)
- Sections (archive)

Soft deletion allows:

- restoration
- audit history
- historical reporting
- accidental recovery

Only Global Administrators may permanently remove entities where supported.

---

## 3.3 Historical Preservation

Historical records are treated as immutable wherever practical.

Examples include:

- Task history
- Audit logs
- Completed tasks
- Deleted tasks

Editing historical records is never supported.

New records are created instead.

---

## 3.4 Explicit Relationships

Relationships are modelled directly.

For example:

```
Task
 ├── Comments
 ├── Assignees
 └── History Events
```

rather than storing unrelated JSON blobs.

This provides:

- referential integrity
- efficient querying
- predictable migrations
- simpler permissions
- better reporting

---

## 3.5 Business Logic Outside the Database

The database intentionally does **not** decide:

- who may edit a task
- who may archive a company
- who may delete comments
- who may restore tasks

Those decisions belong to the Service layer.

This keeps the schema stable while allowing application behaviour to evolve.

---

# 4. Naming Conventions

All database objects use snake_case.

Examples:

```
users
companies
company_memberships
sections
section_lists
tasks
task_comments
task_history_events
```

Primary keys are always named:

```
id
```

Foreign keys follow the convention:

```
company_id
section_id
task_id
user_id
```

Boolean columns begin with descriptive names:

```
is_active
is_completed
is_deleted
is_archived
is_anonymised
```

Timestamp columns use descriptive suffixes:

```
created_at
updated_at
completed_at
deleted_at
archived_at
anonymised_at
last_seen_at
expires_at
```

---

# 5. Common Columns

Most entities include a common set of metadata.

## Primary Key

```
id
```

Integer identity column.

Used internally by the application.

Never reused.

---

## Creation Timestamp

```
created_at
```

UTC timestamp.

Automatically populated when a record is created.

Never modified afterwards.

---

## Update Timestamp

```
updated_at
```

UTC timestamp.

Automatically updated whenever the record changes.

Used for:

- ordering
- optimistic refresh
- audit comparisons

---

## User References

Many entities include references to the acting user.

Examples:

```
created_by_user_id
completed_by_user_id
deleted_by_user_id
```

These always reference the Users table.

Historical relationships remain intact even after a user has been
anonymised.

---

# 6. Timestamp Policy

All timestamps are stored in UTC.

The application converts timestamps into the configured local timezone when
rendering pages.

The database never stores local time.

Advantages include:

- consistent ordering
- daylight savings safety
- easier backups
- easier replication
- simpler integrations

Every timestamp is timezone-aware.

Naive datetimes are never written to the database.

---

# 7. Soft Deletion Strategy

Billson's Tasks distinguishes between deletion, archival and anonymisation.

These are separate concepts.

## Deleted

Used primarily for tasks and comments.

Deleted items remain in the database.

Typical columns include:

```
is_deleted
deleted_at
deleted_by_user_id
```

Deleted records:

- disappear from normal views
- remain searchable by administrators
- may be restored
- continue to exist within audit history

---

## Archived

Used for longer-lived entities.

Examples:

- companies
- sections

Archived entities:

- cannot receive normal activity
- remain visible to administrators
- preserve historical data
- may be restored later

Archiving avoids the need to delete structural entities that still contain
historical tasks.

---

## Anonymised

Applies only to users.

Unlike deletion or archival, anonymisation permanently removes personally
identifiable information while preserving historical relationships.

This process is irreversible.

Further details are documented in:

```
docs/gdpr_anonymisation.md
```

---

# 8. Entity Overview

The core data model is organised into four logical areas.

## Identity

```
Users
Authentication Sessions
```

Responsible for authentication and identity.

---

## Organisation

```
Companies
Company Memberships

Sections
Section Memberships

Section Lists
```

Responsible for organising work.

---

## Work Management

```
Tasks
Task Assignees
Task Comments
Task History Events
```

Responsible for collaborative task management.

---

## Administration

```
Audit Logs
Settings
```

Responsible for operational management, configuration and accountability.

The following sections describe each entity and its relationships in detail.

# 9. Authentication Sessions

## Purpose

Authentication sessions represent authenticated browser sessions.

Sessions are stored in the database rather than using stateless tokens.

This provides:

- immediate session revocation
- administrator-controlled account deactivation
- logout from individual devices
- server-side authentication
- CSRF protection

Each session belongs to exactly one user.

```
User
  │
  └── Authentication Sessions
```

A user may have multiple active sessions simultaneously.

Examples include:

- desktop browser
- laptop browser
- mobile browser

Each session is managed independently.

---

## Primary Relationships

```
User
  │
  └── AuthSession
```

Foreign key:

```
user_id
```

---

## Important Columns

```
id
user_id

token_hash
csrf_token_hash

remember_me

ip_address
user_agent

created_at
last_seen_at
expires_at

is_revoked
revoked_at
```

Authentication tokens are never stored in plaintext.

Only secure hashes are persisted.

---

## Session Lifecycle

A typical lifecycle is:

```
User logs in
        │
        ▼
Session created
        │
        ▼
Browser sends cookie
        │
        ▼
last_seen_at updated
        │
        ▼
Logout / expiry / administrator action
        │
        ▼
Session revoked
```

Expired sessions are periodically removed.

Revoked sessions cannot be reused.

---

## Administrator Interaction

Administrator actions may revoke sessions.

Examples include:

- user deactivation
- password reset
- explicit session revocation

Reactivating a user does **not** restore previously revoked sessions.

The user must authenticate again.

---

# 10. Users

## Purpose

The Users table stores every authenticated account.

Users represent real people who may:

- create companies
- create sections
- create tasks
- complete tasks
- comment
- administer the application

Users never own business data directly.

Instead they act upon it.

---

## Primary Relationships

```
User
 ├── Company Memberships
 ├── Section Memberships
 ├── Created Sections
 ├── Created Tasks
 ├── Completed Tasks
 ├── Deleted Tasks
 ├── Task Assignments
 ├── Task Comments
 ├── Task History Events
 ├── Audit Logs
 └── Authentication Sessions
```

The Users table is therefore the primary identity table.

---

## Important Columns

```
id

username
display_name

password_hash

is_active
is_administrator
is_anonymised

created_at
updated_at
anonymised_at
```

---

## User States

Users may exist in three independent states.

### Active

```
is_active = true
```

The user may authenticate normally.

---

### Inactive

```
is_active = false
```

Authentication is rejected.

Existing sessions are revoked.

Historical data remains unchanged.

---

### Anonymised

```
is_anonymised = true
```

Personally identifiable information has been permanently removed.

The account can no longer authenticate.

Historical references remain valid.

---

## User Lifecycle

```
Created
    │
    ▼
Active
    │
    ├─────────────┐
    ▼             │
Inactive          │
    │             │
    ▼             │
Anonymised ◄──────┘
```

Anonymisation is irreversible.

---

# 11. Companies

## Purpose

Companies represent the highest organisational level within Billson's Tasks.

Every section belongs to exactly one company.

Companies provide:

- organisational isolation
- permission boundaries
- dashboard aggregation
- reporting scope

Examples might include:

- Billson's Brewery
- Anchor Hartland
- Galassify

---

## Primary Relationships

```
Company
 ├── Memberships
 └── Sections
```

A company owns all work beneath it.

```
Company
    │
    ▼
Sections
    │
    ▼
Lists
    │
    ▼
Tasks
```

---

## Important Columns

```
id

name
description

is_archived

created_at
updated_at
archived_at
```

---

## Company Archiving

Companies are archived rather than deleted.

Archiving:

- preserves all historical data
- hides the company from normal use
- prevents new work
- allows restoration

Sections and tasks remain attached.

---

## Visibility

A standard user only sees companies they belong to.

Global Administrators may view every company regardless of membership.

Permission enforcement occurs within the Service layer.

---

# 12. Company Memberships

## Purpose

Company memberships connect users to companies.

This is a classic many-to-many relationship.

```
User
    │
    ├──────────────┐
    ▼              ▼
Company Membership
    ▲              ▲
    └──────────────┘
           │
           ▼
       Company
```

---

## Important Columns

```
id

company_id
user_id

created_at
```

---

## Constraints

Each user may only appear once within a company.

Unique constraint:

```
(company_id, user_id)
```

Duplicate memberships are not permitted.

---

## Behaviour

Company membership grants access to:

- company dashboard
- eligible sections
- company task visibility

Section membership provides the more specific permission layer.

---

# 13. Sections

## Purpose

Sections divide work within a company.

Typical examples include:

- Kitchen
- Front of House
- Maintenance
- Housekeeping
- Management

Each section belongs to exactly one company.

---

## Primary Relationships

```
Company
    │
    ▼
Section
 ├── Members
 └── Lists
```

---

## Important Columns

```
id

company_id

name
description

created_by_user_id

is_archived

created_at
updated_at
archived_at
```

---

## Section Archiving

Sections are archived rather than deleted.

Archiving:

- preserves every task
- preserves comments
- preserves assignments
- preserves audit history

Archived sections no longer appear in normal dashboards.

Administrators may restore archived sections.

---

## Visibility

Section visibility requires:

1. Company membership
2. Appropriate section membership

Administrators bypass these restrictions.

---

# 14. Section Memberships

## Purpose

Section memberships define which users belong to individual sections.

This is the primary permission boundary for normal users.

```
User
     │
     ▼
Section Membership
     ▲
     │
 Section
```

---

## Important Columns

```
id

user_id
section_id

created_at
```

---

## Constraints

Each user may belong to a section only once.

Unique constraint:

```
(section_id, user_id)
```

---

## Behaviour

Section membership allows users to:

- view section boards
- create tasks
- update permitted tasks
- complete tasks
- comment
- view history

Additional task-specific permissions (such as assignment management) are
determined by the Service layer.

---

# 15. Organisational Hierarchy

The complete organisational structure is:

```
Company
    │
    ├── Company Members
    │
    └── Sections
            │
            ├── Section Members
            │
            └── Lists
```

The next section of this document describes the work-management entities that
sit beneath section lists:

```
Section Lists
    │
    ▼
Tasks
    ├── Assignments
    ├── Comments
    └── History
```
# 16. Section Lists

## Purpose

Section Lists represent the columns displayed on a task board.

Examples include:

- Backlog
- To Do
- In Progress
- Waiting
- Completed

Every list belongs to exactly one section.

```
Section
    │
    ▼
Section List
```

Tasks cannot exist outside a section list.

---

## Primary Relationships

```
Section
    │
    ▼
Section List
    │
    ▼
Tasks
```

A section may contain many lists.

A list may contain many tasks.

---

## Important Columns

```
id

section_id

name
description

position

is_archived

created_at
updated_at
```

---

## Ordering

Lists are displayed using the numeric position field.

Example:

```
1  Backlog
2  To Do
3  In Progress
4  Waiting
5  Complete
```

The application maintains ordering whenever lists are moved.

---

## Archiving

Lists may be archived.

Archived lists:

- disappear from normal board views
- preserve contained tasks
- remain available for administrators
- may be restored

Tasks are never automatically moved when a list is archived.

---

# 17. Tasks

## Purpose

Tasks are the primary work-management entity within Billson's Tasks.

Every task belongs to exactly one section list.

```
Section
    │
    ▼
List
    │
    ▼
Task
```

Tasks support:

- assignment
- comments
- history
- completion
- deletion
- restoration

---

## Primary Relationships

```
Task
 ├── Section List
 ├── Assignees
 ├── Comments
 ├── History Events
 ├── Created By User
 ├── Completed By User
 └── Deleted By User
```

---

## Important Columns

```
id

section_list_id

title
description

position

due_date

is_completed
completed_at
completed_by_user_id

is_deleted
deleted_at
deleted_by_user_id

created_by_user_id

created_at
updated_at
```

---

## Ordering

Tasks within a list are ordered using the position column.

Example:

```
To Do

1  Buy milk
2  Call supplier
3  Print menus
4  Order stock
```

Drag-and-drop updates these positions.

Moving between lists updates both:

- section_list_id
- position

The application is responsible for maintaining contiguous ordering.

---

## Lifecycle

```
Created
    │
    ▼
Active
    │
    ├─────────────┐
    ▼             │
Completed         │
    │             │
    ▼             │
Reopened ◄────────┘
    │
    ▼
Deleted
    │
    ▼
Restored
    │
    ▼
Permanently Deleted
```

Permanent deletion is restricted to administrators.

---

## Completion

Completion stores:

```
completed_at
completed_by_user_id
```

Reopening removes these values.

Historical completion events remain available through Task History.

---

## Soft Deletion

Deleted tasks remain fully intact.

This preserves:

- comments
- assignments
- history
- audit records

Administrators may:

- view deleted tasks
- restore deleted tasks
- permanently delete tasks

---

## Visibility

Standard users never see deleted tasks unless explicitly using administrator
tools.

Completed tasks remain visible.

---

# 18. Task Assignees

## Purpose

Task assignments represent responsibility for completing work.

Tasks may have:

- zero assignees
- one assignee
- many assignees

```
Task
    │
    ▼
Task Assignment
    ▲
    │
 User
```

---

## Important Columns

```
id

task_id
user_id

created_at
```

---

## Constraints

Duplicate assignments are not permitted.

Unique constraint:

```
(task_id, user_id)
```

---

## Behaviour

Assignments are independent of section membership.

Only users with access to the section may be assigned.

Assignment changes generate:

- task history events
- audit log entries

---

## Multiple Assignment

A task may legitimately belong to several users.

Example:

```
Prepare Beer Festival

Assigned:

• Dylan
• Sarah
• James
```

Completion remains a task-level property.

Individual assignees are not independently marked complete.

---

# 19. Task Comments

## Purpose

Comments provide discussion and collaboration on tasks.

Every comment belongs to:

- one task
- one author

```
Task
    │
    ▼
Comment
    ▲
    │
 User
```

---

## Important Columns

```
id

task_id
user_id

comment

is_deleted

deleted_at
deleted_by_user_id

created_at
updated_at
```

---

## Soft Deletion

Comments are soft deleted.

Deleted comments:

- disappear from standard views
- remain recoverable
- retain audit history

Administrators may continue to inspect deleted comments where appropriate.

---

## Editing

Comments may be edited.

Editing updates:

```
updated_at
```

Historical edits are not versioned.

Only deletion and creation are recorded within task history.

---

## Visibility

Users require task access to view comments.

Deleted comments are hidden from normal users.

---

# 20. Task History Events

## Purpose

Task history provides an immutable timeline describing significant changes to a
task.

Unlike comments, history is generated automatically.

Users cannot edit history entries.

---

## Primary Relationships

```
Task
    │
    ▼
History Event
    ▲
    │
 User
```

---

## Important Columns

```
id

task_id
user_id

event_type

old_value
new_value

created_at
```

---

## Typical Events

Examples include:

```
Task Created

Title Updated

Description Updated

Moved List

Reordered

Completed

Reopened

Deleted

Restored

Assignee Added

Assignee Removed

Comment Added

Comment Deleted
```

Each event contains sufficient metadata to explain what occurred.

---

## Immutability

History records are never edited.

Corrections generate additional history events.

This guarantees an accurate chronological record.

---

## Relationship to Audit Logging

Task history is intended for operational collaboration.

Audit logging is intended for administration.

Task history answers:

> What happened to this task?

Audit logging answers:

> Who performed a system action, when, and against which entity?

Although related, these systems have different audiences.

---

# 21. Work Management Relationships

The complete task-management hierarchy is:

```
Company
    │
    ▼
Section
    │
    ▼
Section List
    │
    ▼
Task
 ├── Assignees
 ├── Comments
 └── History Events
```

Every work-management entity ultimately belongs to a single company through
this relationship chain.

Permission isolation relies upon this hierarchy.

Cross-company references are intentionally prohibited.

---

# 22. Cascading Behaviour

The application deliberately avoids destructive cascading deletes.

Instead, relationships are preserved through soft deletion and archival.

Examples:

Deleting a task:

```
Task
 ├── Comments
 ├── Assignments
 └── History

remain intact
```

Archiving a section:

```
Section
    │
    ▼
Lists
    │
    ▼
Tasks

remain intact
```

Anonymising a user:

```
User identity removed

Task ownership preserved

History preserved

Audit preserved
```

Historical integrity always takes priority over aggressive deletion.
# 23. Audit Logs

## Purpose

The Audit Log provides a permanent administrative record of significant actions
performed within Billson's Tasks.

Unlike task history, audit logs are intended for:

- security
- accountability
- troubleshooting
- compliance
- administrator review

Audit records are append-only.

They are never edited or deleted by normal application workflows.

---

## Primary Relationships

```
User
    │
    ▼
Audit Log
```

Each audit record references:

- the acting user
- the affected entity
- the action performed

Additional metadata may be recorded where appropriate.

---

## Important Columns

```
id

user_id

event_type

entity_type
entity_id

description

metadata

created_at
```

---

## Recorded Events

Typical events include:

```
Authentication

Password Reset

Task Deleted

Task Restored

Task Permanently Deleted

Comment Deleted

Company Archived

Company Restored

Section Archived

Section Restored

User Deactivated

User Reactivated

User Anonymised

Administrator Actions
```

Only significant events are recorded.

Routine page views and searches are intentionally excluded.

---

## Immutability

Audit records are never modified.

Corrections are represented by additional audit entries rather than editing
existing records.

This guarantees a trustworthy chronological record.

---

# 24. Application Settings

## Purpose

The Settings table stores application-wide configuration.

Settings are intentionally separated from environment variables.

Environment variables configure infrastructure.

Settings configure application behaviour.

---

## Examples

Typical settings include:

```
Application Name

Timezone

Branding

Default Behaviour
```

---

## Relationships

Settings are global.

They are not associated with companies or users.

```
Application
     │
     ▼
 Settings
```

---

# 25. Relationship Summary

The complete entity hierarchy is shown below.

```
Users
 │
 ├── Authentication Sessions
 ├── Company Memberships
 ├── Section Memberships
 ├── Task Assignments
 ├── Task Comments
 ├── Task History Events
 └── Audit Logs

Companies
 │
 ├── Company Memberships
 └── Sections
       │
       ├── Section Memberships
       └── Section Lists
             │
             └── Tasks
                   ├── Task Assignments
                   ├── Task Comments
                   └── Task History Events

Settings
```

The hierarchy intentionally forms a tree.

Cross-company relationships are not permitted.

---

# 26. Isolation Model

The database supports complete organisational isolation.

Every task ultimately belongs to exactly one company.

```
Task
 │
 ▼
Section List
 │
 ▼
Section
 │
 ▼
Company
```

This allows permission services to determine visibility using a single,
predictable ownership chain.

No task may belong to multiple companies.

No section may belong to multiple companies.

No list may belong to multiple sections.

---

# 27. Transaction Boundaries

Repositories never perform commits.

Instead:

```
Repository
    │
    ▼
Service
    │
    ▼
Commit
```

This allows multiple repository operations to participate within a single
transaction.

Example:

```
Create Task

↓

Insert Task

↓

Insert History Event

↓

Insert Audit Event

↓

Commit Once
```

If any operation fails, the entire transaction is rolled back.

---

# 28. Repository Architecture

Repositories provide persistence only.

Typical responsibilities include:

- selecting records
- inserting records
- updating records
- deleting records
- pagination
- filtering
- ordering

Repositories do not:

- validate permissions
- generate audit logs
- perform authentication
- enforce business rules

Those responsibilities belong to services.

---

# 29. Service Architecture

Services coordinate business operations.

Typical responsibilities include:

- validation
- permission enforcement
- transaction coordination
- audit generation
- history generation
- repository orchestration

Services are the only layer permitted to combine multiple repositories within a
single operation.

---

# 30. Indexing Strategy

The schema favours predictable query performance over excessive indexing.

Indexes are created primarily for:

- foreign keys
- unique constraints
- frequently filtered columns
- ordering columns

Typical indexed fields include:

```
user_id

company_id

section_id

section_list_id

task_id

created_at

updated_at

position

is_deleted

is_archived

is_active
```

Additional indexes may be introduced where profiling demonstrates measurable
benefit.

---

# 31. Migration Strategy

All schema changes are managed using Alembic.

Every migration must satisfy the following principles.

### Reversible

Where practical, migrations should support downgrade operations.

---

### Incremental

Large schema changes should be split into smaller migrations.

This simplifies deployment and rollback.

---

### Non-destructive

Existing data should be preserved whenever possible.

Archiving is preferred over deletion.

---

### Tested

Every migration should be accompanied by:

- repository tests
- service tests
- integration tests

where appropriate.

---

# 32. Backup Considerations

Because the database contains operational and audit information, regular
backups are considered essential.

Recommended strategy:

- Daily automated backups
- Point-in-time recovery where supported
- Regular restore verification
- Off-site encrypted backup storage

Application uploads should be backed up independently where applicable.

---

# 33. Future Schema Evolution

The current schema has been designed to allow future expansion without major
structural redesign.

Potential future additions include:

- Labels
- Task priorities
- Task attachments
- Recurring tasks
- Notifications
- Watchers
- Time tracking
- Activity subscriptions
- Saved searches
- API tokens

These features can be introduced using additional tables while preserving the
existing relationship hierarchy.

---

# 34. Design Principles Summary

The Billson's Tasks database has been designed around the following principles.

- Strong referential integrity
- Predictable ownership hierarchy
- Explicit relationships
- Soft deletion instead of destructive deletion
- Historical preservation
- Immutable audit history
- Clear separation between repositories and services
- Business logic outside the database
- UTC timestamp storage
- Administrator accountability
- GDPR-compatible anonymisation
- Incremental schema evolution

Collectively these principles provide a database that is straightforward to
reason about, resilient to future expansion, and capable of supporting both
day-to-day operational workflows and long-term historical reporting while
maintaining clear security and organisational boundaries.