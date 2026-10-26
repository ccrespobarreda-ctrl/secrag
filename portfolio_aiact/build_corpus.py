#!/usr/bin/env python3
"""
Build a demo corpus from the EU AI Act, with the same pipeline as the 10-K corpus.

    python portfolio_aiact/build_corpus.py
    python portfolio_aiact/build_corpus.py --html path/to/saved_eurlex_page.html

Same chunker (src/chunk.py: chunk_section, verify_chunk_budget), same encoder
and settings (config.EMBEDDING_MODEL, normalized vectors), same output format as
demo/demo_corpus.json, so demo/load_demo.py loads it unchanged. The only new
code is the parser, because a regulation is organised in articles, not Items.

Source: Regulation (EU) 2024/1689, EUR-Lex. EU legal texts may be reused with
acknowledgement of the source (Commission Decision 2011/833/EU).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402
from chunk import chunk_section, verify_chunk_budget  # noqa: E402

log = logging.getLogger("aiact")

HERE = Path(__file__).resolve().parent
SOURCE_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689"
RAW = HERE / "aiact.html"
OUT = HERE / "aiact_corpus.json"
DOC_ID = "EU-AI-ACT-2024"

DOCUMENT = {
    "doc_id": DOC_ID,
    "ticker": "EU-AI-ACT",
    "company": "EU AI Act",
    "cik": 0,
    "form_type": "Regulation (EU) 2024/1689",
    "fiscal_year": 2024,
    "filed_date": "2024-07-12",          # publication in the Official Journal
    "source_url": SOURCE_URL,
}

_BLOCK = ("p", "td", "li", "h1", "h2", "h3", "h4")
_ART_ID = re.compile(r"^art_(\d+)$")
_ANX_ID = re.compile(r"^anx_([IVXLC]+)$")


def fetch(path: Path) -> str:
    if path.exists() and path.stat().st_size < 10_000:
        path.unlink()      # EUR-Lex answers scripts with an empty page
    if not path.exists():
        log.info("Downloading %s", SOURCE_URL)
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
        if len(data) < 10_000:
            raise SystemExit(
                "EUR-Lex returned an empty page to the script. Open the URL in a "
                f"browser, save it as 'Web page, HTML only' to {path}, run again.")
        path.write_bytes(data)
    return path.read_text(encoding="utf-8", errors="replace")


_LABEL = re.compile(r"^(\(?[a-z0-9]{1,5}\)|\d+\.|—|-)$")


def block_text(el) -> str:
    """
    One paragraph per block, in document order, so chunk_section can split on
    blank lines. EUR-Lex lays out numbered points as two-cell tables, "(a)" in
    one cell and the text in the next; a cell holding only a label is joined to
    the text that follows it.
    """
    paras, pending = [], ""
    for b in el.find_all(_BLOCK):
        if b.find(_BLOCK):
            continue
        t = " ".join(b.get_text(" ").split())
        if not t:
            continue
        if _LABEL.match(t):
            pending = (pending + " " + t).strip()
            continue
        paras.append((pending + " " + t).strip())
        pending = ""
    if pending:
        paras.append(pending)
    return "\n\n".join(paras)


def parse(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(html, "lxml")
    sections = []

    for div in soup.find_all(id=_ART_ID):
        num = _ART_ID.match(div["id"]).group(1)
        sub = div.find(class_=re.compile("oj-sti-art"))
        title = " ".join(sub.get_text(" ").split()).rstrip("`") if sub else ""
        body = block_text(div)
        # Drop the "Article N" heading and the subtitle from the body; they
        # travel as metadata instead.
        body = re.sub(rf"^Article {num}\s*\n\n", "", body)
        if title and body.startswith(title):
            body = body[len(title):].lstrip()
        sections.append({"item_section": f"Article {num}",
                         "section_title": title, "content": body})

    for div in soup.find_all(id=_ANX_ID):
        num = _ANX_ID.match(div["id"]).group(1)
        body = block_text(div)
        lines = body.split("\n\n")
        title = lines[1] if len(lines) > 1 else ""
        sections.append({"item_section": f"Annex {num}",
                         "section_title": title,
                         "content": "\n\n".join(lines[2:]) or body})

    if not sections:
        raise SystemExit(
            "No articles found by id. The EUR-Lex page layout may have changed; "
            "save the page as HTML and pass it with --html, or tell Claude.")
    return sections


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "httpcore", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    html = fetch(args.html)
    sections = parse(html)
    n_art = sum(s["item_section"].startswith("Article") for s in sections)
    log.info("Parsed %d articles and %d annexes", n_art, len(sections) - n_art)
    if n_art != 113:
        log.warning("Expected 113 articles, found %d. Check the parse before "
                    "recording anything.", n_art)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(C.EMBEDDING_MODEL, device="cpu")
    verify_chunk_budget(model)
    tok = model.tokenizer
    count = lambda t: len(tok.encode(t, add_special_tokens=False))  # noqa: E731

    # Each chunk opens with its article number and title. A 10-K section is
    # long and its heading adds little, but an article's title is often the
    # only place its topic is named: Article 99 never says "penalties" in the
    # paragraph that sets the fines, and Article 113 never says "general-purpose
    # AI". Without the header, version 1 missed both. The budget shrinks by the
    # header so no chunk exceeds CHUNK_TOKENS.
    chunks, index = [], 0
    for s in sections:
        header = f"{s['item_section']}: {s['section_title']}".strip(": ")
        budget = C.CHUNK_TOKENS - count(header) - 2
        for piece in chunk_section(s["content"], count, budget,
                                   C.CHUNK_OVERLAP_TOKENS):
            text = f"{header}\n\n{piece}"
            chunks.append({"doc_id": DOC_ID, "item_section": s["item_section"],
                           "section_title": s["section_title"],
                           "chunk_index": index, "token_count": count(text),
                           "content": text})
            index += 1
    over = [c for c in chunks if c["token_count"] > C.CHUNK_TOKENS]
    if over:
        raise SystemExit(f"{len(over)} chunks exceed CHUNK_TOKENS")

    vectors = model.encode([c["content"] for c in chunks], batch_size=C.EMBEDDING_BATCH_SIZE,
                           show_progress_bar=True, convert_to_numpy=True,
                           normalize_embeddings=True)
    for c, v in zip(chunks, vectors):
        c["embedding"] = [round(float(x), 6) for x in v]

    doc = dict(DOCUMENT, raw_chars=sum(len(s["content"]) for s in sections))
    args.out.write_text(json.dumps({"documents": [doc], "chunks": chunks}),
                        encoding="utf-8")
    log.info("%d chunks -> %s", len(chunks), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
