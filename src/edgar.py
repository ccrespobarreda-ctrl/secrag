#!/usr/bin/env python3
"""
Download 10-K filings from SEC EDGAR.

    python src/edgar.py                  # the latest 10-K of each ticker
    python src/edgar.py --pinned         # exactly the filings that were measured

Three things the SEC enforces, and each one returns a 403 rather than a helpful
error if you get it wrong:

  1. A User-Agent header declaring who you are and how to reach you.
  2. A request rate under 10/second.
  3. Requests to data.sec.gov for JSON, www.sec.gov for documents.

The CIK map is cached to disk after the first run. It is a 10 MB file that
changes rarely, and re-downloading it on every run is exactly the kind of
carelessness the fair-access rules exist to prevent.

WHY --pinned EXISTS

Without it this asks EDGAR for the *latest* 10-K per ticker, which is a question
whose answer changes. The release was measured over nineteen specific filings
producing 4,169 chunks; the same command later produced 4,124, every chunk index
after each difference shifted, and 23 gold labels stopped holding. That is
finding 15, and its cause is that "the latest" was never written down.

`eval/corpus_expected.yaml` writes it down. Accession numbers are immutable, so
--pinned rebuilds the exact corpus the published figures were measured over --
and it needs no submissions request at all, because the accession and the
primary document are the whole address. That also recovers a filing EDGAR will
no longer volunteer: SKX has no 10-K on record now, and unpinned runs report it
as missing.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import logging
import zlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

log = logging.getLogger("edgar")

_MIN_INTERVAL = 1.0 / C.SEC_MAX_REQUESTS_PER_SECOND
_last_request = 0.0


def _decompress(body: bytes, encoding: str) -> bytes:
    """
    urllib does not decompress responses, unlike requests.

    Asking for gzip and then reading the bytes as text fails with
    "UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1" --
    0x1f 0x8b being the gzip magic number. The header is worth keeping: the
    ticker index is 10 MB uncompressed and the filings are several MB each.

    Content-Encoding is checked rather than assumed, because a proxy may have
    already decompressed the body.
    """
    encoding = encoding.lower()
    if "gzip" in encoding:
        return gzip.decompress(body)
    if "deflate" in encoding:
        # Some servers send raw deflate without the zlib header.
        try:
            return zlib.decompress(body)
        except zlib.error:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    return body


def _throttled_get(url: str, attempts: int = 3) -> bytes:
    """One GET, rate-limited across the whole process, with backoff on 429/5xx."""
    global _last_request

    for attempt in range(1, attempts + 1):
        wait = _MIN_INTERVAL - (time.time() - _last_request)
        if wait > 0:
            time.sleep(wait)

        req = urllib.request.Request(url, headers={
            "User-Agent": C.SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                _last_request = time.time()
                return _decompress(r.read(), r.headers.get("Content-Encoding", ""))
        except urllib.error.HTTPError as exc:
            _last_request = time.time()
            if exc.code == 403:
                raise SystemExit(
                    "EDGAR returned 403. The User-Agent header must declare a real "
                    "name and email. Set SEC_USER_AGENT and try again."
                ) from exc
            if exc.code in (429, 500, 502, 503) and attempt < attempts:
                backoff = 2.0 * attempt
                log.warning("HTTP %d on attempt %d; retrying in %.0fs",
                            exc.code, attempt, backoff)
                time.sleep(backoff)
                continue
            raise

    raise RuntimeError(f"gave up on {url}")


# ─────────────────────────────────────────────────────────────────────
# CIK resolution
# ─────────────────────────────────────────────────────────────────────
def load_cik_map(cache_path: Path) -> dict[str, tuple[int, str]]:
    """ticker -> (cik, company name). Cached after the first download."""
    if cache_path.exists():
        with cache_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        log.info("CIK map from cache (%d tickers)", len(rows))
        return {r["ticker"]: (int(r["cik"]), r["company"]) for r in rows}

    log.info("Downloading the SEC ticker index (once)")
    raw = json.loads(_throttled_get(C.SEC_TICKER_INDEX))

    # The index is a dict keyed by row number, not a list.
    mapping = {
        e["ticker"].upper(): (int(e["cik_str"]), e["title"])
        for e in raw.values()
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "cik", "company"])
        for t, (cik, name) in sorted(mapping.items()):
            w.writerow([t, cik, name])

    log.info("Cached %d tickers to %s", len(mapping), cache_path)
    return mapping


# ─────────────────────────────────────────────────────────────────────
# Filing discovery
# ─────────────────────────────────────────────────────────────────────
def latest_filing(cik: int, form_type: str = C.FORM_TYPE) -> dict | None:
    """
    Most recent filing of a given form type.

    The submissions endpoint returns parallel arrays rather than a list of
    objects: form[i], accessionNumber[i], primaryDocument[i] all describe the
    same filing. Zipping them is the whole trick.
    """
    data = json.loads(_throttled_get(C.SEC_SUBMISSIONS.format(cik=cik)))
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    if not forms:
        return None

    for i, form in enumerate(forms):
        if form != form_type:
            continue
        return {
            "cik": cik,
            "company": data.get("name", ""),
            "form_type": form,
            # Accession numbers appear dashed in the API and undashed in archive
            # paths. Both are needed.
            "accession": recent["accessionNumber"][i].replace("-", ""),
            "accession_dashed": recent["accessionNumber"][i],
            "filed_date": recent["filingDate"][i],
            "report_date": recent.get("reportDate", [None] * len(forms))[i],
            "document": recent["primaryDocument"][i],
            "fiscal_year": int(recent["reportDate"][i][:4])
                           if recent.get("reportDate", [None])[i] else None,
        }
    return None


def pinned_filings(path: Path) -> list[dict]:
    """The declared filings, read rather than discovered.

    No request to the submissions endpoint: an accession number and a primary
    document name are the complete address of a filing, so nothing here depends
    on what EDGAR currently considers most recent. `company` is carried through
    from the pin because the warehouse column is NOT NULL and there is no
    lookup to supply it.
    """
    import yaml

    if not path.is_file():
        raise SystemExit(
            f"{path} not found. Write it from a corpus you trust:\n"
            f"  python src/pin_corpus.py --write")
    pin = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    filings = pin.get("filings") or []
    if not filings:
        raise SystemExit(f"{path} declares no filings.")

    out = []
    for f in filings:
        missing = [k for k in ("ticker", "cik", "accession", "document")
                   if not f.get(k)]
        if missing:
            raise SystemExit(f"{path}: {f.get('ticker', '?')} is missing "
                             f"{', '.join(missing)}")
        out.append({
            "cik": int(f["cik"]),
            "company": f.get("company", ""),
            "form_type": f.get("form_type", C.FORM_TYPE),
            "accession": str(f["accession"]),
            "accession_dashed": f.get("accession_dashed", ""),
            "filed_date": f.get("filed_date"),
            "report_date": f.get("report_date"),
            "document": f["document"],
            "fiscal_year": f.get("fiscal_year"),
            "ticker": str(f["ticker"]).upper(),
            "declared_raw_chars": f.get("raw_chars"),
        })
    return out


def download_filing(filing: dict, out_dir: Path) -> Path:
    url = C.SEC_ARCHIVE.format(cik=filing["cik"], accession=filing["accession"],
                               document=filing["document"])
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{filing['ticker']}-{filing['form_type']}-{filing['fiscal_year']}.html"

    # Recorded before the cache check, not after. Setting it only on the download
    # path meant a re-run with everything cached wrote a manifest with no
    # source_url at all -- and the warehouse column is NOT NULL, so the failure
    # surfaced two steps later with no obvious cause.
    filing["source_url"] = url

    if dest.exists():
        log.info("  %-6s cached (%.1f MB)", filing["ticker"], dest.stat().st_size / 1e6)
        return dest

    body = _throttled_get(url)
    dest.write_bytes(body)
    log.info("  %-6s %.1f MB  FY%s  filed %s",
             filing["ticker"], len(body) / 1e6, filing["fiscal_year"],
             filing["filed_date"])
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Download 10-K filings from EDGAR")
    ap.add_argument("--out", default=C.RAW_DIR, type=Path)
    ap.add_argument("--tickers", nargs="*", default=C.COMPANIES)
    ap.add_argument("--pinned", action="store_true",
                    help="download the filings declared in "
                         "eval/corpus_expected.yaml instead of the latest, so "
                         "the corpus is the one the figures were measured over")
    ap.add_argument("--pin", type=Path,
                    default=Path(__file__).resolve().parent.parent
                    / "eval" / "corpus_expected.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    if "@" not in C.SEC_USER_AGENT:
        log.error("SEC_USER_AGENT must contain a contact email. EDGAR returns 403 "
                  "without one.")
        return 2

    if args.pinned:
        # No ticker index and no submissions request: the pin is the address.
        planned = pinned_filings(args.pin)
        log.info("pinned to %s: %d filings", args.pin.name, len(planned))
    else:
        cik_map = load_cik_map(Path(C.CIK_CACHE))
        planned = []
        for ticker in args.tickers:
            entry = cik_map.get(ticker.upper())
            if not entry:
                log.warning("%-6s not found in the ticker index", ticker)
                continue
            cik, _name = entry
            filing = latest_filing(cik)
            if not filing:
                log.warning("%-6s has no %s on record", ticker, C.FORM_TYPE)
                continue
            filing["ticker"] = ticker.upper()
            planned.append(filing)
        log.warning("Downloading the latest filing of each ticker. The corpus "
                    "this produces\n  is whatever EDGAR holds today, not the "
                    "one the published figures were\n  measured over. Use "
                    "--pinned for that.")

    # What was asked for differs by mode, and the count at the end has to say
    # so: --pinned requests the declared filings, not config.COMPANIES. An
    # earlier version of this reported "19/4 filings" and named SKX as missing
    # when SKX is not in the pin at all.
    requested = ({f["ticker"] for f in planned} if args.pinned
                 else {t.upper() for t in args.tickers})
    manifest = []
    missing = sorted(requested - {f["ticker"] for f in planned})

    for filing in planned:
        ticker = filing["ticker"]
        path = download_filing(filing, args.out)

        # doc_id is recorded, not reconstructed downstream. src/load.py used to
        # derive it from local_path, and on Windows str(path) contains
        # backslashes that Path().stem does not treat as separators anywhere
        # else -- so the loader produced a doc_id no chunk referenced and the
        # foreign key failed with nothing pointing at the manifest.
        #
        # local_path is written with forward slashes for the same reason: it is
        # data that travels between machines, not a local path object.
        filing["doc_id"] = path.stem
        filing["local_path"] = path.as_posix()
        filing["raw_chars"] = path.stat().st_size

        # A pinned filing whose bytes differ from the declaration is caught
        # here, before parsing, chunking and embedding spend twenty minutes
        # producing a corpus that is not the declared one.
        declared = filing.pop("declared_raw_chars", None)
        if declared is not None and int(declared) != filing["raw_chars"]:
            log.error("%-6s is %d bytes, declared %d. The pin and the archive "
                      "disagree;", ticker, filing["raw_chars"], int(declared))
            log.error("       delete %s and re-run, or investigate before "
                      "measuring.", path.name)
            return 1

        manifest.append(filing)

    manifest_path = Path(args.out).parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    log.info("Downloaded %d/%d filings; manifest -> %s",
             len(manifest), len(requested), manifest_path)
    if missing:
        log.warning("Missing: %s", ", ".join(missing))
        log.warning("Check the ticker on sec.gov/cgi-bin/browse-edgar — companies "
                    "that delisted or changed symbol will not resolve.")
    if args.pinned and not missing:
        log.info("Every declared filing is present. Verify the corpus once it "
                 "is loaded:\n  python src/pin_corpus.py --verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
