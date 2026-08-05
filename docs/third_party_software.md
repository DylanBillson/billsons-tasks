# Third-Party Software

Billson's Tasks vendors a small number of third-party libraries directly into the repository to avoid external CDN dependencies.

---

## SortableJS

**Project**

https://github.com/SortableJS/Sortable

**Version**

1.15.6

**Purpose**

Provides drag-and-drop support for:

- Section lists
- Task cards
- Future sortable interfaces

The library is configured to only allow dragging from explicit drag handles. This prevents accidental movement while interacting with cards.

Files:

```
app/web/static/vendor/sortablejs/Sortable.min.js
app/web/static/vendor/sortablejs/LICENSE
```

**Licence**

MIT License

Copyright (c) SortableJS contributors

The original licence text is included alongside the vendored source.

---

## Why libraries are vendored

Billson's Tasks intentionally vendors JavaScript libraries instead of loading them from CDNs because:

- deployments may not have Internet access
- avoids supply-chain changes
- guarantees deterministic builds
- simplifies long-term maintenance
- works in isolated Docker environments

Only libraries that are actively required by the application should be vendored.