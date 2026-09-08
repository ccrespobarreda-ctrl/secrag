# Relabelling log

Applied 2026-09-08 20:48 UTC by `apply_relabel.py --apply`.

## The rule

A label moved if and only if its anchor was no longer inside the chunk
it named, `tests/fixture_corpus.json` held the text that position had
when the figures were published, and exactly one chunk of the same
document in `data/chunks.json` had identical content once whitespace was
flattened. Every other case was left alone and is listed below.

Not proximity: Q029's release text is identical to chunk 80 while the
nearest candidate is 79, and Q001's anchor appears in five chunks of the
same filing, one of which was rejected by hand in August.

## What changed

`eval/questions_vnext.yaml`

- before: `e9cde5d2650b2416476d45025eab9ecf8615608f21c33747ee29dc04f42e7499`
- after:  `1f6f43660afcab94d9b0d23d52b78df3ac116d500071cf5eff707bac102db11a`

| Question | Document | Was | Now | Offset |
|---|---|---:|---:|---:|
| Q001 | `URBN-10-K-2026` | 121 | 118 | -3 |
| Q002 | `UAA-10-K-2026` | 126 | 123 | -3 |
| Q003 | `LULU-10-K-2026` | 118 | 114 | -4 |
| Q004 | `NKE-10-K-2026` | 85 | 83 | -2 |
| Q005 | `CROX-10-K-2025` | 169 | 166 | -3 |
| Q009 | `WRBY-10-K-2025` | 155 | 153 | -2 |
| Q010 | `W-10-K-2025` | 151 | 150 | -1 |
| Q011 | `PTON-10-K-2026` | 138 | 137 | -1 |
| Q011 | `PTON-10-K-2026` | 145 | 144 | -1 |
| Q012 | `LULU-10-K-2026` | 100 | 96 | -4 |
| Q014 | `URBN-10-K-2026` | 119 | 116 | -3 |
| Q015 | `CROX-10-K-2025` | 169 | 166 | -3 |
| Q018 | `UAA-10-K-2026` | 217 | 214 | -3 |
| Q025 | `UAA-10-K-2026` | 86 | 84 | -2 |
| Q025 | `UAA-10-K-2026` | 87 | 85 | -2 |
| Q027 | `GAP-10-K-2026` | 57 | 55 | -2 |
| Q027 | `GAP-10-K-2026` | 102 | 99 | -3 |
| Q028 | `W-10-K-2025` | 165 | 164 | -1 |
| Q029 | `ANF-10-K-2026` | 83 | 80 | -3 |
| Q030 | `HNST-10-K-2025` | 172 | 171 | -1 |
| Q032 | `LULU-10-K-2026` | 117 | 113 | -4 |
| Q035 | `CROX-10-K-2025` | 169 | 166 | -3 |
| Q059 | `W-10-K-2025` | 106 | 105 | -1 |

## Fixture chunks with no identical counterpart

Their text changed between the release corpus and the corpus on
disk. No move above depends on them.

- `NKE-10-K-2026` chunk 84

## What has not been done yet

1. `python src/verify_labels.py --questions eval/questions_vnext.yaml --max-anchor-matches 8 --max-exceptions 4`
2. Delete and regenerate the derived split files: they carry copies of
   these indices. Then `python src/derive_split.py --verify`.
3. `python tests/fixture.py --build`, so the fixture stops being the
   only record of the old corpus and starts describing this one.
4. Re-measure retrieval. **The published 0.735 was measured against the
   labels as they were, over a corpus of 4,169 chunks that this pipeline
   no longer produces.** Whatever comes out is a new figure and is
   published as a new figure, with this log as the reason.
