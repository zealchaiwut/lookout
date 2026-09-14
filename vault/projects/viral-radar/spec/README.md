# viral-radar — Spec workspace (Lookout)

Working Spec pack living in Lookout. Portable files here are meant to be
promoted into `~/dev/viral-radar/` when approved (`lookout promote-spec`).
Readable view: [[projects/viral-radar/spec|Spec Hub]] (sidebar hides this folder).

| File | Status |
|------|--------|
| `api.yaml` | Draft — generated from README endpoint tables |
| `PRODUCT.md` / `DESIGN.md` / `SCHEMA.md` | Mirrored from the clone when absent; vault wins once present |
| `status.yaml` | Lifecycle: `draft` → `in-review` → `approved` → `promoted` |

```bash
bin/lookout spec validate viral-radar
bin/lookout spec submit viral-radar
bin/lookout spec approve viral-radar
bin/lookout promote-spec viral-radar          # or --dry-run first
```
