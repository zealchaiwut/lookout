# viral-radar — Spec workspace (Lookout)

Working Spec pack living in Lookout. Portable files here are meant to be
promoted into `~/dev/viral-radar/` when approved (`lookout promote-spec`).

| File | Status |
|------|--------|
| `api.yaml` | Draft — generated from README endpoint tables (53 GET paths) |
| `PRODUCT.md` / `DESIGN.md` | Mirrored from the clone when absent; vault wins once present |
| `plan.md` | Acceptance checklist stub |
| `mock/` | Fixtures for mock validate |
| `status.yaml` | Lifecycle: `draft` → `in-review` → `approved` → `promoted` |

Until `api.yaml` is copied into the viral-radar clone root, gather still
reports `API ✗` on the Spec pack badge.
