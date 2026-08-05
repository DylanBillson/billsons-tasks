# Billson's Tasks — Permissions

## 1. Purpose

This document describes the permission model used throughout Billson's Tasks.

Permissions are enforced entirely within the application layer.

The database stores relationships between entities, but never determines
whether a user is permitted to perform an action.

All permission decisions are evaluated by dedicated services before any state
change occurs.

This document covers:

- authentication
- authorisation
- user roles
- organisation boundaries
- permission inheritance
- server-side enforcement
- security principles

---

# 2. Permission Philosophy

Billson's Tasks follows several core security principles.

## 2.1 Server-Side Enforcement

Every permission is enforced on the server.

The user interface exists only for convenience.

Removing a button from the UI does **not** provide security.

Every route validates permissions regardless of:

- browser behaviour
- JavaScript
- hidden fields
- URL manipulation
- API requests

---

## 2.2 Least Privilege

Users receive only the permissions necessary to perform their work.

Examples:

- section members cannot administer users
- company membership does not automatically grant section access
- archived data is hidden unless explicitly permitted

Users never receive elevated access "just in case."

---

## 2.3 Explicit Membership

Access is always granted through explicit relationships.

Permissions are never inferred from unrelated entities.

Examples:

```
Company Membership
        │
        ▼
Company Dashboard Access
```

```
Section Membership
        │
        ▼
Section Board Access
```

A user must belong to a section before interacting with its tasks.

---

## 2.4 Separation of Responsibilities

Permission logic is isolated from:

- repositories
- templates
- database models

Instead, permission evaluation is centralised within dedicated services.

Typical flow:

```
Web Route
      │
      ▼
Permission Service
      │
      ▼
Business Service
      │
      ▼
Repository
```

This keeps behaviour consistent throughout the application.

---

# 3. Authentication

Authentication answers one question:

> Who is making this request?

Authentication occurs before any permission checks.

Successful authentication establishes:

- current user
- active session
- CSRF protection

Only authenticated users may access protected routes.

---

## Authentication Requirements

A valid session must satisfy all of the following:

- session exists
- session has not expired
- session has not been revoked
- associated user is active
- associated user has not been anonymised

Failure of any requirement immediately ends authentication.

---

## Authentication State

Users are either:

```
Authenticated
```

or

```
Unauthenticated
```

There are no partial authentication states.

---

# 4. User States

Permissions depend not only on user role but also on account state.

## Active User

```
is_active = true
```

May authenticate normally.

Permissions are evaluated according to role and memberships.

---

## Inactive User

```
is_active = false
```

Cannot authenticate.

Existing sessions are revoked.

No application permissions remain available.

---

## Anonymised User

```
is_anonymised = true
```

Cannot authenticate.

Cannot be reactivated.

Historical ownership remains intact.

No permissions are ever granted.

---

# 5. Global Roles

Billson's Tasks intentionally has very few global roles.

This keeps the security model understandable.

## Standard User

Default role.

Permissions are determined almost entirely by organisational membership.

---

## Administrator

Global administrator.

Administrators may:

- manage users
- archive companies
- restore companies
- archive sections
- restore sections
- view deleted tasks
- permanently delete tasks
- access audit logs
- manage application settings
- view all companies
- bypass normal membership restrictions

Administrator status is global.

It is not tied to any company.

---

# 6. Permission Resolution

Permissions are evaluated in a predictable order.

```
Authenticated?

        │
        ▼

User Active?

        │
        ▼

User Anonymised?

        │
        ▼

Administrator?

        │
        ▼

Organisation Membership?

        │
        ▼

Entity-Level Permission?

        │
        ▼

Action Allowed
```

Evaluation stops as soon as access is denied.

---

# 7. Organisation Boundaries

Companies are the highest permission boundary.

Every entity ultimately belongs to one company.

```
Company
    │
Section
    │
Section List
    │
Task
```

Cross-company access is never permitted for standard users.

This applies equally to:

- tasks
- comments
- history
- assignments
- dashboards

Administrators are the only exception.

---

# 8. Membership Hierarchy

Permissions are inherited through organisational relationships.

```
Company
    │
    ▼
Company Membership
```

grants access to company-level information.

```
Section
    │
    ▼
Section Membership
```

