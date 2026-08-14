"""
Parser tests against a fixture reproducing four real EDGAR defects.

Written because each of these cost a debugging session, and because the fixture
caught a genuine design bug: a fixed 400-character threshold, intended to discard
table-of-contents entries, silently dropped a real Item 1 of 392 characters.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import parse as P
import config as C

FIXTURE = pathlib.Path(__file__).parent / "fixture_10k.html"
CROSSREF = pathlib.Path(__file__).parent / "fixture_10k_crossref.html"
HTML = FIXTURE.read_text(encoding="utf-8")
TEXT = P.html_to_text(HTML)


def test_block_boundaries_survive():
    """A div-laid-out table must not collapse into one unbroken string."""
    i = TEXT.find("Revenue")
    assert "51,217" in TEXT[i:i + 60]
    assert "Revenue51,217" not in TEXT


def test_entities_normalized():
    assert "\xa0" not in TEXT              # non-breaking space
    assert "\u200b" not in TEXT            # zero-width space
    assert "Management" in TEXT


def test_toc_entries_discarded():
    """The TOC lists every Item before the sections; only the bodies survive."""
    candidates = len(list(P._ITEM_PATTERN.finditer(TEXT)))
    sections = P.find_sections(TEXT)
    assert candidates > len(sections)
    assert len(sections) == 5


def test_short_but_real_sections_kept():
    """Regression: Item 3 is 241 chars and genuinely brief. It is not a TOC line."""
    found = {s["item_section"] for s in P.find_sections(TEXT)}
    assert "Item 3" in found
    assert "Item 1" in found


def test_heading_format_variants():
    """ITEM 1. BUSINESS / Item 1A. / Item&nbsp;3. / typographic apostrophe."""
    found = {s["item_section"] for s in P.find_sections(TEXT)}
    assert {"Item 1", "Item 1A", "Item 3", "Item 7", "Item 8"} <= found


def test_exhibits_not_indexed():
    parsed = P.parse_filing(FIXTURE)
    assert "Item 15" not in parsed["sections_indexed"]


# ─────────────────────────────────────────────────────────────────────
# Section boundaries
# ─────────────────────────────────────────────────────────────────────
# A heading the parser does not recognise cannot close the section before it.
# Item 9 was in neither ITEM_SECTIONS nor any other list, so the body of Item 8 --
# the financial statements -- ran through it and out the other side:
#
#     "...on page F-1.  ITEM 9. Changes in and Disagreements with Accountants
#      None.  ITEM 9A. Controls and Procedures"
#
# Fixing that exposed a second fault underneath: every section ended at the next
# heading's END offset rather than its START, so each body carried the following
# section's heading line. Item 9A ended with "ITEM 15. Exhibits and Financial
# Statement Schedules" attached.

def test_unindexed_item_closes_the_previous_section():
    """Item 9 is never indexed, and must still stop Item 8."""
    text = P.html_to_text(CROSSREF.read_text(encoding="utf-8"))
    item8 = next(s for s in P.find_sections(text) if s["item_section"] == "Item 8")
    assert "ITEM 9" not in item8["content"].upper()
    assert "Changes in and Disagreements" not in item8["content"]


def test_section_body_stops_before_the_next_heading():
    text = P.html_to_text(CROSSREF.read_text(encoding="utf-8"))
    for section in P.find_sections(text):
        tail = section["content"].upper()
        assert not tail.rstrip().endswith("SCHEDULES"), section["item_section"]
        assert "ITEM 15." not in tail, section["item_section"]


def test_boundary_only_items_are_never_emitted():
    """They exist to delimit. None of them may reach the corpus."""
    text = P.html_to_text(CROSSREF.read_text(encoding="utf-8"))
    emitted = {s["item_section"] for s in P.find_sections(text)}
    assert not (emitted & set(C.BOUNDARY_ONLY_ITEMS))


def test_item_9a_no_longer_absorbs_the_rest_of_the_filing():
    """Regression: Item 9A ran to end of document, 9,097 of 10,377 chars."""
    text = P.html_to_text(CROSSREF.read_text(encoding="utf-8"))
    item9a = next(s for s in P.find_sections(text)
                  if s["item_section"] == "Item 9A")
    assert item9a["char_count"] < 1_000, item9a["char_count"]
    assert "CONSOLIDATED BALANCE SHEETS" not in item9a["content"].upper()




# ─────────────────────────────────────────────────────────────────────
# The Item 8 cross-reference
# ─────────────────────────────────────────────────────────────────────
# Found by the boundary verifier, not by inspection: Item 8 showed a 580x spread
# across 18 real filings, with three of them under 400 characters against a
# median of 101,778. Reading one showed why:
#
#   "The consolidated financial statements and supplementary data are as set
#    forth in the index to consolidated financial statements on page F-1."
#
# The parser was right; the corpus would have been wrong.


def test_crossref_item8_is_recovered():
    parsed = P.parse_filing(CROSSREF)
    assert parsed["item8_recovered_from_fpages"] is True
    item8 = next(s for s in parsed["sections"] if s["item_section"] == "Item 8")
    assert "CONSOLIDATED BALANCE SHEETS" in item8["content"]
    assert "CONSOLIDATED STATEMENTS OF OPERATIONS" in item8["content"]


def test_crossref_pointer_is_replaced_not_appended():
    """The recovered section is the statements, not the pointer plus the statements."""
    parsed = P.parse_filing(CROSSREF)
    item8 = next(s for s in parsed["sections"] if s["item_section"] == "Item 8")
    assert "page F-1" not in item8["content"]


def test_normal_item8_untouched():
    """A filing whose Item 8 already holds the statements must not be rewritten."""
    parsed = P.parse_filing(FIXTURE)
    assert parsed["item8_recovered_from_fpages"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}  {e}")
    print(f"\n{len(fns)} tests")
