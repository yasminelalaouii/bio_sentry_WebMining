import time
import requests
from database import MongoDBManager


# ── Drug list ────────────────────────────────────────
DRUGS = [
    # Antidepressants / Anxiolytics
    "sertraline", "fluoxetine", "escitalopram", "paroxetine", "citalopram",
    "venlafaxine", "duloxetine", "bupropion", "trazodone", "mirtazapine",
    # Benzodiazepines / Sleep
    "alprazolam", "lorazepam", "clonazepam", "diazepam", "zolpidem",
    # ADHD
    "methylphenidate", "amphetamine", "lisdexamfetamine", "atomoxetine",
    # Antipsychotics
    "quetiapine", "risperidone", "olanzapine", "aripiprazole", "lithium",
    # Pain / Anti-inflammatory
    "ibuprofen", "naproxen", "tramadol", "gabapentin", "pregabalin",
    "acetaminophen", "aspirin", "meloxicam",
    # Cardiovascular / Metabolic
    "atorvastatin", "metformin", "lisinopril", "amlodipine", "metoprolol",
    # Antibiotics / Other
    "amoxicillin", "azithromycin", "omeprazole", "levothyroxine", "prednisone",
]

REPORTS_PER_DRUG = 100
PAGES_PER_DRUG   = 2

FDA_BASE_URL = "https://api.fda.gov/drug/event.json"


# ── Helpers ─────────────────────────────────────────────────────────────────
def _extract_drugs_mentioned(drugs_in_report: list) -> list:
    """Normalize drug names to lowercase for consistency with Reddit schema."""
    seen  = set()
    clean = []
    for d in drugs_in_report:
        low = d.strip().lower()
        if low and low not in seen:
            seen.add(low)
            clean.append(low)
    return clean


def _build_doc(report: dict, drug: str) -> dict | None:
    """Convert a raw FDA FAERS report dict into the shared Reddit-like schema."""
    report_id = report.get("safetyreportid")
    if not report_id:
        return None

    post_id = f"openfda_{report_id}"

    # Reactions list
    reactions = [
        rx.get("reactionmeddrapt", "").strip()
        for rx in report.get("patient", {}).get("reaction", [])
        if rx.get("reactionmeddrapt")
    ]

    # Drugs in the report
    raw_drugs = [
        d.get("medicinalproduct", "").strip()
        for d in report.get("patient", {}).get("drug", [])
        if d.get("medicinalproduct")
    ]
    drugs_mentioned = _extract_drugs_mentioned(raw_drugs)

    serious      = report.get("serious", 0)
    serious_text = "serious" if int(serious or 0) == 1 else "non-serious"

    patient_age  = report.get("patient", {}).get("patientonsetage", "unknown")
    patient_sex_code = report.get("patient", {}).get("patientsex", "0")
    sex_map = {"1": "male", "2": "female"}
    patient_sex  = sex_map.get(str(patient_sex_code), "unknown")

    # ── Title (mirrors Reddit style) ──
    reaction_str = ", ".join(reactions[:3]) if reactions else "adverse reaction"
    title = f"[FDA FAERS] {drug.title()} adverse event: {reaction_str}"

    # ── Full narrative text (mirrors Reddit post body + comments) ──
    narrative = report.get("narrativeincludeclinical") or ""

    text_parts = [
        f"Adverse event report filed with the FDA for {drug.title()}.",
        f"Patient: {patient_sex}, age {patient_age}.",
        f"Medications involved: {', '.join(raw_drugs) if raw_drugs else drug}.",
        f"Reported reactions: {', '.join(reactions) if reactions else 'not specified'}.",
        f"Case classification: {serious_text}.",
    ]
    if narrative:
        text_parts.append(f"\nClinical narrative: {narrative[:2000]}")

    text = " ".join(text_parts)

    # ── URL (public FAERS viewer) ──
    url = f"https://www.fda.gov/safety/reporting-serious-problems-fda/what-voluntary-reporting-form-mdr?safetyreportid={report_id}"

    return {
        "post_id":         post_id,
        "source":          "openfda",
        "forum":           "FDA FAERS",
        "title":           title,
        "text":            text,
        "url":             url,
        "drugs_mentioned": drugs_mentioned,
        "content_type":    "adverse_event_report",
        "search_query":    drug,
        "num_comments":    0,
        "reactions":       reactions,
        "serious":         serious,
        "report_date":     report.get("receivedate"),
        "safetyreportid":  report_id,
    }


# ── Main scraper ─────────────────────────────────────────────────────────────
class OpenFDAScraper:
    def __init__(self):
        self.db            = MongoDBManager()
        self.total_inserted = 0
        self.total_skipped  = 0

    def _fetch_page(self, drug: str, skip: int) -> list:
        try:
            resp = requests.get(
                FDA_BASE_URL,
                params={
                    "search": f"patient.drug.medicinalproduct:{drug}",
                    "limit":  100,
                    "skip":   skip,
                },
                timeout=15,
            )
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            print(f"       API error (skip={skip}): {e}")
            return []

    def scrape(self):
        print("=" * 70)
        print("OPENFDA SCRAPER")
        print(f"   {len(DRUGS)} drugs  ×  {PAGES_PER_DRUG} pages  ×  100 reports = "
              f"up to {len(DRUGS) * PAGES_PER_DRUG * 100:,} reports")
        print("=" * 70)

        for drug_idx, drug in enumerate(DRUGS, 1):
            print(f"\n  [{drug_idx}/{len(DRUGS)}] {drug}")
            drug_inserted = 0

            for page in range(PAGES_PER_DRUG):
                skip    = page * 100
                reports = self._fetch_page(drug, skip)

                if not reports:
                    break

                for report in reports:
                    doc = _build_doc(report, drug)
                    if not doc:
                        continue

                    success, reason = self.db.insert_post(doc)
                    if success:
                        self.total_inserted += 1
                        drug_inserted       += 1
                    else:
                        self.total_skipped += 1

                time.sleep(0.5) 

            print(f"      {drug_inserted} nouveaux rapports insérés")

        # ── Summary ──
        print(f"\n{'=' * 70}")
        print(" RÉSUMÉ OPENFDA")
        print(f"{'=' * 70}")
        print(f" Insérés  : {self.total_inserted}")
        print(f" Ignorés  : {self.total_skipped}")
        print(f" Total DB : {self.db.get_stats()['total_documents']}")
        self.db.close()


if __name__ == "__main__":
    scraper = OpenFDAScraper()
    try:
        scraper.scrape()
    except KeyboardInterrupt:
        print("\n Interruption utilisateur")
    finally:
        scraper.db.close()