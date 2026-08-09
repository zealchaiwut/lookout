# lookout

Lookout is a personal intelligence layer that periodically inspects a named target project—reading local files, GitHub activity, and structured notes—and surfaces a concise digest of what has changed and what needs attention. It runs as a local CLI tool, keeping all data within your own environment and committing a deterministic audit trail to this repository. Each run validates vault integrity so the knowledge base stays internally consistent over time.

## Running a lookout

```
bin/lookout <target>
```

Where `<target>` is a key defined in `targets.yaml` (e.g. `perf-coach` or `commander`).

## Design and product context

- **[PRODUCT.md](PRODUCT.md)** — what lookout is, who it is for, and the core user flows.
- **[DESIGN.md](DESIGN.md)** — the design system: tokens, typography, and visual intent.

## Roadmap status

| Sprint | Scope |
|--------|-------|
| sprint-1 | Repo scaffold, vault linter, run wrapper (this sprint) |
| sprint-2 | Collectors arrive — gathering from GitHub, local files, and Notion |
| sprint-3 | Synthesis pipeline — summarisation, diff digests, and report generation |
