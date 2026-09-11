import time

MAX_ROWS = 2000  # Hard stop — scraper exits Phase 2 once this is reached
import re
import hashlib
from selenium.webdriver.common.by import By
from scrapers.base_scraper import BaseSeleniumScraper
from database import MongoDBManager


class DrugsForumScraper(BaseSeleniumScraper):
    def __init__(self):
        super().__init__()
        self.db = MongoDBManager()
        self.total_inserted = 0
        self.total_skipped = 0

    # ------------------------------------------------------------------ #
    #  FORUMS TO SCRAPE                                                    #
    # ------------------------------------------------------------------ #
    FORUMS = [
        ("https://drugs-forum.com/forums/pharmaceuticals.42/","Pharmaceuticals",30),
        ("https://drugs-forum.com/forums/opioids.7/","Opioids",30),
        ("https://drugs-forum.com/forums/cannabis.8/","Cannabis",20),
    ]

    DRUG_KEYWORDS = [
        'adderall', 'xanax', 'valium', 'klonopin', 'ativan', 'lorazepam',
        'oxycodone', 'hydrocodone', 'tramadol', 'morphine', 'codeine',
        'prozac', 'zoloft', 'lexapro', 'paxil', 'celexa', 'fluoxetine',
        'wellbutrin', 'effexor', 'cymbalta', 'trazodone', 'sertraline',
        'ambien', 'lunesta', 'zolpidem', 'ritalin', 'concerta', 'vyvanse',
        'strattera', 'methylphenidate', 'gabapentin', 'pregabalin', 'lyrica',
        'suboxone', 'methadone', 'naltrexone', 'buprenorphine', 'lithium',
        'seroquel', 'abilify', 'risperdal', 'zyprexa', 'quetiapine',
        'ibuprofen', 'aspirin', 'acetaminophen', 'paracetamol', 'tylenol',
        'lipitor', 'metformin', 'insulin', 'warfarin', 'prednisone',
        'amoxicillin', 'azithromycin', 'ciprofloxacin', 'lisinopril',
        'losartan', 'metoprolol', 'amlodipine', 'omeprazole', 'levothyroxine',
        'cetirizine', 'montelukast', 'atorvastatin', 'meloxicam',
    ]

    # ------------------------------------------------------------------ #
    #  PHASE 1 — Collect thread URLs from forum listing pages              #
    # ------------------------------------------------------------------ #
    def get_forum_threads(self, forum_url, forum_name, max_pages=30):
        from bs4 import BeautifulSoup

        print(f"\n  Forum: {forum_name}")
        threads_data = []

        for page_num in range(1, max_pages + 1):
            page_url = f"{forum_url}page-{page_num}" if page_num > 1 else forum_url
            print(f"    Page {page_num}", end=" ")

            try:
                self.driver.get(page_url)
                time.sleep(4)
                for y in [300, 600, 1000]:
                    self.driver.execute_script(f"window.scrollTo(0, {y});")
                    time.sleep(0.3)
            except Exception as e:
                print(f"  Error: {e}")
                break

            html = self.driver.page_source
            soup = BeautifulSoup(html, 'lxml')

            # XenForo 2: structItem elements
            thread_elems = soup.find_all('div', class_='structItem')
            print(f"-> {len(thread_elems)} threads", end="")

            if not thread_elems:
                print(" (empty page, stopping)")
                break

            page_added = 0
            for elem in thread_elems:
                try:
                    title_div = elem.find('div', class_='structItem-title')
                    if not title_div:
                        continue

                    link = title_div.find('a')
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    href  = link.get('href', '')

                    if not title or not href:
                        continue

                    # Build full URL
                    if href.startswith('/'):
                        url = f"https://drugs-forum.com{href}"
                    elif not href.startswith('http'):
                        url = f"https://drugs-forum.com/{href}"
                    else:
                        url = href

                    thread_id = self._extract_thread_id(url)
                    threads_data.append({
                        'thread_id': thread_id,
                        'title':     title,
                        'url':       url,
                        'forum':     forum_name,
                    })
                    page_added += 1

                except Exception:
                    continue

            print(f" | added {page_added}")
            self.delay(2, 4)

        # Deduplicate by thread_id
        seen = set()
        unique = []
        for t in threads_data:
            if t['thread_id'] not in seen:
                seen.add(t['thread_id'])
                unique.append(t)

        print(f"  => {len(unique)} unique threads from {forum_name}")
        return unique

    # ------------------------------------------------------------------ #
    #  PHASE 2 — Scrape individual thread content                          #
    # ------------------------------------------------------------------ #
    def get_thread_content(self, thread_data):
        from bs4 import BeautifulSoup

        url       = thread_data['url']
        thread_id = thread_data['thread_id']
        title     = thread_data['title']

        # Duplicate check
        if self.db.collection.find_one({"post_id": thread_id, "source": "drugs_forum"}):
            self.total_skipped += 1
            print(" SKIP", end="")
            return None

        try:
            self.driver.get(url)
            time.sleep(5)
            for y in [200, 500, 800, 1200]:
                self.driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(0.4)
        except Exception as e:
            print(f" ERR({e})", end="")
            return None

        html = self.driver.page_source
        soup = BeautifulSoup(html, 'lxml')

        # ── Extract text — multiple fallback methods ──
        text = ""

        # Method 1: XenForo 2 bbWrapper
        bb = soup.find('div', class_='bbWrapper')
        if bb:
            text = bb.get_text(separator=' ', strip=True)

        # Method 2: Other XenForo message classes
        if not text:
            for cls in ['message-content', 'messageContent', 'message-body',
                        'message-main', 'message-text', 'post-content']:
                elem = soup.find(class_=cls)
                if elem:
                    text = elem.get_text(separator=' ', strip=True)
                    break

        # Method 3: First <article> tag
        if not text:
            articles = soup.find_all('article')
            if articles:
                text = articles[0].get_text(separator=' ', strip=True)

        # Method 4: Densest <div>
        if not text:
            max_len = 0
            for div in soup.find_all('div'):
                txt = div.get_text(strip=True)
                if 100 < len(txt) < 50000 and len(txt) > max_len:
                    max_len = len(txt)
                    text = txt

        if not text or len(text) < 50:
            print(" SHORT", end="")
            return None

        # Clean
        text = re.sub(r'\s+', ' ', text).strip()

        drugs = self._extract_drugs(text)

        # Count comments (number of posts in thread beyond the first)
        comment_elems = soup.find_all('article', class_=lambda c: c and 'message' in str(c).lower())
        num_comments = max(0, len(comment_elems) - 1)

        doc = {
            "post_id":         thread_id,
            "source":          "drugs_forum",
            "forum":           f"drugs-forum.com/{thread_data['forum']}",
            "title":           title[:300],
            "text":            text,
            "url":             url,
            "drugs_mentioned": drugs,
            "content_type":    "forum_post",
            "search_query":    thread_data['forum'],
            "num_comments":    num_comments,
        }

        success, _ = self.db.insert_post(doc)
        if success:
            self.total_inserted += 1
            print(f" OK ({len(text)} chars)", end="")
            return doc
        return None

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    def _extract_thread_id(self, url):
        # XenForo: /threads/title.12345/
        m = re.search(r'\.(\d+)/?$', url)
        if m:
            return f"df_{m.group(1)}"
        m = re.search(r'/(?:posts|threads)/(\d+)', url)
        if m:
            return f"df_{m.group(1)}"
        m = re.search(r'(\d+)(?:/|$)', url)
        if m:
            return f"df_{m.group(1)}"
        return f"df_{hashlib.md5(url.encode()).hexdigest()[:10]}"

    def _extract_drugs(self, text):
        low = text.lower()
        return [d for d in self.DRUG_KEYWORDS if d in low]

    # ------------------------------------------------------------------ #
    #  ENTRY POINT                                                         #
    # ------------------------------------------------------------------ #
    def scrape(self):
        print("=" * 70)
        print("DRUGS-FORUM.COM SCRAPER (v4 - Expanded)")
        print(f"  {len(self.FORUMS)} forums, target 2000+ rows")
        print("=" * 70)

        # Phase 1: collect all thread URLs
        all_threads = []
        for forum_url, forum_name, max_pages in self.FORUMS:
            threads = self.get_forum_threads(forum_url, forum_name, max_pages)
            all_threads.extend(threads)
            self.delay(3, 6)

        # Deduplicate across all forums
        seen = set()
        unique_threads = []
        for t in all_threads:
            if t['thread_id'] not in seen:
                seen.add(t['thread_id'])
                unique_threads.append(t)

        print(f"\n{'='*70}")
        print(f"Phase 2: {len(unique_threads)} unique threads to scrape")
        print(f"{'='*70}")

        # Phase 2: scrape each thread (stops at MAX_ROWS)
        for i, thread in enumerate(unique_threads, 1):
            if self.total_inserted >= MAX_ROWS:
                print(f"\n  Target of {MAX_ROWS} rows reached — stopping early.")
                break
            print(f"\n  [{i}/{len(unique_threads)}] {thread['title'][:55]}...", end="")
            self.get_thread_content(thread)
            self.delay(1, 3)

        # Summary
        print(f"\n\n{'='*70}")
        print("RESUME DRUGS-FORUM")
        print(f"{'='*70}")
        print(f"Inseres : {self.total_inserted}")
        print(f"Ignores : {self.total_skipped}")
        print(f"Total DB: {self.db.get_stats()['total_documents']}")

        self.db.close()
        self.quit()


if __name__ == "__main__":
    scraper = DrugsForumScraper()
    try:
        scraper.scrape()
    except KeyboardInterrupt:
        print("\n Interruption")
    except Exception as e:
        print(f"\n Erreur: {e}")
    finally:
        scraper.quit()