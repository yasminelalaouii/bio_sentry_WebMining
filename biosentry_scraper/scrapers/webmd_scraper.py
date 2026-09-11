import time
import re
import hashlib
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from scrapers.base_scraper import BaseSeleniumScraper
from database import MongoDBManager


class WebMDScraper(BaseSeleniumScraper):
    def __init__(self):
        super().__init__()
        self.db = MongoDBManager()
        self.total_inserted = 0
        self.total_skipped = 0

    # ------------------------------------------------------------------ #
    #  DRUG LIST — target drugs to scrape                                  #
    # ------------------------------------------------------------------ #
    TARGET_DRUGS = [
        # ── Psychiatrie / Anxiété / Dépression ──
        {"name": "Zoloft (Sertraline)","detail_url": "https://www.webmd.com/drugs/2/drug-35/zoloft-oral/details", "review_slug": "sertraline-zoloft"},
        {"name": "Lexapro (Escitalopram)","detail_url": "https://www.webmd.com/drugs/2/drug-63990/lexapro-oral/details","review_slug": "escitalopram-lexapro"},
        {"name": "Cymbalta (Duloxetine)","detail_url": "https://www.webmd.com/drugs/2/drug-91491/cymbalta-oral/details","review_slug": "duloxetine-cymbalta"},

        # ── Douleur / Anti-inflammatoires ──
        {"name": "Ibuprofen (Advil)", "detail_url": "https://www.webmd.com/drugs/2/drug-5166-9368/ibuprofen-oral/ibuprofen-oral/details", "review_slug": "ibuprofen-advil-motrin"},
        {"name": "Prednisone", "detail_url": "https://www.webmd.com/drugs/2/drug-6007-9383/prednisone-oral/prednisone-oral/details", "review_slug": "prednisone-deltasone"},
        {"name": "Gabapentin (Neurontin)","detail_url": "https://www.webmd.com/drugs/2/drug-14208/gabapentin-oral/details", "review_slug": "gabapentin-neurontin"},
        {"name": "Meloxicam (Mobic)", "detail_url": "https://www.webmd.com/drugs/2/drug-911/meloxicam-oral/details", "review_slug": "meloxicam-mobic"},

        # ── Antibiotiques ──
        {"name": "Amoxicillin", "detail_url": "https://www.webmd.com/drugs/2/drug-1531-3295/amoxicillin-oral/amoxicillin-oral/details", "review_slug": "amoxicillin-amoxil"},
        {"name": "Azithromycin (Z-Pack)","detail_url": "https://www.webmd.com/drugs/2/drug-1702-3506/azithromycin-oral/azithromycin-oral/details", "review_slug": "azithromycin-zithromax-z-pak-zmax"},
        {"name": "Ciprofloxacin (Cipro)","detail_url": "https://www.webmd.com/drugs/2/drug-7748-4044/ciprofloxacin-oral/ciprofloxacin-oral/details", "review_slug": "ciprofloxacin-cipro"},

        # ── Cardiologie / Tension artérielle ──
        {"name": "Lisinopril","detail_url": "https://www.webmd.com/drugs/2/drug-6873-9371/lisinopril-oral/lisinopril-oral/details", "review_slug": "lisinopril-prinivil-zestril"},
        {"name": "Losartan (Cozaar)","detail_url": "https://www.webmd.com/drugs/2/drug-6659-5765/losartan-oral/losartan-oral/details", "review_slug": "losartan-cozaar"},
        {"name": "Metoprolol (Toprol)","detail_url": "https://www.webmd.com/drugs/2/drug-6987-7098/metoprolol-succinate-oral/metoprolol-succinate-extended-release-oral/details", "review_slug": "metoprolol-lopressor"},
        {"name": "Amlodipine (Norvasc)","detail_url": "https://www.webmd.com/drugs/2/drug-5765-8043/amlodipine-oral/amlodipine-oral/details","review_slug": "amlodipine-norvasc"},

        # ── Cholestérol ──
        {"name": "Atorvastatin (Lipitor)","detail_url": "https://www.webmd.com/drugs/2/drug-5765/atorvastatin-oral/details","review_slug": "atorvastatin-calcium-lipitor"},

        # ── Diabète ──
        {"name": "Metformin","detail_url": "https://www.webmd.com/drugs/2/drug-11285-7061/metformin-oral/metformin-oral/details","review_slug": "metformin"},
        {"name": "Ozempic (Semaglutide)","detail_url": "https://www.webmd.com/drugs/2/drug-174491/ozempic-subcutaneous/details","review_slug": "ozempic-semaglutide"},

        # ── Gastro / Estomac ──
        {"name": "Omeprazole (Prilosec)","detail_url": "https://www.webmd.com/drugs/2/drug-3766-2231/omeprazole-oral/omeprazole-delayed-release-oral/details", "review_slug": "omeprazole-prilosec-otc"},
        {"name": "Pantoprazole (Protonix)","detail_url": "https://www.webmd.com/drugs/2/drug-20533-7087/pantoprazole-oral/pantoprazole-delayed-release-oral/details", "review_slug": "pantoprazole-protonix"},

        # ── Allergie / Asthme ──
        {"name": "Cetirizine (Zyrtec)","detail_url": "https://www.webmd.com/drugs/2/drug-3780-3069/cetirizine-oral/cetirizine-oral/details", "review_slug": "cetirizine-zyrtec"},
        {"name": "Montelukast (Singulair)", "detail_url": "https://www.webmd.com/drugs/2/drug-18120/montelukast-oral/details","review_slug": "montelukast-singulair"},

        # ── Thyroïde ──
        {"name": "Levothyroxine (Synthroid)", "detail_url": "https://www.webmd.com/drugs/2/drug-1433/levothyroxine-oral/details","review_slug": "levothyroxine-synthroid-tirosint"},

        # ── Sommeil ──
        {"name": "Ambien (Zolpidem)","detail_url": "https://www.webmd.com/drugs/2/drug-9690/ambien-oral/details","review_slug": "zolpidem-ambien"},
        {"name": "Trazodone","detail_url": "https://www.webmd.com/drugs/2/drug-11188/trazodone-oral/details","review_slug": "trazodone"},
    ]

    # ------------------------------------------------------------------ #
    #  PHASE 1 — Scrape drug detail page                                   #
    # ------------------------------------------------------------------ #
    def scrape_drug_details(self, drug_info):
        """Scrape the main drug information page (uses, side effects, etc.)"""
        from bs4 import BeautifulSoup

        drug_name = drug_info['name']
        url = drug_info['detail_url']
        post_id = f"webmd_detail_{self._url_to_id(url)}"

        print(f"\n    {drug_name}", end="")

        # Check duplicate
        if self.db.collection.find_one({"post_id": post_id, "source": "webmd"}):
            self.total_skipped += 1
            print(f"DOUBLON")
            return None

        try:
            self.driver.get(url)
            time.sleep(5)
            self.scroll_page(max_y=3000, step=500)
        except Exception as e:
            print(f"\n     Erreur chargement: {e}")
            return None

        html = self.driver.page_source
        soup = BeautifulSoup(html, 'lxml')

        # Extract structured content
        sections = {}

        # Extract all h3 headings and their following content
        for h3 in soup.find_all('h3'):
            heading = h3.get_text(strip=True)
            content_parts = []

            # Collect all siblings until next h3 or h2
            sibling = h3.find_next_sibling()
            while sibling and sibling.name not in ['h3', 'h2']:
                txt = sibling.get_text(separator=' ', strip=True)
                if txt and len(txt) > 5:
                    content_parts.append(txt)
                sibling = sibling.find_next_sibling()

            if content_parts:
                sections[heading] = ' '.join(content_parts)

        # Fallback: get main content area
        text = ""
        if sections:
            text = '\n\n'.join(f"## {k}\n{v}" for k, v in sections.items())
            print(f"\n       {len(sections)} sections, {len(text)} chars")
        else:
            # Try to get main content div
            main = soup.find('main') or soup.find('div', id='main-container')
            if main:
                text = main.get_text(separator=' ', strip=True)
                print(f"\n       main content {len(text)} chars")
            else:
                # Dense div fallback
                max_len = 0
                for div in soup.find_all('div'):
                    txt = div.get_text(strip=True)
                    if 100 < len(txt) < 50000 and len(txt) > max_len:
                        max_len = len(txt)
                        text = txt
                if text:
                    print(f"\n       div dense {len(text)} chars")

        if not text or len(text) < 50:
            print(f"\n       Texte trop court ({len(text) if text else 0})")
            return None

        # Clean
        text = re.sub(r'\s+', ' ', text)

        drugs = self.extract_drugs(text)

        doc = {
            "post_id":         post_id,
            "source":          "webmd",
            "forum":           "drug_details",
            "title":           f"WebMD - {drug_name} - Drug Information",
            "text":            text,
            "url":             url,
            "drugs_mentioned": drugs,
            "drug_name":       drug_name,
            "content_type":    "drug_info",
        }

        success, _ = self.db.insert_post(doc)
        if success:
            self.total_inserted += 1
            return doc
        return None

    # ------------------------------------------------------------------ #
    #  PHASE 2 — Scrape user reviews (1 review = 1 document)               #
    # ------------------------------------------------------------------ #
    def scrape_drug_reviews(self, drug_info, max_pages=30):
        from bs4 import BeautifulSoup

        drug_name = drug_info['name']
        review_slug = drug_info['review_slug']
        base_review_url = f"https://reviews.webmd.com/drugs/drugreview-{review_slug}"

        print(f"\n    Reviews: {drug_name}")

        reviews_collected = 0
        empty_pages = 0  

        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                page_url = base_review_url
            else:
                page_url = f"{base_review_url}?page={page_num}"

            print(f"       Page {page_num}", end="")

            try:
                self.driver.get(page_url)
                time.sleep(5)
                self.scroll_page(max_y=5000, step=600)
                self.close_popups()
            except Exception as e:
                print(f"  Erreur: {e}")
                break

            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')

            # ── Extract individual reviews ──
            individual_reviews = self._extract_individual_reviews(soup)

            if not individual_reviews:
                empty_pages += 1
                print(f"  Aucun review trouvé")
                if empty_pages >= 2:
                    print(f"       {empty_pages} pages vides consécutives → arrêt")
                    break
                continue
            else:
                empty_pages = 0  # Reset counter

            # ── Insert each review as its own document ──
            page_inserted = 0
            page_skipped = 0

            for idx, review_text in enumerate(individual_reviews):
                # Generate unique ID per review
                review_hash = hashlib.md5(review_text[:200].encode()).hexdigest()[:8]
                post_id = f"webmd_rv_{self._url_to_id(review_slug)}_p{page_num}_r{idx}_{review_hash}"

                # Check duplicate
                if self.db.collection.find_one({"post_id": post_id, "source": "webmd"}):
                    self.total_skipped += 1
                    page_skipped += 1
                    continue

                drugs = self.extract_drugs(review_text)

                doc = {
                    "post_id":         post_id,
                    "source":          "webmd",
                    "forum":           "user_reviews",
                    "title":           f"WebMD Review - {drug_name} (p{page_num} #{idx+1})",
                    "text":            review_text,
                    "url":             page_url,
                    "drugs_mentioned": drugs,
                    "drug_name":       drug_name,
                    "content_type":    "user_review",
                    "page_num":        page_num,
                    "review_index":    idx,
                }

                success, _ = self.db.insert_post(doc)
                if success:
                    self.total_inserted += 1
                    reviews_collected += 1
                    page_inserted += 1

            print(f"  {page_inserted} insérés, {page_skipped} doublons (total page: {len(individual_reviews)})")

            self.delay(3, 6)

        print(f"       {reviews_collected} reviews collectés pour {drug_name}")
        return reviews_collected

    def _extract_individual_reviews(self, soup):
        """Extract individual review texts from a WebMD review page."""
        reviews = []

        # ── Method 1: Structured review containers ──
        review_containers = (
            soup.find_all('div', class_='review-comment') or
            soup.find_all('div', class_='user-review') or
            soup.find_all('div', class_='review-details') or
            soup.find_all('div', attrs={'data-review-id': True}) or
            soup.find_all('p', class_=lambda x: x and 'review' in str(x).lower()) or
            []
        )

        if review_containers:
            for block in review_containers:
                txt = block.get_text(separator=' ', strip=True)
                if len(txt) >= 50:
                    reviews.append(txt)
            if reviews:
                return reviews

        # ── Method 2: Find all substantial text blocks that look like reviews ──
        # WebMD reviews are typically 80-2000 chars, personal experiences
        skip_phrases = [
            'privacy policy', 'cookie policy', 'terms of use',
            'advertise', 'editorial policy', 'webmd does not',
            'pill identifier', 'interaction checker', 'find a doctor',
            'drugs & supplements', 'sign up', 'log in', 'subscribe',
            'read more', 'read less', 'see more', 'see less',
            'most voted', 'most helpful', 'most recent', 'highest rating',
            'share your experience', 'user-generated content',
            'the opinions expressed', 'important information',
            'view free coupon', 'show ratings', 'no data',
        ]

        seen_texts = set()  # Deduplicate within page
        candidate_reviews = []

        for elem in soup.find_all(['div', 'p', 'span']):
            txt = elem.get_text(strip=True)

            # Reviews are typically 80-5000 chars
            if len(txt) < 80 or len(txt) > 5000:
                continue

            # Skip navigation/UI elements
            txt_lower = txt.lower()
            if any(skip in txt_lower for skip in skip_phrases):
                continue

            # Skip if text contains too many links (navigation)
            links_in_elem = elem.find_all('a')
            if len(links_in_elem) > 5:
                continue

            # Deduplicate: use first 100 chars as fingerprint
            fingerprint = txt[:100]
            if fingerprint in seen_texts:
                continue
            seen_texts.add(fingerprint)

            # Check if it reads like a review (personal experience language)
            review_indicators = [
                'i ', 'my ', 'me ', 'was ', 'had ', 'took ', 'taking ',
                'doctor ', 'prescribed ', 'side effect', 'worked ',
                'helped ', 'felt ', 'feeling ', 'experience',
                'medication', 'medicine', 'drug ', 'dose', 'mg',
                'days', 'weeks', 'months', 'years',
                'pain', 'anxiety', 'depression', 'sleep',
                'nausea', 'dizziness', 'headache', 'stomach',
            ]
            indicator_count = sum(1 for ind in review_indicators if ind in txt_lower)
            if indicator_count >= 3:
                candidate_reviews.append(txt)

        if candidate_reviews:
            candidate_reviews.sort(key=len, reverse=True)
            final_reviews = []
            for review in candidate_reviews:
                is_subset = False
                for existing in final_reviews:
                    if review[:80] in existing:
                        is_subset = True
                        break
                if not is_subset:
                    final_reviews.append(review)
            reviews = final_reviews

        return reviews

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    def _url_to_id(self, url):
        """Generate a stable short ID from a URL or slug"""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def extract_drugs(self, text):
        common_drugs = [
            'adderall', 'xanax', 'valium', 'klonopin', 'ativan', 'lorazepam',
            'oxycodone', 'hydrocodone', 'tramadol', 'morphine', 'codeine',
            'prozac', 'zoloft', 'lexapro', 'paxil', 'celexa', 'fluoxetine',
            'wellbutrin', 'effexor', 'cymbalta', 'trazodone', 'sertraline',
            'ambien', 'lunesta', 'sonata', 'zolpidem',
            'ritalin', 'concerta', 'vyvanse', 'strattera', 'methylphenidate',
            'gabapentin', 'pregabalin', 'lyrica', 'neurontin',
            'suboxone', 'methadone', 'naltrexone', 'buprenorphine',
            'lithium', 'seroquel', 'abilify', 'risperdal', 'zyprexa', 'quetiapine',
            'ibuprofen', 'aspirin', 'acetaminophen', 'paracetamol', 'tylenol',
            'lipitor', 'metformin', 'insulin', 'warfarin', 'prednisone',
            'alprazolam', 'clonazepam', 'diazepam', 'escitalopram', 'duloxetine',
            'venlafaxine', 'bupropion', 'lisinopril', 'losartan', 'metoprolol',
        ]

        text_lower = text.lower()
        return [drug for drug in common_drugs if drug in text_lower]

    # ------------------------------------------------------------------ #
    #  ENTRY POINT                                                         #
    # ------------------------------------------------------------------ #
    def scrape(self):
        print("=" * 70)
        print(" WEBMD.COM DRUG SCRAPER")
        print("=" * 70)

        # ── Phase 1: Drug detail pages ──
        print(f"\n{'='*70}")
        print(f" Phase 1: Scraping {len(self.TARGET_DRUGS)} drug info pages")
        print(f"{'='*70}")

        for i, drug in enumerate(self.TARGET_DRUGS, 1):
            print(f"\n   [{i}/{len(self.TARGET_DRUGS)}]", end="")
            self.scrape_drug_details(drug)
            self.delay(3, 6)

        # ── Phase 2: User reviews ──
        print(f"\n{'='*70}")
        print(f" Phase 2: Scraping user reviews for {len(self.TARGET_DRUGS)} drugs")
        print(f"{'='*70}")

        for i, drug in enumerate(self.TARGET_DRUGS, 1):
            print(f"\n   [{i}/{len(self.TARGET_DRUGS)}]", end="")
            self.scrape_drug_reviews(drug, max_pages=30)
            self.delay(5, 8)

        # ── Summary ──
        print(f"\n{'='*70}")
        print(" RÉSUMÉ WEBMD")
        print(f"{'='*70}")
        print(f" Insérés  : {self.total_inserted}")
        print(f"  Ignorés  : {self.total_skipped}")
        print(f" Total DB : {self.db.get_stats()['total_documents']}")

        self.db.close()
        self.quit()


if __name__ == "__main__":
    scraper = WebMDScraper()
    try:
        scraper.scrape()
    except KeyboardInterrupt:
        print("\n Interruption utilisateur")
    except Exception as e:
        print(f"\n Erreur: {e}")
    finally:
        scraper.quit()
