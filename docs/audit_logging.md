# Billson's Tasks — Audit Logging

## 1. Purpose

The Audit Log provides a permanent record of significant actions performed
within Billson's Tasks.

Its primary goals are:

- accountability
- security
- operational troubleshooting
- compliance
- administrative oversight

Unlike task history, which records changes to an individual task for
collaboration purposes, the audit log records important actions across the
entire application.

The audit log is intended for administrators rather than day-to-day users.

---

# 2. Design Goals

The audit logging system has been designed around several core principles.

## Accountability

Every significant administrative or business action should be attributable to
an authenticated user wherever possible.

The audit log answers questions such as:

- Who performed this action?
- When did it occur?
- Which entity was affected?
- What type of action was performed?

---

## Immutability

Audit records are append-only.

Once written they are never:

- edited
- reordered
- deleted
- rewritten

If a later action reverses an earlier one, a new audit record is created rather
than modifying the existing record.

Example:

```
09:12
Task Deleted

↓

09:14
Task Restored
```

Both events remain visible.

---

## Historical Accuracy

Audit records preserve what actually happened.

They do not attempt to present only the current system state.

For example:

```
User Deactivated

↓

User Reactivated
```

Both events remain permanently visible.

---

## Minimal Performance Impact

Audit generation should add minimal overhead to normal application operations.

Audit records are created within the same transaction as the originating
operation.

This guarantees consistency while avoiding unnecessary database round trips.

---

## Security

Audit data must never weaken application security.

Sensitive information such as:

- passwords
- authentication tokens
- CSRF tokens
- password hashes

must never be written to the audit log.

---

# 3. Audit Event Model

Every audit record represents one completed action.

Conceptually an event consists of four parts.

```
Actor

↓

Action

↓

Target

↓

Timestamp
```

Example:

```
Administrator

↓

Archived Company

↓

Anchor Hotels

↓

2026-08-03 14:37 UTC
```

This simple structure allows the audit log to remain consistent across all
areas of the application.

---

# 4. Audit Record Structure

Each audit record contains a common set of information.

## Actor

The authenticated user responsible for the action.

Example:

```
Dylan Billson
```

If an action is performed automatically by the system, the actor may be absent
or represented as a system event.

---

## Event Type

A short machine-readable identifier describing the action.

Examples:

```
task.deleted

task.restored

company.archived

user.deactivated

audit.viewed
```

Event types remain stable over time to support filtering and reporting.

---

## Entity Type

Identifies the type of object affected.

Examples:

```
Task

Company

Section

User

Comment

Session
```

---

## Entity Identifier

The primary key of the affected entity.

Example:

```
Task #482
```

This allows administrators to navigate from audit events to related objects
where appropriate.

---

## Description

A human-readable explanation of the event.

Example:

```
Archived company "Anchor Hotels"
```

Descriptions are intended for administrators rather than application logic.

---

## Metadata

Optional structured information describing the action in more detail.

Examples include:

- previous values
- new values
- affected usernames
- archived state
- restored state

Metadata is always supplementary.

The audit record should remain understandable without it.

---

## Timestamp

Every audit record stores the UTC time at which the action completed.

Timestamps are immutable.

The application converts them into the configured timezone when displaying
audit information.

---

# 5. Actor Relationships

Audit records normally reference an authenticated user.

```
User

↓

Audit Record
```

Users may later become:

- inactive
- anonymised

The relationship remains intact.

Historical accountability is therefore preserved even when personal
information has been removed.

The display of anonymised users is covered separately within the GDPR
documentation.

---

# 6. Entity Relationships

Audit records may reference many different entity types.

Examples include:

```
User

Company

Section

Section List

Task

Task Assignment

Task Comment

Authentication Session
```

The audit system intentionally stores the entity type alongside the entity
identifier.

This avoids ambiguity when different tables contain identical numeric primary
keys.

Example:

```
Task #14
```

is distinct from

```
Company #14
```

---

# 7. Event Lifecycle

Audit records are generated automatically by the Service layer.

The lifecycle is:

```
Business Operation

↓

Validation

↓

Permission Check

↓

Database Update

↓

Audit Event Created

↓

Transaction Commit
```

If the transaction rolls back, the audit record is rolled back as well.

This guarantees that audit records never exist for operations that ultimately
failed.

---

# 8. Service Responsibilities

Repositories never generate audit records.

Instead, services coordinate:

- business validation
- permission enforcement
- entity updates
- audit creation

Typical flow:

```
Route

↓

Permission Service

↓

Business Service

↓

Repository

↓

Audit Repository

↓

Commit
```

This ensures every successful operation is accompanied by a corresponding audit
record where appropriate.

