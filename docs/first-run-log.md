# First run from a clean clone

Produced by `python first_run.py`. Nothing here was fixed while it ran:
a workaround applied during a measurement measures the workaround.

- **When:** 2026-09-08 20:17 UTC
- **Commit:** `b0557d0`
- **Platform:** Windows-11-10.0.26200-SP0, Python 3.14.6
- **Result:** 10 of 11 steps succeeded, all of them

## The machine, and what the instructions leave out

| | |
|---|---|
| `git` | C:\Program Files\Git\cmd\git.EXE |
| `docker` | C:\Users\Cristina Crespo\AppData\Local\Programs\DockerDesktop\resources\bin\docker.EXE |
| `psql` | NOT FOUND on PATH |
| `DATABASE_URL` | postgresql://secrag:secrag@localhost:5433/secrag |
| `port` | 5433, from the README. .github/workflows/ci.yml uses 5432. One of the two is wrong, or the difference is undeclared. |
| `SEC user agent` | no such variable set. EDGAR requires a declared user agent; if src/edgar.py hardcodes one, say so in the README. |
| `LLM_PROVIDER` | unset -- retrieval needs no model, so this run does not either |

## The versions this run measured under

`requirements.txt` states floors and no ceilings, and nothing in this
repository records the versions the published figures were measured
with. Whether the numbers reproduce across this gap is the question the
run answers.

| | |
|---|---|
| `python` | 3.14.6 |
| `torch` | 2.14.0 |
| `sentence-transformers` | 6.0.1 |
| `transformers` | 5.16.1 |
| `numpy` | 2.5.3 |
| `psycopg2-binary` | 2.9.12 |
| `beautifulsoup4` | 4.15.0 |
| `lxml` | 6.1.3 |
| `anthropic` | 1.4.0 |
| `pyyaml` | 6.0.3 |
| `scikit-learn` | 1.9.0 |
| `scipy` | 1.18.1 |

## Each step

| Step | Exit | Seconds |
|---|---:|---:|
| install dependencies | ok | 1.3 |
| fetch filings from EDGAR | ok | 14.7 |
| parse HTML to sections | ok | 27.8 |
| verify section boundaries | ok | 0.3 |
| chunk | ok | 115.9 |
| embed locally on CPU | ok | 977.4 |
| load into Postgres | ok | 10.5 |
| reconcile the warehouse | ok | 0.4 |
| gold labels resolve | **1** | 1.1 |
| retrieval, with sabotage | ok | 43.7 |
| release artifacts | ok | 0.2 |

### Failed: gold labels resolve

`C:\Users\Cristina Crespo\Desktop\secrag-clean\.venv\Scripts\python.exe src/verify_labels.py --questions eval/questions_vnext.yaml --max-anchor-matches 8 --max-exceptions 4` exited 1 after 1.1s.

```text
  Q001    URBN-10-K-2026 chunk 121 exists as chunk_id 3417 but no longer contains '6,165,376'
  Q002    UAA-10-K-2026 chunk 126 exists as chunk_id 3203 but no longer contains '(Note 10) $ 4,966,370'
  Q003    LULU-10-K-2026 chunk 118 exists as chunk_id 2292 but no longer contains 'transfer of control'
  Q004    NKE-10-K-2026 chunk 85 exists as chunk_id 2420 but no longer contains '7.5'
  Q005    CROX-10-K-2025 chunk 169 exists as chunk_id 726 but no longer contains 'Deloitte'
  Q009    WRBY-10-K-2025 chunk 155 exists as chunk_id 3863 but no longer contains 'Store Count(1) 323 276 237'
  Q010    W-10-K-2025 chunk 151 exists as chunk_id 3631 but no longer contains 'data) Net revenue $ 12,457'
  Q011    PTON-10-K-2026 chunk 138 exists as chunk_id 2688 but no longer contains '(collectively, the “Connected'
  Q011    PTON-10-K-2026 chunk 145 exists as chunk_id 2695 but no longer contains 'of Ending Paid Connected'
  Q012    LULU-10-K-2026 chunk 100 exists as chunk_id 2274 but no longer contains '1,700,753'
  ... 13 more
Otherwise relabel:  python src/find_gold.py "the question" --expect "the answer"
```

## What to do with this

Each failure above is a defect in the instructions, in the code, or
in an assumption about the environment that was never written down.
Fix them one at a time and re-run this script; the log is
regenerated, so the diff shows what the fix moved.
