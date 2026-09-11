import re
import sys
import logging
import traceback
import hashlib
from datetime import datetime, timezone
from typing import Optional

# Fix Windows console encoding so print() never crashes on special chars
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
import os
import pymongo
from pymongo import InsertOne, UpdateOne

# ── Load environment ─────────────────────────────────────────────────────────
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not set in .env file")

DB_NAME           = "bio_sentry"
OUTPUT_COLLECTION = "processed_unified123"
BATCH_SIZE        = 500
ERROR_LOG_FILE    = "pipeline_errors.log"

# ── Raw collection → source label mapping ────────────────────────────────────
RAW_COLLECTIONS = [
    ("raw_Reddit_scraper", "reddit"),
    ("raw_webmd",          "webmd"),
    ("raw_openfda",        "openfda"),
    ("raw_arctic_shift",   "arctic_shift"),
    ("raw_drugs_forum",    "drugs_forum"),
    ("raw_reddit_api",     "reddit_api"),
]

# content_type map by source
CONTENT_TYPE_MAP = {
    "reddit":       "forum_post",
    "arctic_shift": "forum_post",
    "drugs_forum":  "forum_post",
    "reddit_api":   "forum_post",
    "webmd":        "drug_review",
    "openfda":      "adverse_report",
}

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ─────────────────────────────────────────────────────────────────────────────
#  SCHEMA NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def _safe_str(val, default="") -> str:
    if val is None:
        return default
    return str(val).strip()


def _safe_int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_list(val) -> list:
    if isinstance(val, list):
        return [str(v).strip().lower() for v in val if v]
    return []


def _safe_datetime(val) -> datetime:
    if isinstance(val, datetime):
        return val
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_content_hash(title: str, text: str) -> str:
    """Generate a unique signature for deduplication based on Title + Text (excluding comments)."""
    # Remove Reddit comments from text if present to ensure the hash matches across scrapers
    base_text = str(text).split("--- COMMENTS ---")[0]
    
    # Clean whitespace and lowercase
    clean_text = re.sub(r'\s+', ' ', base_text).strip().lower()
    clean_title = re.sub(r'\s+', ' ', str(title)).strip().lower() if title else ""
    
    content_to_hash = f"{clean_title}|{clean_text}"
    return hashlib.md5(content_to_hash.encode("utf-8")).hexdigest()


def normalize(doc: dict, source: str) -> Optional[dict]:  # FIX 7: dict | None → Optional[dict]
    """
    Map any raw source document to the unified schema.
    Returns None if the doc is fundamentally malformed (no usable fields).
    """
    try:
        post_id = _safe_str(doc.get("post_id"))
        if not post_id:
            return None

        # ── forum & post_id ───────────────────────────────────────────────────
        if source in ("arctic_shift", "reddit_api"):
            subreddit = _safe_str(doc.get("subreddit"))
            forum = f"r/{subreddit}" if subreddit else "N/A"
        else:
            forum = _safe_str(doc.get("forum"), "N/A")

        # Normalize Reddit IDs (remove "reddit_" prefix if present) so all scrapers match
        if source in ("reddit", "reddit_rss", "arctic_shift", "reddit_api"):
            if post_id.startswith("reddit_"):
                post_id = post_id[7:]

        # ── title ─────────────────────────────────────────────────────────────
        title = _safe_str(doc.get("title"))

        # ── text ──────────────────────────────────────────────────────────────
        if source == "openfda":
            text = _safe_str(doc.get("text"))
            if len(text) < 40:
                text = _build_openfda_text(doc)
        elif source == "arctic_shift":
            text = _safe_str(doc.get("text") or doc.get("selftext"))
        else:
            text = _safe_str(doc.get("text"))

        # Combine title into text for forum posts
        if source in ("reddit", "arctic_shift", "drugs_forum", "reddit_api"):
            if title and title not in text:
                text = f"{title}\n\n{text}".strip()

        # Truncate if too long — keep doc, trim content
        MAX_TEXT = 30_000
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT]

        content_hash = _generate_content_hash(title, text)

        return {
            "post_id":         post_id,
            "source":          source,
            "content_hash":    content_hash,
            "forum":           forum or "N/A",
            "title":           title,
            "text":            text,
            "url":             _safe_str(doc.get("url")),
            "drugs_mentioned": _safe_list(doc.get("drugs_mentioned")) or (
                [_safe_str(doc.get("drug_name")).lower()]
                if source == "webmd" and doc.get("drug_name")
                else []
            ),
            "content_type":    CONTENT_TYPE_MAP.get(source, "forum_post"),
            "search_query":    _safe_str(doc.get("search_query")),
            "num_comments":    _safe_int(doc.get("num_comments"), 0),
            "language":        "en",
            "date_scraped":    _safe_datetime(doc.get("date_scraped")),
            "text_length":     len(text),
            "processed":       False,
        }

    except Exception as exc:
        logging.error(
            "normalize() failed | source=%s | post_id=%s | error=%s\n%s",
            source, doc.get("post_id", "???"), exc, traceback.format_exc(),
        )
        return None


