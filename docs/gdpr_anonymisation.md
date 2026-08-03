# Billson's Tasks — GDPR Anonymisation

## 1. Purpose

This document describes the GDPR anonymisation process implemented within
Billson's Tasks.

The application distinguishes clearly between:

- deactivation
- deletion
- anonymisation

Each serves a different purpose.

The anonymisation process permanently removes personally identifiable
information while preserving the historical integrity of operational data.

This allows the application to comply with data protection obligations without
destroying legitimate business records.

---

# 2. Design Philosophy

Billson's Tasks follows several principles when handling personal data.

## Historical Integrity

Historical records should remain understandable after a user leaves the
organisation.

Examples include:

- completed tasks
- comments
- task history
- audit records

Removing these records would damage the operational history of the system.

Instead, only the user's personally identifiable information is removed.

---

## Irreversibility

Anonymisation is intended to be permanent.

Once completed:

- original usernames cannot be recovered
- original display names cannot be recovered
- authentication cannot be restored

The process is deliberately one-way.

---

## Data Minimisation

Only information required for legitimate operational purposes is retained.

Personally identifiable information that is no longer required is removed.

Historical references remain because they are necessary to preserve audit
integrity and historical accountability.

---

## Separation from Deactivation

User deactivation and GDPR anonymisation are intentionally separate operations.

```
Deactivate

↓

User can no longer log in

↓

Historical data unchanged
```

```
Anonymise

↓

Personally identifiable information removed

↓

Historical relationships preserved
```

Many users will be deactivated without ever being anonymised.

---

# 3. Scope

The anonymisation process applies only to user accounts.

It does not anonymise:

- companies
- sections
- tasks
- comments
- audit records
- task history

Instead, those records continue to reference the anonymised user account.

---

# 4. Legal Rationale

The application is designed around the principle that historical business
records may continue to exist after personal information has been removed.

Examples include:

```
Task Completed

↓

Completed By

↓

Anonymous User
```

The operational event remains meaningful without revealing the individual's
identity.

This balances:

- historical accuracy
- accountability
- privacy
- compliance

The exact legal obligations applicable to a deployment will depend upon the
organisation's jurisdiction and retention policies.

---

# 5. Preconditions

An administrator cannot anonymise every account.

Several conditions must first be satisfied.

---

## Administrator Only

Only Global Administrators may initiate anonymisation.

Standard users have no access to this functionality.

---

## Authenticated Session

The administrator must have a valid authenticated session.

Expired or revoked sessions cannot perform anonymisation.

---

## Active CSRF Protection

All anonymisation requests require valid CSRF protection.

Requests lacking a valid token are rejected.

---

## Existing User

The target account must exist.

Requests referencing unknown users are rejected.

---

## Not Already Anonymised

The operation is only valid once.

Attempting to anonymise an already anonymised account has no effect.

The application treats anonymisation as an irreversible lifecycle event.

---

## Self-Anonymisation

Administrators cannot anonymise their own account while authenticated.

Preventing self-anonymisation avoids accidental administrative lockout.

---

# 6. Administrator Workflow

The intended workflow is deliberately cautious.

```
Locate User

↓

Review Account

↓

Review Warning

↓

Confirm Action

↓

Permission Validation

↓

Deactivate (if required)

↓

Revoke Sessions

↓

Anonymise Account

↓

Record Audit Event

↓

Commit Transaction
```

Multiple validation steps reduce the likelihood of accidental anonymisation.

---

# 7. User Lifecycle

A typical lifecycle is:

```
User Created

↓

Active

↓

Inactive

↓

Anonymised
```

Not every user will pass through every stage.

Some users may remain active indefinitely.

Others may be deactivated without ever being anonymised.

---

# 8. Relationship with User Deactivation

User deactivation is usually performed before anonymisation.

Deactivation ensures:

- authentication stops immediately
- active sessions are revoked
- further activity cannot occur

Only after the account has become inactive should anonymisation normally be
performed.

Although technically separate operations, they are intended to be used together
when permanently removing a user from the system.

The following sections describe how authentication changes, which data is
modified, what historical information is preserved, and why the process is
intentionally irreversible.

# 9. Authentication Changes

Anonymisation permanently removes the ability for a user to authenticate.