The following sections document the specific events recorded throughout the
application, metadata conventions, filtering behaviour and operational
guidance.

# 9. Recorded Events

The audit log records significant actions that affect the security, integrity or
administration of the application.

Routine activity such as page navigation or viewing task boards is intentionally
excluded.

Only meaningful state changes generate audit events.

---

# 10. Authentication Events

Authentication events describe changes to user authentication state.

Typical events include:

```
auth.login

auth.logout

auth.session_revoked

auth.password_reset

auth.password_changed
```

These events provide administrators with visibility into account activity
without recording sensitive authentication data.

---

## Login

Generated after successful authentication.

Typical information includes:

- acting user
- login time
- session identifier (where applicable)

Passwords are never recorded.

---

## Logout

Generated when a user explicitly signs out.

Automatic session expiry is treated separately.

---

## Session Revocation

Generated whenever a session is revoked before its normal expiry.

Typical causes include:

- administrator deactivation
- password reset
- explicit administrator action
- user logout from all devices

---

# 11. User Management Events

Administrative user lifecycle actions are fully audited.

Typical events include:

```
user.created

user.activated

user.deactivated

user.reactivated

user.password_reset

user.anonymised
```

These events form an important compliance record.

---

## User Deactivation

Records:

- acting administrator
- affected user
- timestamp

Additional metadata may include:

- revoked session count
- previous active state

---

## User Reactivation

Records:

- acting administrator
- affected user

Historical session revocations remain unchanged.

---

## User Anonymisation

Anonymisation is considered a permanent administrative action.

Audit events record:

- acting administrator
- anonymised account
- timestamp

Personally identifiable information removed during anonymisation is **not**
duplicated within audit metadata.

---

# 12. Company Events

Administrative company operations are recorded.

Typical events include:

```
company.created

company.updated

company.archived

company.restored
```

---

## Company Creation

Records:

- creator
- company identifier

---

## Company Updates

Significant administrative changes may generate update events.

Minor presentation changes need not always be recorded.

---

## Company Archive

Archiving records:

- acting administrator
- archived company
- timestamp

Tasks and sections remain unaffected.

---

## Company Restore

Restoration records:

- acting administrator
- restored company

Historical archive events remain preserved.

---

# 13. Section Events

Sections generate audit events for significant lifecycle changes.

Typical events include:

```
section.created

section.updated

section.archived

section.restored
```

---

## Section Archive

Archiving a section records:

- administrator
- affected section
- company

Tasks remain attached.

---

## Section Restore

Restoration generates a corresponding audit event.

The original archive event remains visible.

---

# 14. Task Events

Task activity generates both:

- task history
- audit events

These systems complement rather than replace one another.

---

## Recorded Task Events

Typical events include:

```
task.created

task.updated

task.deleted

task.restored

task.permanently_deleted

task.completed

task.reopened
```

---

## Creation

Records:

- creator
- task identifier

Task history additionally records operational detail.

---

## Completion

Completion records:

- acting user
- completion time

Repeated completion attempts do not generate duplicate events.

---

## Deletion

Soft deletion records:

- acting user
- deleted task

Comments, assignments and history remain preserved.

---

## Permanent Deletion

Permanent deletion is administrator-only.

This event is especially important because it represents irreversible data
removal.

---

## Restoration

Restoring a deleted task generates a new audit event.

The original deletion event remains visible.

---

# 15. Assignment Events

Assignment changes generate audit records where they materially affect
responsibility.

Typical events include:

```
task.assignee_added

task.assignee_removed

task.assignees_replaced
```

Metadata may include:

- affected user
- task identifier

These events complement the task history timeline.

---

# 16. Comment Events

Routine comment editing is primarily represented within task history.

Administrative actions may additionally generate audit events.

Examples include:

```
comment.deleted

comment.restored
```

Audit logging focuses on significant moderation activity rather than ordinary
collaboration.

---

# 17. Administrative Events

Administrator actions outside normal task management are audited.

Examples include:

```
audit.viewed

settings.updated

administrator.login

administrator.logout
```

Where appropriate, viewing sensitive administrative resources may itself be
audited.

This provides accountability for privileged operations.

---

# 18. Event Naming Conventions

Event names follow a predictable pattern.

```
entity.action
```

Examples:

```
task.created

task.deleted

company.archived

section.restored

user.deactivated
```

Advantages include:

- consistency
- reliable filtering
- predictable reporting
- straightforward future expansion

New event types should follow the same convention wherever possible.

The following sections describe metadata standards, redaction policy, filtering
behaviour, retention and operational guidance.

# 19. Audit Metadata

Audit metadata provides additional structured information describing an event.

Metadata supplements an audit record but should never be required to understand
the event itself.