grants access to work performed within that section.

Task permissions are evaluated after organisational access has already been
confirmed.

---

# 9. Permission Services

All permission decisions are centralised.

Typical permission helpers include:

```
can_view_company()

can_view_section()

can_view_task()

can_update_task()

can_complete_task()

can_comment_on_task()

can_manage_task_assignees()

can_delete_task()

can_restore_task()

can_archive_company()

can_archive_section()

can_manage_users()

can_view_audit_log()
```

Routes should never duplicate permission logic.

Instead they delegate to the permission layer.

---

# 10. General Security Principles

The permission model follows several overarching rules.

- Deny by default.
- Grant access explicitly.
- Never trust client-side state.
- Validate every request.
- Preserve organisational isolation.
- Keep permission logic centralised.
- Separate authentication from authorisation.
- Record significant administrative actions in the audit log.

These principles form the foundation for every permission decision made within
Billson's Tasks.

The following sections describe how these principles apply to each user role
and every major area of the application.

# 11. Standard User Permissions

Standard users perform the majority of day-to-day work within Billson's Tasks.

Their permissions are intentionally limited to the companies and sections they
belong to.

They cannot bypass organisational boundaries.

---

## Company Access

A standard user may view a company only if they are a member of that company.

```
User
    │
Company Membership
    │
    ▼
Company Dashboard
```

Users cannot:

- view other companies
- search other companies
- guess company identifiers
- access archived companies

---

## Section Access

A user may access a section only if:

- the parent company is accessible, and
- the user is a member of the section.

Section membership is therefore the primary work-management permission.

---

## Task Visibility

Users may only view tasks that belong to accessible sections.

Hidden tasks include:

- tasks in inaccessible companies
- tasks in inaccessible sections
- deleted tasks
- archived sections
- archived companies

Administrators are exempt from these restrictions.

---

## Comments

Users may:

- view comments on accessible tasks
- create comments
- edit their own comments
- delete their own comments (where permitted)

Users cannot modify another user's comments.

---

## Assignments

Users may view task assignments for accessible tasks.

Assignment management depends upon the task permission service and may require
additional privileges.

---

# 12. Administrator Permissions

Administrators possess unrestricted access across the application.

Administrator permissions are global rather than company-specific.

Administrator access exists to support:

- operational support
- data recovery
- user management
- compliance
- troubleshooting

---

## Organisation Access

Administrators may view:

- every company
- every section
- every list
- every task

Membership is not required.

---

## Administrative Features

Administrators may access:

- Administration dashboard
- User management
- Audit log
- Archived companies
- Archived sections
- Deleted tasks

These areas are not available to standard users.

---

## Recovery Operations

Administrators may:

- restore deleted tasks
- permanently delete tasks
- restore archived companies
- restore archived sections

These actions are recorded in the audit log.

---

## User Lifecycle

Administrators may:

- activate users
- deactivate users
- reset passwords
- anonymise users

Administrators cannot:

- deactivate themselves
- anonymise themselves
- bypass anonymisation safeguards

---

## Audit Access

Administrators may inspect every audit record regardless of company ownership.

Audit visibility is intentionally global.

---

# 13. Company Permissions

Companies represent the highest organisational boundary.

Permission checks begin at the company level.

---

## Company Dashboard

A company dashboard is visible when:

```
Administrator

OR

Company Member
```

Otherwise access is denied.

---

## Company Metrics

Users only see metrics relating to companies they may access.

Examples include:

- task counts
- completion counts
- overdue work

Cross-company aggregation is never exposed to standard users.

---

## Company Navigation

Users cannot navigate directly to another company's dashboard simply by
changing the URL.

Server-side permission checks prevent this.

---

# 14. Section Permissions

Sections provide the primary working area for most users.

---

## Viewing Sections

Access requires:

- company membership
- section membership

or administrator privileges.

---

## Creating Tasks

Users may create tasks only within sections they can access.

Attempting to create tasks elsewhere results in permission denial.

---

## Updating Tasks

Task editing requires access to the parent section.

Additional business rules may also apply.

Examples include:

- deleted tasks
- archived sections
- archived companies

---

## Completing Tasks

Users may complete tasks visible to them.

Completion automatically records:

