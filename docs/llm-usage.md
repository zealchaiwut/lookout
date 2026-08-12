# LLM usage

Lookout is deterministic by default. A handful of stages produce output that no
amount of regex can make useful, and those — and only those — may call a model.

**The rule: every model call goes through `llm.ask()`, and `llm.ask()` only ever
shells out to `claude -p`.** That bills the Claude.ai subscription. Nothing in
this repository may import an SDK or read an API key.

---

## Why

There are two ways to reach a Claude model:

| Surface | Funded by | Allowed here |
|---|---|---|
| `claude -p "…"` (CLI, print mode) | Claude.ai subscription | **yes — the only permitted path** |
| `anthropic` SDK / HTTP API | metered API credit | **no** |

Lookout runs nightly across every registered target. A metered path would turn a
background sweep into a recurring bill with no ceiling. The subscription path has
a ceiling by construction.

`tests/test_pipeline_wiring.py::test_no_module_imports_an_llm_sdk` fails the
build if any module outside `llm.py` mentions `import anthropic`,
`from anthropic`, or `ANTHROPIC_API_KEY`.

---

## The four guarantees

`llm.py` enforces these so callers don't have to think about them.

**1 — Subscription only.** The backend is `["claude", "-p", prompt, "--model", model]`.
There is no other code path.

**2 — Cached.** Responses are keyed by `sha256(model + prompt)` under
`vault/.llm-cache/` (gitignored). Re-running a pipeline over unchanged input
costs nothing. This matters because the same prompt is rebuilt on every run.

**3 — Never fatal.** A missing binary, a non-zero exit, a timeout, or an empty
response returns the caller's `fallback` string. This mirrors `gather.py`, where
an unreachable source is recorded as `absent` and the run still exits 0. A model
being unavailable must never break a snapshot.

**4 — Off by default.** `ask()` returns the fallback without spawning anything
unless `LOOKOUT_LLM=1`. The nightly sweep therefore spends nothing.

---

## Switching it on

```bash
# one target, one stage
LOOKOUT_LLM=1 python capability_card.py asset-studio

# one target, whole derive pass
LOOKOUT_LLM=1 python derive.py asset-studio

# check the wiring without spending anything
python llm.py --status
```

| Variable | Default | Meaning |
|---|---|---|
| `LOOKOUT_LLM` | unset (off) | `1`/`true`/`yes`/`on` enables model calls |
| `LOOKOUT_LLM_MODEL` | `haiku` | model passed to `claude --model` |
| `LOOKOUT_LLM_TIMEOUT` | `120` | seconds before a call is abandoned |

Haiku is the default deliberately. Every task below is structured, bounded, and
mechanical; nothing here needs Sonnet, and nothing here justifies Opus.

---

## Where it is used, and where it is not

Three stages. Each one had a deterministic implementation that produced
structurally valid, semantically empty output.

### 1. Capability card description — `capability_card._build_what_it_is`

The deterministic answer is *"`<target>` is a project tracked by Lookout via
Commander"*, which is true of every target and therefore says nothing. With
enrichment on, the target's own README (first 6 000 chars) plus its documented
GET endpoints are summarised into at most two sentences.

**Preserved across runs.** A real description already on the card survives a
deterministic run — the same protection `## Notes for AI` has always had.
Without it, the nightly sweep would overwrite the good description with the
generic sentence and the next enriched run would have to buy it again. So this
is one call per target, ever, until the README changes enough to be worth
re-running.

### 2. Situation one-liner — `synthesize._capability_what_it_is`

**No call of its own.** It reads the description out of `capability.md` and
reuses it. A target costs at most one description call per run, not two. If the
card holds only the generic sentence, the one-liner falls back to reporting
health.

### 3. Atlas relevance in the assessment pass — `assessment_pass._rank_atlas_notes`

The deterministic pass linked the *first three atlas notes alphabetically* for
each target the idea touched, regardless of what the idea said. For a target with
28 atlas notes that is close to noise. With enrichment on, the model is shown the
idea's freeform text and the full slug list, and picks up to three relevant notes.

**Its answer is intersected with the real slug list before use.** A slug the
model invents is discarded. This preserves the DESIGN.md §9 invariant that every
`[[wikilink]]` in an assessment resolves to a real file. If the model returns
nothing usable, the deterministic first-three answer stands.

Skipped entirely when the target has three or fewer atlas notes — there is
nothing to rank.

### Deliberately not using it

| Stage | Why not |
|---|---|
| `atlas_trace` | Real import traversal. Every node is a file that exists. An LLM would only add the risk of a fabricated edge — the exact failure the module was built to prevent. |
| `drift` | Regex over docs vs git history. The signal is textual and verifiable. |
| `capability_map` | Set intersection over documented paths. A guess here would put a false edge on the fleet map. |
| `ideas_ledger`, `ship_pass` | Frontmatter bookkeeping. |
| `_collect_endpoints` | Parses documented tables. Lookout is read-only against targets and must not call a target's API to introspect it. |

The pattern: **a model may choose or describe; it may not assert a relationship
that the vault cannot confirm.**

---

## Cost shape

Per target, per enriched run:

| Stage | Calls | Input |
|---|---|---|
| capability card | 1, then cached and preserved | ~6 KB README + endpoint list |
| situation one-liner | 0 | — |
| assessment pass | ≤1 per (idea × target), capped at 3 ideas per run | idea text + slug list |

A full enriched sweep of five targets is single-digit Haiku calls on the first
run and near zero afterwards. The nightly sweep is zero by default.

---

## Adding a new LLM-backed stage

1. Write the deterministic version first. It becomes the `fallback` and it is
   what runs nightly.
2. Call `llm.ask(prompt, fallback=…, purpose="stage:target")`. Never
   `subprocess.run(["claude", …])` directly.
3. If the output names anything — a file, a note, a project — validate it against
   the vault before writing it. Grounding is not the model's job.
4. If the output is expensive and stable, preserve it across deterministic runs
   the way the capability description is preserved.
5. Add a test that the stage still produces valid output with `LOOKOUT_LLM` unset.

---

## Note on the fleet

`asset-studio` already shells out to the `claude` CLI for its own
`POST /api/outline` endpoint, so this is the established pattern across these
projects rather than a new one. Commander's own model policy
(`~/dev/CLAUDE.md`) reaches the same conclusion from the other direction: prefer
the subscription-funded CLI, default to Haiku for mechanical work, and never
default to Opus.