The account remains within the database for historical purposes, but it is no
longer capable of signing in.

---

## Authentication State

Before anonymisation:

```
User

↓

Active Session

↓

Authenticated
```

After anonymisation:

```
User

↓

Authentication Denied
```

Authentication checks reject anonymised users before permission evaluation
begins.

---

## Password Handling

Password hashes are no longer considered meaningful after anonymisation.

The application removes or replaces authentication credentials so that future
authentication is impossible.

The original password cannot be recovered.

---

## Session Revocation

All active authentication sessions are revoked as part of the anonymisation
process.

This includes:

- desktop browsers
- mobile devices
- remembered sessions

Revocation occurs before the anonymisation transaction completes.

Existing sessions cannot remain valid after anonymisation.

---

## Session Lifecycle

```
Active Sessions

↓

Revoked

↓

User Anonymised

↓

Authentication Permanently Disabled
```

No existing session may survive anonymisation.

---

# 10. Account State

Following anonymisation, the account enters a permanent terminal state.

Typical values include:

```
is_active = false

is_anonymised = true
```

The account remains present solely to preserve historical relationships.

The account should never return to an active state.

---

## Reactivation

Reactivation of anonymised users is intentionally unsupported.

Unlike deactivation:

```
Inactive

↓

Reactivate
```

An anonymised account follows:

```
Anonymised

↓

Terminal State
```

Attempting to reactivate an anonymised account is rejected.

---

# 11. Audit Implications

Anonymisation itself is an administrative action and therefore generates an
audit event.

The audit record includes:

- acting administrator
- anonymised account identifier
- timestamp

The audit event provides accountability without recreating personal data that
has been intentionally removed.

---

## Historical Audit Records

Audit records generated before anonymisation remain unchanged.

They continue to reference the same user identifier, ensuring chronological
integrity.

When displayed, the application presents the anonymised account using its new
anonymous identity rather than its former personal details.

---

# 12. Permission Changes

Immediately after anonymisation, the account loses every application
permission.

The account can no longer:

- authenticate
- access dashboards
- create tasks
- edit tasks
- comment
- administer the application

Permission evaluation terminates before organisational membership is
considered.

---

# 13. Membership Preservation

Company memberships and section memberships remain in the database.

These relationships are retained because they form part of the historical
record.

Example:

```
Company

↓

Former Member

↓

Anonymous User
```

The preserved relationships allow historical reports and audit records to
remain internally consistent.

Because the account cannot authenticate, retained memberships do not grant any
practical access.

---

# 14. Historical Ownership

Historical ownership is intentionally preserved.

Examples include:

```
Created By

Completed By

Deleted By

Comment Author

History Author
```

These foreign-key relationships continue to reference the anonymised account.

The associated personal information has been removed, but the ownership chain
remains valid.

This avoids orphaned records and preserves referential integrity.

---

# 15. Business Records

Business records are not modified beyond their reference to the anonymised
user.

Examples include:

- tasks
- comments
- task history
- audit events

Operational data continues to exist exactly as before.

Only the identifying information associated with the user changes.

---

# 16. Data Consistency

Anonymisation is performed within a single database transaction.

The process is effectively:

```
Validate Request

↓

Revoke Sessions

↓

Update User Record

↓

Generate Audit Event

↓

Commit
```

If any stage fails, the transaction is rolled back.

This prevents partially anonymised accounts or inconsistent authentication
state.

---

# 17. Design Principles

The authentication and lifecycle changes introduced by anonymisation are guided
by the following principles.

- Authentication must cease immediately.
- Existing sessions must not survive.
- Permissions must become unavailable.
- Historical ownership must remain intact.
- Membership relationships should be preserved for historical consistency.
- Anonymisation must be irreversible.
- The operation must be fully transactional.

The remaining sections describe the exact data transformations applied to the
user record, which fields are retained, how foreign-key relationships are
handled, and the operational guidance for administrators.

# 18. Data Transformation

The anonymisation process replaces personally identifiable information with
anonymous values while preserving the integrity of the underlying account.

The user record continues to exist, but it no longer represents an identifiable
individual.

---

## Personally Identifiable Information

Typical fields affected include:

```
Username

Display Name

Password Hash
```

These values are permanently replaced or removed.

