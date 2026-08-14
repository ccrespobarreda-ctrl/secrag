"""
Citation verification tests. No model, no API calls.

Asking a model for citations and trusting them is theatre. These check what the
code can check: that a cited excerpt was actually supplied, that figures carry
sources, and that a refusal is a refusal rather than an answer with a disclaimer.

Two bugs found here before a single token was spent:

  1. The figure pattern matched bare years, so a refusal saying "the excerpts
     cover fiscal 2026 only" -- exactly the right thing to say -- was flagged as
     answering.

  2. Percentages escaped the check entirely. The pattern ended in \\b after an
     alternation containing %, and % is not a word character, so no boundary
     exists between it and the following space. Every percentage passed
     unchecked, including uncited ones.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import generate as G
import config as C

N = 8


def clean(text):
    _, problems = G.verify_citations(text, N)
    return not problems


def test_cited_answer_passes():
    assert clean("Net revenues were $4,966,370 thousand in fiscal 2026 [2].")


def test_citation_out_of_range_is_caught():
    _, problems = G.verify_citations("Revenue was $4,966,370 [12].", N)
    assert any("only 8" in p for p in problems)


def test_uncited_figure_is_caught():
    assert not clean("Net revenues were $4,966,370 thousand.")


def test_uncited_percentage_is_caught():
    """Regression: a trailing \\b after % meant percentages never matched."""
    assert not clean("Gross margin was 45.3%.")


def test_cited_percentage_passes():
    assert clean("Gross margin was 45.3% [4].")


def test_answer_with_no_citations_is_caught():
    assert not clean("The company operates globally.")


def test_clean_refusal_passes():
    assert clean(f"{C.REFUSAL_MARKER}\nThe excerpts cover fiscal 2026 only.")


def test_refusal_naming_a_year_passes():
    """Regression: a refusal must be free to say which years it does cover."""
    assert clean(f"{C.REFUSAL_MARKER}\nOnly fiscal 2025 and 2026 appear here.")


def test_refusal_that_also_answers_is_caught():
    _, problems = G.verify_citations(
        f"Revenue was $4,966,370 [1]. {C.REFUSAL_MARKER}", N)
    assert any("stand alone" in p for p in problems)


def test_refusal_stating_a_percentage_is_caught():
    assert not clean(f"{C.REFUSAL_MARKER}\nMargin was 45.3% in the excerpts.")


def test_prompt_names_the_refusal_marker():
    """The marker must be exact, or refusal cannot be counted automatically."""
    assert C.REFUSAL_MARKER in G.SYSTEM_PROMPT


def test_excerpts_carry_provenance():
    """Without company and year attached, the model cannot tell filings apart."""
    class Hit:
        content = "Net revenues $4,966,370"
        def label(self): return "(Under Armour, FY2026, Item 8)"
    msg = G.build_user_message("q", [Hit()])
    assert "[1]" in msg and "Under Armour" in msg and "FY2026" in msg




# ─────────────────────────────────────────────────────────────────────
# Refusal versus a partial answer with its scope declared
# ─────────────────────────────────────────────────────────────────────
# Matching a phrase was not enough. Asked how each Gap brand performed, the model
# answered with everything the excerpts held and closed with "the excerpts do not
# provide brand-level net sales broken out individually". Counting that as a
# refusal made two checks contradict each other: one reported a refusal, the
# other reported a refusal that stated figures.

def test_prose_refusal_counts():
    assert G.is_refusal(
        "The excerpts do not provide an exact count of countries where YETI "
        "products are sold. An exact number cannot be determined [15].")


def test_partial_answer_with_declared_scope_is_not_a_refusal():
    assert not G.is_refusal(
        "Gap Inc.'s net sales for fiscal 2025 increased $280 million, or 2 "
        "percent [12]. The excerpts do not provide brand-level net sales "
        "broken out individually [3][12].")


def test_exact_marker_always_counts():
    assert G.is_refusal(f"{C.REFUSAL_MARKER}\nOnly 2023 to 2025 appear.")


def test_clean_answer_is_not_a_refusal():
    assert not G.is_refusal("Net revenues were $4,966,370 thousand [2].")


def test_markdown_bullets_keep_their_citation():
    """Regression: bullets were split away from the citation at their end."""
    assert clean(
        "Gap operates four brands [1].\n"
        "- **Banana Republic**: Founded in 1978 and acquired in 1983 [2].\n"
        "- **Athleta**: Founded in 1998 and acquired in 2008 [2][7].")


def test_long_sentence_with_several_figures_keeps_its_citation():
    """Regression: one citation at the end covers every figure in the sentence."""
    assert clean(
        "Tariffs in effect through January 31, 2026 reduced operating income by "
        "$90 million (170 basis points) in Fiscal 2025, with an expected "
        "incremental $40 million (70 basis points) in Fiscal 2026 [2][7].")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}  {e}")
    print(f"\n{len(fns)} tests")
