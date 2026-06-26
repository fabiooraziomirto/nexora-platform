# Paper build & reproduction

This directory holds the journal paper draft for Nexora, targeting
*Internet of Things and Cyber-Physical Systems* (Elsevier, Q1).

## Files

| File | Purpose |
|------|---------|
| `nexora.tex` | Full paper draft (elsarticle). Architecture figure is inline TikZ — no external render step. |
| `references.bib` | Bibliography. **Every entry is marked `VERIFY`** — confirm exact venue/year before submission. |
| `related-work-comparison.md` | Working notes for §II + the full feature matrix. |
| `experimental-evaluation.md` | Working notes for §V + reproduction commands. |
| `results/` | Raw benchmark JSON (committed after running `perf-eval.py`). |

## Build the PDF

Requires a LaTeX distribution with the `elsarticle` class (TeX Live / MiKTeX).

```bash
cd docs/paper
latexmk -pdf nexora.tex          # or: pdflatex nexora && bibtex nexora && pdflatex x2
```

The architecture figure (Fig. 1) is drawn with TikZ and needs no PlantUML,
Graphviz, or Java.

## Before submission — checklist

1. **Remove all `\TODO{...}` markers.** Grep to find them:
   ```bash
   grep -n 'TODO' nexora.tex
   ```
   Every experimental number, the author block, and the hardware description
   are `\TODO` placeholders.
2. **Fill the results tables** (§5.1–5.3) from the benchmark JSON — see below.
3. **Verify every `references.bib` entry** (remove the `VERIFY` notes once
   confirmed against the original sources).

## Reproduce the experiments

The numbers in §5 come from the committed harness. Run against a live stack:

```bash
# 1. Start the stack (Docker Compose, smoke profile)
docker compose -f docker-compose.dev.yml --profile smoke up -d --build

# 2. Run the benchmark suite; capture JSON + human-readable log
python3 scripts/perf-eval.py \
    --base-url http://localhost:8000 \
    --fleet-url http://localhost:8006 \
    > docs/paper/results/perf-eval.json \
    2> docs/paper/results/perf-eval.txt

# 3. (optional) dispatch round-trip latency (§5.4)
bash scripts/perf-dispatch-latency.sh
```

Then transcribe the p50/p95/p99 values from `results/perf-eval.json` into the
corresponding `\TODO{}` cells of `nexora.tex` (tables `tab:ingest`, `tab:slo`,
`tab:fleet`) and record the test hardware in the §5 preamble.

> Note: the harness needs a running stack. Without Docker, the services can also
> be started locally with `uvicorn` + SQLite (`KAFKA_ENABLED=false`,
> `AUTH_ENABLED=false`) and benchmarked against `localhost` — document whichever
> environment you actually measured on.