The original values cannot be reconstructed.

---

## Anonymous Identity

Following anonymisation, the application generates a new anonymous identity.

Typical examples include:

```
Anonymous User

Anonymous User 42

Anonymised User
```

The exact naming convention is determined by the application.

The replacement identity exists solely to distinguish historical accounts from
one another.

---

## Username Replacement

The original username is discarded.

It is replaced with a unique anonymous value that satisfies database
constraints.

For example:

```
Original

↓

dylan.billson
```

becomes

```
anonymous-user-42
```

The original username is never retained elsewhere within the application.

---

## Display Name Replacement

Display names are similarly replaced.

Example:

```
Original

↓

Dylan Billson
```

becomes

```
Anonymous User
```

Historical task ownership therefore remains understandable without revealing
personal identity.

---

# 19. Data Preservation

Although identifying information is removed, many relationships are
intentionally preserved.

These include references from:

- tasks
- comments
- task history
- audit records
- created sections
- completed tasks
- deleted tasks

Preserving these relationships ensures that operational history remains
complete.

---

## Foreign Keys

Foreign-key relationships are **not** modified.

Example:

```
Task

↓

created_by_user_id

↓

Anonymous User
```

The relationship remains valid because the user record itself still exists.

---

## Historical Reports

Historical reporting continues to function after anonymisation.

Examples include:

- task completion statistics
- workload reports
- audit timelines
- operational history

Reports simply display the anonymised identity instead of the original user.

---

# 20. Data Not Modified

Many records remain intentionally unchanged.

Examples include:

- task titles
- task descriptions
- comments
- due dates
- completion timestamps
- archive timestamps
- audit timestamps

Only information capable of identifying the individual is removed.

Operational data remains intact.

---

# 21. Referential Integrity

One of the primary goals of anonymisation is preserving referential integrity.

Deleting user records would leave many orphaned relationships.

Instead:

```
User

↓

Anonymous User
```

allows every foreign key to remain valid.

Examples include:

```
Task

↓

Created By

↓

Anonymous User
```

and

```
Comment

↓

Author

↓

Anonymous User
```

No application records become detached.

---

# 22. Audit Preservation

Existing audit events continue to reference the anonymised account.

When administrators review historical events they will see the anonymised
identity.

Example:

```
2025

Task Deleted

Actor

↓

Anonymous User
```

The event remains historically accurate while protecting personal identity.

---

# 23. Task History Preservation

Task history behaves similarly.

Example timeline:

```
Task Created

↓

Comment Added

↓

Task Completed
```

continues to exist unchanged.

Only the displayed identity of the user changes.

The chronological sequence is preserved.

---

# 24. Comments

Comments themselves are not removed.

Doing so would damage operational history and collaborative discussions.

Instead:

```
Comment

↓

Author

↓

Anonymous User
```

The comment content remains available unless it has been separately deleted
through normal application workflows.

---

# 25. Company and Section Memberships

Membership records remain in place.

Although the anonymised account can never authenticate again, preserving
membership relationships helps explain historical ownership and reporting.

Because authentication is permanently disabled, retained memberships cannot be
used to gain access.

---

# 26. Operational Consequences

Following anonymisation:

- the user cannot log in
- passwords are unusable
- active sessions no longer exist
- navigation is unavailable
- permissions are unavailable
- historical ownership remains visible
- reports remain internally consistent
- referential integrity is preserved

The application therefore balances operational history with privacy protection.

---

# 27. Transaction Safety

Every data transformation occurs within a single database transaction.

```
Validate

↓

Deactivate User

↓

Revoke Sessions

↓

Replace Personal Data

↓

Generate Audit Event

↓

Commit
```

Any failure results in a complete rollback.

No partially anonymised account can exist.

---

# 28. Design Principles

The transformation process follows several important rules.

- Remove personally identifiable information.
- Preserve database relationships.
- Preserve historical ownership.
- Maintain referential integrity.
- Keep reports functional.
- Prevent future authentication.
- Perform all updates atomically.

The final section covers administrator guidance, operational procedures,
testing strategy and future enhancements to the anonymisation framework.

# 29. Administrator Guidance

GDPR anonymisation is one of the most significant administrative actions within
Billson's Tasks.