def _build_openfda_text(doc: dict) -> str:
    """Reconstruct narrative text for an OpenFDA adverse event report."""
    parts   = []
    patient = doc.get("patient", {}) or {}

    reactions = [
        r.get("reactionmeddrapt", "").strip()
        for r in patient.get("reaction", [])
        if r.get("reactionmeddrapt")
    ]
    raw_drugs = [
        d.get("medicinalproduct", "").strip()
        for d in patient.get("drug", [])
        if d.get("medicinalproduct")
    ]

    search_drug  = _safe_str(doc.get("search_query") or doc.get("drug"))
    serious_text = "serious" if int(doc.get("serious") or 0) == 1 else "non-serious"
    age          = patient.get("patientonsetage", "unknown")
    sex          = {"1": "male", "2": "female"}.get(str(patient.get("patientsex", "0")), "unknown")

    parts.append(f"Adverse event report filed with the FDA for {search_drug.title() if search_drug else 'unknown drug'}.")
    parts.append(f"Patient: {sex}, age {age}.")
    if raw_drugs:
        parts.append(f"Medications involved: {', '.join(raw_drugs)}.")
    if reactions:
        parts.append(f"Reported reactions: {', '.join(reactions)}.")
    parts.append(f"Case classification: {serious_text}.")

    narrative = doc.get("narrativeincludeclinical") or ""
    if narrative:
        parts.append(f"Clinical narrative: {str(narrative)[:2000]}")

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  FILTERING
# ─────────────────────────────────────────────────────────────────────────────

_REPEATED_CHAR_RE = re.compile(r"^(.)\1{15,}$")
_WHITESPACE_RE    = re.compile(r"^\s*$")


def _is_garbage_text(text: str) -> bool:
    if _WHITESPACE_RE.match(text):
        return True
    cleaned = re.sub(r"\s+", "", text)
    if cleaned and _REPEATED_CHAR_RE.match(cleaned):
        return True
    if len(cleaned) > 50 and len(set(cleaned)) < 5:
        return True
    return False


def should_keep(doc: dict, source: str, seen: set) -> tuple:
    """
    Returns (True, "") to insert, or (False, reason) to skip.

    FIX 5: Removed per-document find_one() DB call — was causing 14k individual
    queries. Deduplication against processed_unified is now handled entirely by
    the unique index (post_id + source). BulkWriteError code 11000 catches any
    DB-level duplicates at flush time, which is orders of magnitude faster.
    """
    text    = doc.get("text", "")
    post_id = doc.get("post_id", "")

    if not text or len(text) < 40:
        return False, "text_too_short"

    # webmd must have at least one drug mention (since it's a drug review site)
    if source == "webmd" and not doc.get("drugs_mentioned"):
        return False, "no_drugs_mentioned"

    if _is_garbage_text(text):
        return False, "garbage_text"

    # In-memory dedup (within this run)
    content_hash = doc.get("content_hash", "")
    if content_hash in seen:
        return False, "duplicate_in_batch"

    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
