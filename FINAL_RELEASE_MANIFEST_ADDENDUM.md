# Addendum to FINAL_RELEASE_MANIFEST.md

**Status of the manifest:** `FINAL_FROZEN`, and correct as published. Its own
hash verifies.

Three things need saying about it that it cannot say itself. Its freeze rule
makes a change to configuration, benchmark labels, prompts, generation code or
result files a new evaluation version, and it is listed in `SHA256SUMS.txt` with
a hash that holds. Editing it would either break that hash or quietly rewrite a
published document. So the corrections live here, beside it, and this file is
not hashed because it is expected to grow.

---

## 1. The refusal and hallucination rates depend on which detector produced them

The manifest reports **Unanswerable refusal rate: 100.0%** and **Automatic
hallucination rate: 0.0%**.

Both figures rest on a single record out of 210. Two result files holding
identical generated text disagreed on that one record, and the flip is the whole
difference between 65/66 and 66/66 refusal, and between 1/66 and 0/66
hallucination. The cause was a real improvement — refusal detection moved from a
substring test to a rule about whether the limitation *is* the answer — but the
zero was published without naming which detector produced it. Zero with one
detector, one with the other, on the same text.

Read those two figures as "zero under the rule-based detector, one under the
substring detector". Finding 11 in the README is the full account.

## 2. The code artifacts are recorded, not reproducible

The manifest's **Final artifacts** table lists twelve files with their SHA-256
hashes. Nine verify today, byte for byte: `src/config.py`,
`eval/questions_canonical.yaml` and every results file. Those are the evidence,
and they are gated in continuous integration by `verify_release.py`.

The other five — `src/retrieve.py`, `src/generate.py` and the three
`src/evaluate_*.py` modules — cannot be verified against anything. They were
hashed at 17:42 on 17 August from a working tree, and edited before that state
was ever committed. Three searches establish it and are kept in the repository
so it can be re-tested:

| | Result |
|---|---|
| `verify_release.py` | matches neither the working tree nor the release tag |
| `find_release_commit.py` | in none of the 42 commits |
| `find_release_blobs.py` | in none of the 195 blobs in the object database, orphaned included |

**What this does and does not mean.** The published figures were produced by
that code, and every results file it wrote is byte-identical to publication. It
does not mean a reader can check out the release and reproduce those bytes, and
listing the five hashes as release artifacts implied they could. They are marked
`record` in `SHA256SUMS.txt`: kept visible, verified by nothing.

The reproducibility claim that does hold is finding 6, and it is the stronger
one: seven days later, from a question file rebuilt by a script, with the
evaluation harness modified, on a reloaded environment, all twelve retrieval
figures came out identical to this manifest. The figures survived the code
changing, which is a better property than the code being pinned.

## 3. This manifest describes the 50-question release, not the current benchmark

The manifest reports 50 benchmark questions, 34 answerable, 62 canonical gold
labels, groundedness 97.9% and a false-refusal rate of 2.9%. The README reports
100 questions, 127 audited labels, groundedness 97.4% and a false-refusal rate
of 0%.

Neither is wrong. They are different evaluation versions, and the freeze rule is
why: the benchmark was relabelled and the refusal detection corrected, which by
the manifest's own definition makes what came after a new version. The 2.9% here
and the 0% there are the same defect measured before and after the fix described
in finding 3.

When comparing the two documents, `Recall@16 = 0.735` is the figure that means
the same thing in both.

---

**The release tag.** `SECRAG-RRF40-2026-08-17` points at the commit that
finalised this release. It reproduces the results files and the configuration
exactly. It does not reproduce the five source files at their published hashes,
for the reason in section 2.