- acting user
- completion timestamp
- task history
- audit event (where applicable)

---

## Reopening Tasks

Completed tasks may be reopened by authorised users.

Reopening clears completion metadata while preserving historical records.

---

# 15. Membership Inheritance

Permissions are intentionally inherited in a predictable hierarchy.

```
Company Membership
        │
        ▼
Company Dashboard
```

```
Section Membership
        │
        ▼
Lists
        │
        ▼
Tasks
        │
        ▼
Comments
History
Assignments
```

Permissions never flow upwards.

Being assigned to a task does **not** grant access to its company.

Being able to comment does **not** grant administrative privileges.

---

# 16. Anonymous, Inactive and Anonymised Users

The application distinguishes between several non-active states.

---

## Anonymous Visitor

Not authenticated.

May only access public pages such as:

- login
- static assets

Everything else requires authentication.

---

## Inactive User

Cannot authenticate.

Any existing sessions are revoked immediately.

Protected routes redirect to the login page.

---

## Anonymised User

Authentication is permanently disabled.

No permissions remain available.

Historical ownership of entities remains intact for audit and reporting
purposes.

---

# 17. Permission Failure Behaviour

Permission failures never expose protected data.

Typical behaviour includes:

- redirecting to a safe page
- displaying an appropriate error message
- returning HTTP 403 where applicable
- recording administrative actions where necessary

Permission failures never reveal whether inaccessible entities exist.

This helps prevent information disclosure through identifier enumeration.

---

# 18. Design Summary

The role model intentionally remains simple.

```
Unauthenticated
        │
Authenticated
        │
 ┌──────┴──────┐
 │             │
Standard   Administrator
```

Actual access is determined by organisational membership rather than by a
large hierarchy of roles.

This keeps permission decisions predictable, testable and straightforward to
reason about.

The next section documents permissions for dashboards, task management,
comments, assignments and the remainder of the application.

# 19. Dashboard Permissions

Billson's Tasks provides multiple dashboards, each with its own permission
rules.

Although they share common metrics and presentation, their visibility differs.

---

## Global Dashboard

The global dashboard is the default landing page after authentication.

Standard users only see information relating to companies they can access.

Administrators see system-wide information.

```
Administrator
        │
        ▼
All Companies
```

```
Standard User
        │
        ▼
Accessible Companies Only
```

---

## Dashboard Metrics

Dashboard metrics are always permission filtered.

Examples include:

- open task count
- completed task count
- overdue tasks
- assigned tasks

Users never receive aggregate values for companies they cannot access.

---

## Company Dashboard

Company dashboards require:

```
Administrator

OR

Company Membership
```

Users are redirected away from inaccessible companies.

Direct URL manipulation cannot bypass these checks.

---

## My Tasks

The **My Tasks** dashboard displays only work assigned to the authenticated
user.

Assignment is evaluated using the authenticated account rather than company
membership alone.

Tasks are still filtered by visibility rules.

Hidden tasks remain hidden even if historical assignment records exist.

---

## Deleted Tasks

Deleted Tasks is an administrative feature.

Access requires administrator privileges.

Standard users cannot:

- list deleted tasks
- restore deleted tasks
- permanently delete tasks

---

## Archived Companies

Archived Companies is an administrator-only view.

It displays:

- archived companies
- archive dates
- restoration options

Standard users never see archived companies.

---

## Archived Sections

Archived Sections follows the same model.

Only administrators may:

- browse archived sections
- restore archived sections

---

# 20. Task Permissions

Task permissions are evaluated using both organisational access and task state.

A user must first be able to view the task before any additional permissions
are considered.

---

## View Task

Requirements:

- authenticated
- active account
- company access
- section access
- task not hidden by archival or deletion

or administrator privileges.

---

## Create Task

Users may create tasks only within accessible sections.

Creation automatically records:

- creator
- creation timestamp
- history event
- audit event (where applicable)

---

## Update Task

Users may update tasks they can access provided the task remains editable.

Updates include:

- title
- description
- due date
- list movement
- ordering

Every significant update generates task history.

---

## Move Task

Task movement requires permission to both:

- the source section
- the destination section

Cross-company movement is never permitted.

Drag-and-drop operations remain subject to the same server-side validation as
traditional forms.