Because it is irreversible, administrators should confirm that
anonymisation—not simple deactivation—is the appropriate action.

Typical situations include:

- former employees
- right-to-erasure requests
- expired retention periods
- organisational data protection policies

In many other situations, deactivation alone is sufficient.

---

## Recommended Workflow

The recommended administrator workflow is:

```
Review User

↓

Confirm Account

↓

Deactivate Account

↓

Ensure No Further Access Required

↓

Review Warning

↓

Confirm Anonymisation

↓

Audit Event Recorded
```

The confirmation page intentionally emphasises that the operation cannot be
undone.

---

# 30. Warning and Confirmation

Before anonymisation, administrators are presented with a confirmation screen
summarising the consequences.

Typical warnings include:

- authentication will be permanently disabled
- personally identifiable information will be removed
- historical ownership will remain
- the operation cannot be reversed

The administrator must explicitly confirm the action before it proceeds.

---

## Confirmation Requirement

Confirmation protects against accidental anonymisation.

The operation should never occur through:

- a simple hyperlink
- a GET request
- accidental navigation

Instead, anonymisation requires:

- a POST request
- CSRF validation
- explicit administrator confirmation

---

# 31. Audit Requirements

Every anonymisation operation generates an audit record.

The audit event includes:

- acting administrator
- anonymised account identifier
- timestamp
- event type

The audit log intentionally does **not** preserve the personal information that
has been removed.

Instead, it records only the information necessary to demonstrate that the
operation occurred.

---

# 32. Testing Strategy

The anonymisation process is verified through automated tests at several
layers.

---

## Repository Tests

Repository tests verify:

- user updates
- anonymisation flags
- persisted anonymous values

---

## Service Tests

Service tests verify:

- validation
- session revocation
- audit generation
- transaction behaviour
- lifecycle transitions

---

## Route Tests

Route tests verify:

- administrator access
- confirmation workflow
- CSRF enforcement
- successful anonymisation
- permission denial for non-administrators

---

## Authentication Tests

Authentication tests confirm that anonymised users:

- cannot authenticate
- cannot create new sessions
- cannot regain access through existing sessions

These tests ensure anonymisation genuinely represents a terminal account state.

---

# 33. Operational Considerations

Organisations deploying Billson's Tasks should establish a documented policy
covering when anonymisation should occur.

Example considerations include:

- employee departure
- legal retention periods
- contractual obligations
- subject access requests
- right-to-erasure requests

The application provides the mechanism.

The organisation determines the policy.

---

## Backup Considerations

Database backups created before anonymisation may still contain historical
personal information.

Organisations should therefore ensure that backup retention policies comply
with their legal obligations.

Anonymising the live database does not automatically anonymise historical
backups.

---

# 34. Future Expansion

The anonymisation framework has been designed to support future enhancements
without altering its core principles.

Potential future additions include:

- configurable anonymisation policies
- scheduled anonymisation
- retention reminders
- bulk anonymisation
- organisation-specific retention periods
- automated lifecycle workflows

Future enhancements should continue to preserve:

- referential integrity
- historical accountability
- irreversible anonymisation
- transactional consistency

---

# 35. Relationship to Other Systems

GDPR anonymisation interacts with several other components of the application.

## Authentication

Authentication is permanently disabled.

---

## User Lifecycle

The account enters its terminal state.

---

## Audit Logging

The anonymisation action itself is permanently recorded.

---

## Task History

Historical ownership remains visible through the anonymised identity.

---

## Permissions

All permissions become unavailable because authentication is no longer
possible.

Each subsystem therefore continues to function without requiring foreign-key
relationships to be removed.

---

# 36. Design Principles Summary

The GDPR anonymisation implementation is based upon the following principles.

- Permanent removal of personally identifiable information.
- Preservation of historical business records.
- Preservation of referential integrity.
- Immediate revocation of authentication.
- Irreversible lifecycle transition.
- Explicit administrator confirmation.
- Comprehensive audit logging.
- Transactional consistency.
- Secure handling of authentication credentials.
- Separation between deactivation and anonymisation.

By anonymising identity rather than deleting historical records, Billson's
Tasks preserves operational history, reporting accuracy and audit integrity
while supporting organisations in meeting data protection obligations and
maintaining a clear, consistent and secure user lifecycle.