"""
Parser tests against a fixture reproducing four real EDGAR defects.

Written because each of these cost a debugging session, and because the fixture
caught a genuine design bug: a fixed 400-character threshold, intended to discard
table-of-contents entries, silently dropped a real Item 1 of 392 characters.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import parse as P

FIXTURE = pathlib.Path(__file__).parent / "fixture_10k.html"
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

CROSSREF = pathlib.Path(__file__).parent / "fixture_10k_crossref.html"


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