---

## Complete Task

Users may complete accessible tasks.

Completion records:

- completed_at
- completed_by_user

History entries are generated automatically.

---

## Delete Task

Soft deletion requires appropriate task permissions.

Deletion:

- hides the task
- preserves history
- preserves comments
- preserves assignments

Only administrators may permanently remove tasks.

---

# 21. Assignment Permissions

Assignments represent responsibility rather than ownership.

Being assigned to a task does not automatically grant additional permissions.

---

## View Assignments

Anyone able to view the task may view its assignments.

---

## Add Assignment

Assignment management requires:

- task visibility
- permission to manage assignments

Only eligible users within the same section may be assigned.

---

## Remove Assignment

Assignment removal follows the same permission model.

Removing an assignee generates:

- task history
- audit events where appropriate

---

## Replace Assignments

Bulk replacement follows identical validation.

Every proposed assignee is independently checked.

Invalid assignments are rejected.

---

# 22. Comment Permissions

Comments inherit task visibility.

Users cannot interact with comments belonging to hidden tasks.

---

## Create Comment

Requirements:

- authenticated
- active account
- task visibility
- comment permission

The author is recorded automatically.

---

## Edit Comment

Users may edit their own comments.

Editing another user's comment is prohibited.

Administrators do not routinely edit user comments.

---

## Delete Comment

Users may delete comments they are authorised to remove.

Deletion is soft.

Historical relationships remain intact.

---

# 23. History Permissions

Task history is visible to anyone able to view the task.

History cannot be:

- edited
- reordered
- deleted

History entries are generated automatically by the application.

---

# 24. Filtering Permissions

Filtering never broadens visibility.

Filters only reduce the set of records already visible to the authenticated
user.

Examples:

Searching:

```
Visible Tasks

↓

Search

↓

Matching Visible Tasks
```

never

```
Search

↓

Previously Hidden Tasks
```

The same principle applies to:

- dashboards
- company views
- My Tasks
- deleted tasks
- audit logs

---

# 25. Navigation Permissions

Navigation reflects the authenticated user's permissions.

Users are shown only links they may legitimately access.

Examples:

Standard user:

```
Dashboard

Companies

My Tasks
```

Administrator:

```
Dashboard

Companies

My Tasks

Administration
    Users
    Audit Log
    Archived Companies
    Archived Sections
    Deleted Tasks
```

Hidden navigation items do not provide security.

Every destination independently validates permissions.

---

# 26. Route Protection

Every protected route follows the same pattern.

```
Authenticate

↓

Permission Check

↓

Business Logic

↓

Response
```

Business logic is never executed before permission validation succeeds.

---

# 27. Permission Consistency

Every interface—whether HTML, drag-and-drop, form submission or asynchronous
request—uses the same underlying permission services.

Examples include:

- task creation
- task movement
- assignment changes
- comment management
- archive restoration
- dashboard rendering

This guarantees identical behaviour regardless of how the request reaches the
server.

The final section documents administrator-only functionality, audit access,
server-side isolation guarantees and the overall security model.

# 28. Administration Permissions

Administrative functionality is intentionally isolated from day-to-day task
management.

These features are available only to Global Administrators.

---

## Administration Dashboard

Access requires:

```
Administrator
```

The dashboard provides an overview of:

- user activity
- archived entities
- deleted tasks
- audit activity
- system metrics

Standard users are redirected away from this area.

---

## User Management

Administrators may:

- view users
- activate users
- deactivate users
- reset passwords
- anonymise users

Administrators cannot:

- deactivate themselves
- anonymise themselves
- bypass anonymisation safeguards

All significant lifecycle operations generate audit events.

---

## Archived Companies

Administrators may:

- view archived companies
- restore archived companies

Standard users have no visibility of archived companies.

---

## Archived Sections

Administrators may:

- view archived sections
- restore archived sections

Archived sections remain excluded from standard dashboards and board views.

---

## Deleted Tasks

Administrators may:

- browse deleted tasks
- inspect deleted task details
- restore deleted tasks
- permanently delete tasks

Permanent deletion is intentionally restricted to administrators because it
cannot be reversed.

---

# 29. Audit Log Permissions

The audit log is an administrative resource.

It is not intended as an operational activity feed.

