"""
Company detection tests. No database, no model.

The company constraint is worth +0.118 Recall@16 over hybrid alone, so a name
the detector misses is a question that loses that entirely -- and a name it
invents sends the search to the wrong filing.

Gap failed in both directions at once, which is why it has its own pattern:

    "What were Gap's net sales in fiscal 2025?"   detected nothing
    "Describe the gap in supply chain coverage"   detected GAP

The bare word was deliberately left out of the alias list to avoid the second,
and the alias "the gap" produced it anyway.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import retrieve as R
import config as C


def test_possessive_company_name_is_detected():
    """Regression: no alias was the bare word, so "Gap's" matched nothing."""
    assert R.detect_companies("What were Gap's net sales in fiscal 2025?") == ["GAP"]


def test_bare_company_name_is_detected():
    assert R.detect_companies("Which brands does Gap operate?") == ["GAP"]


def test_corporate_suffix_still_matches():
    assert R.detect_companies("How did Gap Inc brands perform?") == ["GAP"]


def test_common_noun_is_not_a_company():
    """Regression: the alias "the gap" matched the ordinary English noun."""
    assert R.detect_companies("Describe the gap in supply chain coverage") == []
    assert R.detect_companies("What is the gap between wholesale and DTC?") == []


def test_brand_names_reach_their_parent():
    assert R.detect_companies("How did Old Navy perform?") == ["GAP"]
    assert R.detect_companies("What does HOKA contribute?") == ["DECK"]


def test_comparative_detects_both_companies_in_order():
    """A comparative that finds one company is searched as if it named one, and
    the quota split that guarantees evidence from both never runs."""
    assert R.detect_companies(
        "Do both Gap and Abercrombie & Fitch identify tariffs as a risk?"
    ) == ["GAP", "ANF"]
    assert R.detect_companies("Compare Nike and Lululemon revenue") == ["NKE", "LULU"]


def test_longest_alias_wins():
    """Regression: "columbia" must not shadow "columbia sportswear"."""
    assert R.detect_companies("Does Columbia Sportswear hedge currency?") == ["COLM"]


def test_company_not_in_the_corpus_has_no_alias():
    """
    SKX is configured but did not resolve in the SEC ticker index, so there are
    19 filings for 20 tickers. An alias for a filing that is not there would
    filter every Skechers question down to an empty corpus.
    """
    assert "SKX" not in R.COMPANY_ALIASES
    assert R.detect_companies("What were Skechers' net sales?") == []


def test_every_alias_belongs_to_a_configured_ticker():
    unknown = set(R.COMPANY_ALIASES) - set(C.COMPANIES)
    assert not unknown, f"aliases for tickers not in config.COMPANIES: {unknown}"


def test_patterns_do_not_duplicate_literal_aliases():
    """A ticker matched by a literal must not be added twice by its pattern."""
    for question in ("How did Old Navy perform?", "Gap Inc reported net sales"):
        found = R.detect_companies(question)
        assert len(found) == len(set(found)), question


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}  {e}")
    print(f"\n{len(fns)} tests")