#  FLUSH BATCH  (FIX 1: moved outside the loop — was redefined every iteration)
# ─────────────────────────────────────────────────────────────────────────────

def flush_batch(
    insert_ops:    list,
    raw_ids_all:   list,
    raw_col,
    processed_col,
) -> tuple:                         # FIX 3: now actually returns (kept, dupes)
    """
    Bulk-insert docs into processed_unified, then mark all raw docs processed.

    Returns
    -------
    kept_delta  : int  — number of docs actually inserted into processed_unified
    dupes_delta : int  — number of docs rejected by the unique index (duplicates)

    FIX 4: raw_ids_ok removed — we mark ALL raw docs as processed=True
    regardless, because whether they were kept or filtered, they have been
    evaluated and we don't want to re-process them on the next run.
    """
    kept_delta  = 0
    dupes_delta = 0

    if insert_ops:
        try:
            result      = processed_col.bulk_write(insert_ops, ordered=False)
            kept_delta  = result.inserted_count
            dupes_delta = len(insert_ops) - result.inserted_count
        except pymongo.errors.BulkWriteError as bwe:
            kept_delta  = bwe.details.get("nInserted", 0)
            dupes_delta = 0
            for err in bwe.details.get("writeErrors", []):
                if err.get("code") == 11000:        # duplicate key
                    dupes_delta += 1
                else:
                    logging.error("BulkWrite non-dedup error: %s", err)

    if raw_ids_all:
        try:
            raw_col.bulk_write(
                [UpdateOne({"_id": rid}, {"$set": {"processed": True}}) for rid in raw_ids_all],
                ordered=False,
            )
        except Exception as exc:
            logging.error("Failed to mark raw docs processed: %s", exc)

    return kept_delta, dupes_delta


