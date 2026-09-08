# Twenty-five comparative pairs, to write twenty questions

Comparison questions are the weakest type in this benchmark — coverage 0.300 on
the original set — and the only type with room to move. They are also the type
that cannot currently decide anything: with n=5, the metric moves in steps of
0.2, and no retrieval change can be accepted or rejected against it. Twenty
questions bring that step down to 0.05.

These pairs are a starting list, not questions. Choosing which companies to
compare is not labelling; reading the filings and deciding which passage answers
is, and that part is not delegated.

---

## The rule these are labelled under

The order matters more than anything else on this page. It is the correction to
finding 1, and doing it in the wrong order would reproduce the bias in the act
of fixing it.

**1. Read both filings first.** Open the two documents, find what each says
about the topic, and decide whether a real comparison exists. If one company
discloses the thing and the other does not, the question is not comparative —
discard it, or keep it as an `unanswerable_absent`.

**2. Write the question and the answer from what you read.** Not from what you
hope to find.

**3. Record the passages that answer it.** Every passage, in both filings. If
the evidence for one company is spread over three chunks, label all three; that
is what coverage exists to measure.

**4. Keep the question even if the retriever misses it.** This is the whole
point. The old rule dropped questions whose evidence could not be located by
literal search, which selected for questions a keyword search already handles.
A question the system fails is the most valuable label in the set.

**5. Only then, if you want, look at where the retriever placed them.** After
the label is written, that observation cannot influence it.

**Anchors:** write a phrase that carries the answer and appears in few chunks of
that document. `src/show_chunk.py DOC INDEX --find "your anchor"` tells you how
many. Eight or fewer passes the gate; one is ideal.

---

## Where these go

A new split, `comparative_v2`, in `eval/vnext_splits.yaml`. Not into legacy.

Legacy is the frozen set every published figure is measured against; adding to
it would break comparability with the August release. A separate split labelled
under the corrected rule is also the measurement of the correction: run plain
keyword search over it and over the old comparatives, and the difference in
lexical lift is the bias, quantified a second way and independently.

Question ids continue from Q106.

---

## The pairs

Ordered so the ones most likely to yield a real comparison come first. Expect to
discard four or five on opening the documents — that is the process working, not
failing.

### Strong: both companies disclose the same thing in the same form

| # | Pair | Topic | Evidence likely to be |
|---|---|---|---|
| 1 | NIKE · Under Armour | Contract manufacturing: how many factories, in which countries, concentration | Prose plus counts, two or three passages each |
| 2 | Gap · Abercrombie | Store count by brand, and net openings or closings | Tables, one passage each |
| 3 | Chewy · Wayfair | Fulfilment network: own warehouses versus supplier-direct | Prose, distributed |
| 4 | Lululemon · Columbia | Direct-to-consumer channel: what it includes and its share | Prose plus a percentage |
| 5 | Etsy · REVOLVE | Inventory position: marketplace holding none versus owned stock | Prose, one strong passage each |
| 6 | Deckers · Crocs | Brand portfolio and which brand carries the growth | Prose plus segment figures |
| 7 | Peloton · Warby Parker | Subscription or recurring revenue, and how each defines it | Definitions, often two passages |
| 8 | Levi Strauss · Columbia | Geographic segments and their relative size | Segment tables |
| 9 | FIGS · Warby Parker | Physical retail alongside a digital-first model | Prose plus store counts |
| 10 | Urban Outfitters · Abercrombie | Brand families and how each reports them | Segment structure |

### Moderate: comparable, but the disclosures may differ in form

| # | Pair | Topic | Watch for |
|---|---|---|---|
| 11 | NIKE · Deckers | Share of revenue from outside the United States | One may give a percentage, the other a table |
| 12 | Gap · Levi Strauss | Franchise and licensing arrangements | Depth varies a lot |
| 13 | YETI · Crocs | Wholesale versus direct mix | May be a single sentence each |
| 14 | Chewy · Etsy | How each defines an active customer | Definitions are often near-identical, which is itself the answer |
| 15 | Honest · FIGS | Product categories and channel mix | Honest's is in Item 1, FIGS' may be split |
| 16 | Peloton · Lululemon | Membership or community as a retention strategy | Prose, may be diffuse |
| 17 | Wayfair · Urban Outfitters | Returns, and what each says it costs | Often buried in Item 7 |
| 18 | Under Armour · Columbia | Inventory management after an excess-stock period | Prose, distributed |
| 19 | REVOLVE · Warby Parker | Customer acquisition cost and marketing spend | One may not disclose it — check before writing |
| 20 | Abercrombie · Levi Strauss | Tariff exposure and stated mitigation | Rich in both, likely three passages each |

### Worth trying: higher chance of being discarded

| # | Pair | Topic | Why it may not work |
|---|---|---|---|
| 21 | Etsy · Wayfair | Take rate or seller economics | Wayfair's model may not have an equivalent |
| 22 | NIKE · Lululemon | Digital platform and app strategy | May be marketing language with no figures |
| 23 | Crocs · Deckers | Third-party manufacturer concentration | One may name suppliers, the other may not |
| 24 | Honest · Chewy | Retail partner concentration | Very different scales |
| 25 | Peloton · YETI | Product warranty and returns policy | May be absent from one filing |

---

## Template for each question

```yaml
- id: Q106
  question: How do NIKE and Under Armour structure their contract manufacturing?
  type: comparative
  answerable: true
  gold_chunk_ids: []            # filled by verify_labels on resolve
  gold_answer: >
    Written from the filings, naming both companies and the figures that
    distinguish them.
  notes: >
    comparative_v2. Labelled by reading both filings before any search.
    Say here what made it comparable, and anything a reader would need to
    judge the label.
  gold_chunks:
    - doc_id: NKE-10-K-2026
      chunk_index: 6
      contains: a phrase carrying the answer, in few chunks of this document
    - doc_id: UAA-10-K-2026
      chunk_index: 9
      contains: likewise
```

**After every few questions**, not at the end:

```powershell
python .\src\verify_labels.py --questions .\eval\questions_vnext.yaml --max-anchor-matches 8
```

Catching a bad anchor after three questions costs three minutes. Catching it
after twenty costs an evening.

---

## What this buys, and what it does not

With twenty comparatives the metric resolves a single question changing outcome
as 0.05 rather than 0.2, and a retrieval change can be judged against it for the
first time.

It does not fix comparison retrieval. Coverage of 0.300 stays 0.300 until
something is changed about how the system handles a question naming two
companies — and the diagnosis already exists: the per-company quota splits the
budget evenly regardless of which company's evidence is harder to reach. These
questions are what makes that fix measurable.