Example:

```
Event

Task Deleted
```

may include metadata such as:

```
{
    "task_title": "Prepare Beer Festival",
    "section": "Front of House"
}
```

The event remains understandable even if metadata is unavailable.

---

## Typical Metadata

Examples include:

- previous values
- new values
- usernames
- display names
- company names
- section names
- task titles
- session counts
- restoration status

Metadata should always describe the action rather than duplicate the entire
entity.

---

## Structured Storage

Metadata is stored using structured key/value data rather than free-form text.

Advantages include:

- consistent filtering
- easier reporting
- future API support
- predictable rendering

Metadata keys should remain stable wherever practical.

---

# 20. Metadata Redaction

Audit metadata must never contain secrets.

Examples of prohibited values include:

- passwords
- password hashes
- authentication tokens
- CSRF tokens
- session cookies
- API keys
- encryption keys

If a value is considered sensitive enough that it should never appear in
application logs, it should also never appear in the audit log.

---

## Personally Identifiable Information

Personally identifiable information (PII) should be recorded only where
necessary for administrative accountability.

Examples that may legitimately appear include:

- usernames
- display names

These values assist administrators in understanding historical events.

When a user is later anonymised, the audit record preserves the historical
relationship without exposing newly removed personal data.

Further details are provided in the GDPR anonymisation documentation.

---

# 21. Filtering

The audit log supports administrator filtering to simplify investigation of
historical events.

Typical filters include:

- event type
- entity type
- acting user
- date range
- search text

Filtering never modifies the underlying audit records.

It only changes the subset displayed.

---

## Event Type Filtering

Administrators may view only particular categories of events.

Examples:

```
Task Events

↓

task.created

task.deleted

task.restored
```

or

```
User Events

↓

user.deactivated

user.anonymised
```

This allows rapid investigation of specific administrative actions.

---

## Entity Filtering

Audit events may also be filtered by the affected entity.

Examples include:

- user
- company
- section
- task

Entity filtering assists when investigating the lifecycle of a single object.

---

## Date Filtering

Administrators may restrict results to a defined time period.

Examples include:

- today
- last seven days
- current month
- custom date range

All comparisons are performed using UTC timestamps.

Displayed dates are converted into the configured application timezone.

---

## Search

Search provides a text-based filter across audit descriptions and other
searchable fields.

Search narrows visible audit events.

It never exposes hidden data.

---

# 22. Pagination

Audit logs are paginated to maintain predictable performance.

Typical ordering is:

```
Newest

↓

Oldest
```

Pagination ensures:

- responsive administration pages
- reduced database load
- predictable memory usage

Filtering is applied before pagination.

---

# 23. Relationship with Task History

Audit logging and task history serve different purposes.

---

## Task History

Audience:

```
Operational Users
```

Answers:

> What happened to this task?

Examples:

- completed
- reopened
- moved
- comment added

---

## Audit Log

Audience:

```
Administrators
```

Answers:

> Who performed this administrative or significant business action?

Examples:

- user deactivated
- company archived
- task permanently deleted

---

## Complementary Systems

Both systems may record the same operation from different perspectives.

Example:

Deleting a task produces:

```
Task History

↓

Task Deleted
```

and

```
Audit Log

↓

task.deleted
```

The former explains the task lifecycle.

The latter provides administrative accountability.

---

# 24. Audit Record Visibility

Audit records are visible only to Global Administrators.

Standard users never receive access through:

- dashboards
- company pages
- section pages
- task pages
- search
- direct URLs

Server-side permission checks protect every audit route.

---

# 25. Error Handling

Audit generation forms part of the originating transaction.

If an operation fails before commit:

```
Business Update

↓

Rollback

↓

Audit Record Removed
```

No orphaned audit events remain.

Likewise, an audit record is never committed for an operation that ultimately
fails validation or is rolled back.

---

# 26. Consistency Principles

Every audit event should satisfy the following rules.

- Generated automatically.
- Created by the Service layer.
- Written within the same transaction.
- Never modified after creation.
- Never duplicated unnecessarily.
- Never contain sensitive secrets.
- Always identify the acting user where possible.
- Always identify the affected entity.
- Always include a timestamp.

Following these principles ensures the audit log remains a trustworthy record
of application activity.

The final section documents retention strategy, developer guidance, future
expansion and operational best practices.

# 27. Retention Strategy

Audit records form part of the permanent operational history of Billson's
Tasks.

Unlike authentication sessions or temporary application data, audit records are
not routinely deleted.

Long-term retention supports:

- operational investigations
- historical reporting
- security reviews
- compliance requirements
- administrator accountability

Where organisational policy requires archival, audit records should be archived
rather than modified.