# ─────────────────────────────────────────────────────────────────────────────
#  PIPELINE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline():
    print("\nConnecting to MongoDB Atlas…")
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        print("  [OK] Connected\n")
    except Exception as exc:
        print(f"  [ERR] Cannot reach MongoDB: {exc}")
        raise

    mongo_db      = client[DB_NAME]
    processed_col = mongo_db[OUTPUT_COLLECTION]

    # Ensure old index is removed to avoid conflicts with normalized post_ids
    try:
        processed_col.drop_index("post_id_1_source_1")
    except Exception:
        pass

    # Unique index — this is now the ONLY dedup guard against the DB
    processed_col.create_index(
        [("content_hash", 1)],
        unique=True,
        background=True,
    )

    stats                    = {}
    total_duplicates_removed = 0
    seen                     = set()   # in-memory dedup across all collections

    print("=" * 54)
    print("  STARTING PIPELINE")
    print("=" * 54)

    for coll_name, source in RAW_COLLECTIONS:
        raw_col     = mongo_db[coll_name]
        read_count  = 0
        kept_count  = 0     # FIX 2: will be updated from flush results, not pre-flush count
        drop_count  = 0
        dupes_local = 0
        drop_reasons: dict = {}

        print(f"\n[{coll_name}]  source='{source}'")

        cursor = raw_col.find({"processed": {"$ne": True}}).batch_size(BATCH_SIZE)

        insert_ops  = []
        raw_ids_all = []    # FIX 4: raw_ids_ok removed — raw_ids_all is enough

        try:
            for raw_doc in cursor:
                read_count += 1
                raw_ids_all.append(raw_doc["_id"])

                norm = normalize(raw_doc, source)
                if norm is None:
                    drop_count += 1
                    drop_reasons["normalize_failed"] = drop_reasons.get("normalize_failed", 0) + 1
                    continue

                keep, reason = should_keep(norm, source, seen)
                if not keep:
                    drop_count += 1
                    drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
                    if reason == "duplicate_in_batch":
                        dupes_local += 1
                        # FIX 6: in-memory dupes counted in total_duplicates_removed
                        total_duplicates_removed += 1
                    continue

                seen.add(norm["content_hash"])
                insert_ops.append(InsertOne(norm))

                if len(insert_ops) >= BATCH_SIZE:
                    kd, dup = flush_batch(insert_ops, raw_ids_all, raw_col, processed_col)
                    kept_count              += kd    # FIX 2: update from actual DB result
                    dupes_local             += dup
                    total_duplicates_removed += dup  # FIX 6: DB dupes also counted
                    insert_ops  = []
                    raw_ids_all = []
                    print(f"  … batch flushed ({BATCH_SIZE} docs processed so far)")

            # Flush remainder
            if insert_ops or raw_ids_all:
                kd, dup = flush_batch(insert_ops, raw_ids_all, raw_col, processed_col)
                kept_count              += kd        # FIX 2
                dupes_local             += dup
                total_duplicates_removed += dup      # FIX 6

        except Exception as exc:
            logging.error(
                "Pipeline error in collection %s: %s\n%s",
                coll_name, exc, traceback.format_exc(),
            )
            print(f"  [ERR] Error processing {coll_name}: {exc}")
        finally:
            cursor.close()

        # drop_count already accumulated above; kept_count now reflects real inserts
        total_dropped = read_count - kept_count
        stats[coll_name] = {
            "source":       source,
            "read":         read_count,
            "kept":         kept_count,
            "dropped":      total_dropped,
            "drop_reasons": drop_reasons,
        }
        print(
            f"  read={read_count}  kept={kept_count}  "
            f"dropped={total_dropped}  dupes={dupes_local}"
        )
        if drop_reasons:
            for reason, cnt in sorted(drop_reasons.items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {cnt}")

    # ── Indexes ───────────────────────────────────────────────────────────────
    print("\nCreating indexes on processed_unified…")
    _create_indexes(processed_col)

    final_count = processed_col.count_documents({})
    _print_report(stats, total_duplicates_removed, final_count)

    client.close()


def _create_indexes(col):
    indexes = [
        ([("source", 1)],          {}),
        ([("drugs_mentioned", 1)], {}),
        ([("processed", 1)],       {}),
        ([("text_length", 1)],     {}),
        ([("text", "text")],       {"name": "text_search_idx"}),
    ]
    for key_spec, kwargs in indexes:
        try:
            col.create_index(key_spec, background=True, **kwargs)
            print(f"  [OK] Index on '{key_spec[0][0]}'")
        except Exception as exc:
            logging.error("Index creation failed for %s: %s", key_spec, exc)
            print(f"  [ERR] Index failed: {exc}")


def _print_report(stats: dict, dupes_removed: int, final_count: int):
    COL_W = 22
    total_read = total_kept = total_dropped = 0
    for v in stats.values():
        total_read    += v["read"]
        total_kept    += v["kept"]
        total_dropped += v["dropped"]

    print(f"\n{'=' * 54}")
    print("  PIPELINE REPORT")
    print(f"{'=' * 54}")
    for coll_name, v in stats.items():
        label = f"{coll_name}:"
        print(
            f"  {label:<{COL_W}}  "
            f"{v['read']:>5} read  |  "
            f"{v['kept']:>5} kept  |  "
            f"{v['dropped']:>5} dropped"
        )
    print(f"  {'─' * 50}")
    print(
        f"  {'TOTAL:':<{COL_W}}  "
        f"{total_read:>5} read  |  "
        f"{total_kept:>5} kept  |  "
        f"{total_dropped:>5} dropped"
    )
    print(f"  Duplicates removed : {dupes_removed}")
    print(f"  processed_unified  : {final_count} documents ready")
    print(f"{'=' * 54}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start = datetime.now()
    print(f"\nPipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
    except Exception as exc:
        logging.critical("Pipeline crashed: %s\n%s", exc, traceback.format_exc())
        print(f"\n  FATAL: {exc}")
    finally:
        elapsed = (datetime.now() - start).total_seconds()
        print(f"  Elapsed: {elapsed:.1f}s")