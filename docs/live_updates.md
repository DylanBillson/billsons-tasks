# Billson's Tasks — Live Updates

## 1. Purpose

This document describes the polling-based live update system used throughout
Billson's Tasks.

The goal of the live update system is to allow multiple users to work within
the same company, section and task simultaneously while ensuring every user
eventually sees consistent information.

The implementation intentionally avoids persistent WebSocket connections.

Instead it uses lightweight HTTP polling combined with deterministic revision
hashes.

This document covers:

- architecture
- polling behaviour
- revision generation
- optimistic concurrency
- drag-and-drop protection
- conflict handling
- security
- performance
- future expansion

---

# 2. Design Goals

The live update system has several primary goals.

- Support multiple simultaneous users.
- Detect concurrent modifications.
- Avoid unnecessary page reloads.
- Minimise server resource usage.
- Work behind reverse proxies.
- Require no additional infrastructure.
- Remain compatible with standard HTTP deployments.

The design deliberately favours simplicity over maximum real-time latency.

---

# 3. Architecture

Rather than maintaining long-lived connections, every client periodically asks
the server whether the currently displayed resource has changed.

```
Browser

    │

    ▼

Revision Endpoint

    │

    ▼

Current Revision

    │

    ▼

Changed?

 ┌──────┴──────┐

 │             │

No            Yes

 │             │

 ▼             ▼

Continue   Refresh Region
```

Only when the revision changes does the browser request updated content.

---

# 4. Polling Model

Billson's Tasks uses fixed interval polling.

Every supported page periodically requests a lightweight revision endpoint.

Current resources include:

- section boards
- task detail pages

The polling interval is configured globally.

```
LIVE_UPDATES_POLL_INTERVAL_SECONDS
```

The interval may be changed without modifying application code.

---

# 5. Revision Endpoints

Each live-updated resource exposes a dedicated revision endpoint.

Examples include:

```
GET /api/live-updates/sections/{id}/revision

GET /api/live-updates/tasks/{id}/revision
```

Each endpoint returns:

- resource identifier
- resource scope
- current revision
- changed flag

The browser compares this revision against its locally stored value.

---

# 6. Revision Generation

A revision is a deterministic hash representing the current state of a
resource.

Section revisions include information such as:

- lists
- task ordering
- task counts
- task timestamps

Task revisions include information such as:

- task fields
- assignments
- comments
- history entries

Two identical resources always produce the same revision.

Any meaningful change produces a different revision.

---

# 7. Partial Refreshes

When a revision changes the browser requests only the affected fragments.

Examples include:

Section board:

```
Entire board
```

Task page:

```
Comments

History

Assignments

Task details
```

Refreshing fragments rather than entire pages preserves scroll position,
browser state and user context.

---

# 8. Optimistic Concurrency

Live updates are also used to prevent concurrent drag-and-drop conflicts.

Every reorder request includes the client's current section revision.

```
known_revision
```

The server compares this against the latest revision.

If the revisions match, the operation proceeds normally.

If they differ, the request is rejected.

---

# 9. Conflict Detection

Conflicting requests return HTTP 409.

The response includes:

- error code
- latest revision
- human-readable message

Example:

```json
{
    "code": "live_update_conflict",
    "current_revision": "...",
    "detail": "The board changed while you were editing."
}
```

The client updates its stored revision before requesting fresh content.

---

# 10. Drag-and-Drop Protection

SortableJS interactions remain optimistic.

Users experience immediate movement locally.

The server performs authoritative validation.

If another user modified the board first:

- the reorder is rejected
- the board refreshes
- no inconsistent ordering is committed

This prevents lost updates while maintaining responsive interaction.

---

# 11. Polling Behaviour

Polling intentionally pauses under several conditions.

Examples include:

- browser tab hidden
- network offline
- board currently saving
- drag-and-drop in progress
- active form editing

Polling resumes automatically once interaction finishes.

This reduces unnecessary refreshes and avoids disrupting user input.

---

# 12. Live Update Status

Pages expose a small status component indicating current synchronisation.

Possible states include:

- synchronised
- checking
- updating
- offline
- error
- conflict

The status is purely informational.

Permission decisions always remain server-side.

---

# 13. Performance

Revision endpoints are intentionally lightweight.

They return only metadata.

Large HTML fragments are fetched only when necessary.

Benefits include:

- lower bandwidth
- fewer database queries
- reduced rendering
- predictable polling cost

For unchanged pages the payload remains extremely small.

---

# 14. Security

Revision endpoints use exactly the same permission services as the remainder
of the application.

Users cannot poll resources they cannot access.

Responses never reveal whether inaccessible resources exist.

Unknown and inaccessible resources both return identical responses.

Optimistic concurrency validation is also performed entirely on the server.

Client-provided revisions are never trusted.

---

# 15. Server-Side Enforcement

Every live update request follows the standard request pipeline.

```
Authenticate

↓

Permission Check

↓

Current Revision

↓

Response
```

No revision information is exposed before permission validation succeeds.

---

# 16. Browser Integration

The browser exposes a single coordination object.

```
window.BillsonsLiveUpdates
```

This provides shared functionality including:

- polling
- revision refresh
- conflict handling
- status updates

Other page-specific JavaScript interacts only with this public API.

---

# 17. Configuration

The following application setting controls polling frequency.

```
LIVE_UPDATES_POLL_INTERVAL_SECONDS
```

Increasing the interval reduces server load.

Reducing the interval decreases visible update latency.

The implementation does not require application restarts beyond normal
configuration reload.

---

# 18. Future Expansion

The architecture intentionally supports future transport mechanisms.

Possible future improvements include:

- Server-Sent Events
- WebSockets
- notification subscriptions
- background notification delivery
- collaborative editing

These technologies could reuse the same revision generation and permission
services without redesigning application logic.

---

# 19. Testing Strategy

The live update system is verified using multiple test layers.

Repository tests verify revision generation.

Service tests verify revision comparison.

Route tests verify endpoint behaviour.

Integration tests verify:

- polling endpoints
- drag-and-drop conflicts
- optimistic concurrency
- permission enforcement
- company isolation

Static asset tests verify JavaScript integration.

Together these ensure consistent behaviour across both server and browser.

---

# 20. Design Summary

The live update system follows a simple layered model.

```
Browser

↓

Revision Endpoint

↓

Revision Comparison

↓

Fragment Refresh

↓

Updated Interface
```

Optimistic concurrency extends this model by validating every modifying request
against the latest server revision.

This approach provides collaborative behaviour suitable for typical business
task management while avoiding the operational complexity of persistent
real-time connections.