---

## Data Preservation

Audit records should remain readable even if related entities change.

Examples include:

- renamed companies
- restored sections
- deleted tasks
- anonymised users

The audit record represents the historical state at the time the event
occurred.

---

# 28. System Events

Most audit records are associated with an authenticated user.

Some events, however, originate from the application itself.

Examples include:

- scheduled maintenance
- automated cleanup
- expired session removal
- background maintenance jobs

These events should identify the actor as the system rather than attributing
them to an administrator.

Example:

```
Actor

System

↓

Expired Sessions Deleted
```

This distinguishes automated behaviour from manual administrative activity.

---

# 29. Developer Guidelines

Developers should generate audit events whenever an operation changes the
meaningful state of the application.

Typical examples include:

- creating entities
- deleting entities
- restoring entities
- archiving entities
- changing user lifecycle state
- performing administrative actions

Routine read operations should not normally generate audit events.

---

## Where Audit Events Belong

Audit creation belongs within the Service layer.

Correct flow:

```
Route

↓

Permission Check

↓

Service

↓

Repository Updates

↓

Audit Repository

↓

Commit
```

Repositories should never create audit records directly.

Templates must never generate audit events.

---

## Event Ordering

Audit events should be generated after successful validation but before the
transaction commits.

```
Validate

↓

Update Entity

↓

Create Audit Event

↓

Commit
```

This ensures the audit record accurately reflects the completed operation.

---

## Event Granularity

Audit events should describe meaningful business actions rather than low-level
database operations.

Preferred:

```
Company Archived
```

Avoid:

```
Updated is_archived field
```

Preferred events describe intent rather than implementation.

---

# 30. Best Practices

The following practices should be followed when extending the audit system.

---

## Keep Events Predictable

Use consistent event naming.

Examples:

```
task.created

task.deleted

task.restored
```

Avoid introducing multiple names for the same operation.

---

## Record the Actor

Whenever possible, identify the authenticated user responsible for the action.

System-generated events should explicitly identify the system as the actor.

---

## Avoid Excessive Detail

Audit records should provide sufficient context without duplicating entire
database records.

Good:

```
Archived company "Anchor Hotels"
```

Poor:

```
Complete serialisation of Company object
```

The audit log is intended for investigation rather than data export.

---

## Never Store Secrets

Audit records must never contain:

- passwords
- password hashes
- authentication cookies
- CSRF tokens
- session identifiers in plaintext
- encryption keys
- API credentials

Sensitive operational information should be omitted or appropriately
redacted.

---

## Preserve Historical Accuracy

Audit events should always describe what actually happened.

Subsequent changes must generate additional events rather than rewriting
history.

Example:

```
Task Deleted

↓

Task Restored

↓

Task Deleted Again
```

Each event remains independently visible.

---

# 31. Future Expansion

The audit framework has been designed to accommodate additional functionality
without structural redesign.

Potential future event categories include:

```
Notification Events

API Requests

Webhook Deliveries

Attachment Management

Recurring Tasks

Time Tracking

Role Changes

Permission Changes

Integration Activity
```

Future events should continue to follow the established naming convention:

```
entity.action
```

This preserves consistency across the application.

---

# 32. Testing Strategy

Audit logging is verified through automated testing at multiple levels.

Repository tests validate:

- persistence
- filtering
- ordering

Service tests verify:

- event generation
- metadata
- transaction behaviour

Route tests confirm:

- administrator access
- filtering
- pagination
- detail rendering

Security tests ensure:

- standard users cannot access audit routes
- cross-company isolation is preserved
- permission checks cannot be bypassed

Every newly introduced audit event should be accompanied by appropriate test
coverage.

---

# 33. Relationship to Other Systems

The audit log operates alongside several related systems.

## Task History

Provides operational history for individual tasks.

Audience:

```
Operational Users
```

---

## Authentication Sessions

Track active browser sessions.

Audience:

```
Authentication System
```

---

## Audit Log

Provides administrative accountability across the application.

Audience:

```
Global Administrators
```

Although these systems reference many of the same entities, they serve distinct
purposes and should not be treated as interchangeable.

---

# 34. Audit Logging Summary

The audit logging system is built upon several fundamental principles.

- Append-only records.
- Immutable history.
- Server-generated events.
- Service-layer responsibility.
- Transactional consistency.
- Administrator visibility.
- Secure handling of sensitive information.
- Predictable event naming.
- Structured metadata.
- Long-term historical preservation.

By recording significant actions in a consistent, immutable and security-aware
manner, the audit log provides administrators with a trustworthy record of
system activity while supporting operational troubleshooting, compliance,
historical investigation and future reporting requirements.