---

## View Audit Log

Only administrators may:

- browse audit events
- search audit events
- filter audit events
- inspect individual audit records

Standard users never receive access.

---

## Audit Integrity

Audit records are immutable.

Administrators cannot:

- edit events
- delete events
- rewrite history

If corrective action is required, a new audit event is generated.

---

## Audit Visibility

Administrators may view events relating to:

- any company
- any section
- any task
- any user

No organisation-based filtering applies.

---

# 30. Server-Side Isolation

Every permission decision is enforced by the server.

Isolation is never dependent upon:

- hidden form fields
- browser behaviour
- JavaScript
- CSS
- navigation visibility

Every request is independently validated.

---

## Company Isolation

Standard users cannot access another company's data by:

- changing URLs
- modifying identifiers
- altering query parameters
- submitting crafted requests

Repositories always operate on data sets that have already passed permission
validation.

---

## Section Isolation

Section membership prevents access to work belonging to other sections.

Users cannot:

- view foreign task boards
- move tasks into inaccessible sections
- comment on inaccessible tasks
- assign users within inaccessible sections

---

## Task Isolation

Every task request verifies:

- authenticated user
- organisational access
- task visibility
- current task state

Only after these checks succeed does the requested operation continue.

---

## Dashboard Isolation

Dashboard metrics are generated using permission-aware repository queries.

Users never receive statistics relating to inaccessible entities.

Examples include:

- company counts
- overdue totals
- completion metrics
- assigned work

Filtering cannot expose hidden information.

---

## Audit Isolation

Audit routes are administrator-only.

No audit data is ever exposed through:

- dashboards
- company pages
- task pages
- search
- filters

---

# 31. Security Principles

The permission system follows several core security rules.

## Deny by Default

Every request begins in a denied state.

Permissions must be explicitly granted.

---

## Authenticate First

Permission checks never occur before authentication.

Unauthenticated requests are rejected immediately.

---

## Validate Every Request

Every request is validated regardless of:

- request origin
- HTTP method
- UI controls
- JavaScript behaviour

---

## Centralised Decisions

Permission logic exists in one place.

Routes, templates and repositories must not duplicate permission rules.

This ensures:

- consistency
- maintainability
- predictable behaviour
- comprehensive testing

---

## Preserve Historical Integrity

Permission decisions never remove historical records.

Deletion, restoration and anonymisation preserve relationships wherever
possible.

This supports:

- audit requirements
- compliance
- operational troubleshooting

---

# 32. Testing Strategy

Permissions are verified using automated tests at multiple layers.

Repository tests ensure data isolation.

Service tests verify business rules.

Route tests confirm HTTP behaviour.

Integration tests validate complete request lifecycles.

Dedicated security tests verify:

- dashboard isolation
- audit isolation
- administrator-only routes
- company boundaries
- section boundaries
- task visibility
- user lifecycle restrictions

Every new permission should be accompanied by corresponding automated tests.

---

# 33. Future Expansion

The permission model has been designed to support future functionality without
fundamental redesign.

Potential future additions include:

- read-only users
- company administrators
- section managers
- custom roles
- API authentication
- personal access tokens
- delegated administration
- granular feature permissions

These features should extend the existing permission services rather than
introducing permission logic into routes or repositories.

---

# 34. Permission Model Summary

Billson's Tasks intentionally adopts a simple, layered permission model.

```
Authentication
        │
        ▼
User State
        │
        ▼
Global Role
        │
        ▼
Organisation Membership
        │
        ▼
Entity Permission
        │
        ▼
Business Rules
```

This structure ensures that:

- authentication and authorisation remain separate
- organisational boundaries are consistently enforced
- administrator privileges are explicit
- permission decisions are centralised
- historical integrity is preserved
- server-side validation is authoritative
- security remains predictable and testable

By combining a minimal global role model with explicit organisational
membership and centralised permission services, Billson's Tasks provides a
permission system that is straightforward to reason about, resilient against
client-side manipulation, and scalable as additional features are introduced.

# Feedback

Authenticated users may submit application feedback.

Feedback is available from every authenticated page.

Feedback:

• is emailed
• is not stored in the database
• records an audit event
• cannot be submitted anonymously
• uses CSRF protection