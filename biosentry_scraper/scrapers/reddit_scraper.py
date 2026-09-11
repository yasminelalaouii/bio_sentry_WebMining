import time
import re
import hashlib
import json
import os
from selenium.webdriver.common.by import By
from scrapers.base_scraper import BaseSeleniumScraper
from database import MongoDBManager


class RedditSeleniumScraper(BaseSeleniumScraper):
    def __init__(self):
        super().__init__()
        self.db = MongoDBManager()
        self.total_inserted = 0
        self.total_skipped = 0

    # ------------------------------------------------------------------ #
    #  CONFIG — subreddits + keywords                                      #
    # ------------------------------------------------------------------ #
    SUBREDDITS = [
        # Médecine / Santé
        "AskDocs", "medicine", "Nootropics",
        "Supplements", "StackAdvice",
        # Effets secondaires / Expériences
        "sideeffects", "pharmacology", "Drugs",
        # Conditions spécifiques
        "Anxiety", "depression", "ADHD", "insomnia",
        "ChronicPain", "Fibromyalgia", "migraine",
        # Médicaments spécifiques
        "antidepressants", "benzodiazepines",
        "zoloft", "lexapro", "Effexor",
    ]

    KEYWORDS = [
        "side effects", "adverse effect", "drug reaction",
        "medication experience", "withdrawal symptoms",
        "prescribed medication", "started taking",
        "stopped taking", "dosage change",
        "side effect report", "drug interaction",
    ]

    # ------------------------------------------------------------------ #
    #  PHASE 1 — Search + collect post URLs                                #
    # ------------------------------------------------------------------ #
    def search_posts(self, subreddit, keyword, max_scroll=30):
        """Search Reddit for posts with robust scrolling and link detection"""
        from bs4 import BeautifulSoup

        query = keyword.replace(" ", "%20")
        url = f"https://www.reddit.com/r/{subreddit}/search/?q={query}&type=posts&sort=relevance&t=all"

        print(f"\n   r/{subreddit} | '{keyword}'")

        try:
            self.driver.get(url)
            time.sleep(6) # Attente initiale plus longue
            self.close_popups()
        except Exception as e:
            print(f"     Erreur chargement: {e}")
            return []

        # ── Scroll Intensif ──
        post_links = set()
        
        for i in range(max_scroll):
            # On scroll par incréments de 1500 pixels
            self.driver.execute_script(f"window.scrollBy(0, 1500);")
            time.sleep(1.5)
            
            # On récupère les liens au fur et à mesure du scroll pour ne rien rater
            current_html = self.driver.page_source
            current_soup = BeautifulSoup(current_html, 'lxml')
            
            for a in current_soup.find_all('a', href=True):
                href = a['href']
                # On capture tout ce qui ressemble à un post Reddit
                if '/comments/' in href and ('/r/' in href or '/user/' in href):
                    if href.startswith('/'):
                        href = f"https://www.reddit.com{href}"
                    # Nettoyage
                    full_url = href.split('?')[0].rstrip('/')
                    if full_url not in post_links:
                        post_links.add(full_url)
            
            if len(post_links) > 100: # Limite raisonnable par recherche
                break

        print(f"     {len(post_links)} posts trouvés")
        return list(post_links)

    # ------------------------------------------------------------------ #
    #  PHASE 2 — Scrape individual post + comments                         #
    # ------------------------------------------------------------------ #
    def scrape_post(self, post_url, subreddit, keyword):
        """Scrape a single post page: title, body text, and top comments"""
        from bs4 import BeautifulSoup

        post_id = self._extract_post_id(post_url)

        # Check duplicate
        if self.db.collection.find_one({"post_id": post_id, "source": "reddit"}):
            self.total_skipped += 1
            return None

        try:
            self.driver.get(post_url)
            time.sleep(5)
            self.close_popups()
            # Scroll to load comments
            for y in [500, 1000, 2000, 3000, 4000]:
                self.driver.execute_script(f"window.scrollTo(0, {y});")
                time.sleep(0.5)
        except Exception as e:
            print(f"  Erreur: {e}")
            return None

        html = self.driver.page_source
        soup = BeautifulSoup(html, 'lxml')

        # ── Extract title ──
        title = ""
        # Method 1: shreddit-post title attribute
        shreddit = soup.find('shreddit-post')
        if shreddit:
            title = shreddit.get('post-title', '') or shreddit.get('title', '')

        # Method 2: h1 tag
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        # Method 3: og:title meta
        if not title:
            og = soup.find('meta', property='og:title')
            if og:
                title = og.get('content', '')

        if not title:
            return None

        # ── Extract post body text ──
        body_text = ""

        # Method 1: div with data-testid=post-content
        content_div = soup.find('div', attrs={'data-testid': 'post-content'})
        if content_div:
            body_text = content_div.get_text(separator=' ', strip=True)

        # Method 2: shreddit-post text content
        if not body_text and shreddit:
            # Find text-body within shreddit-post
            text_body = shreddit.find('div', class_=lambda x: x and 'text-body' in str(x).lower())
            if text_body:
                body_text = text_body.get_text(separator=' ', strip=True)

        # Method 3: Find substantial div that looks like post content
        if not body_text:
            for div in soup.find_all('div'):
                cls = ' '.join(div.get('class', []))
                if any(c in cls.lower() for c in ['md', 'post-content', 'usertext-body', 'expando']):
                    txt = div.get_text(separator=' ', strip=True)
                    if len(txt) > len(body_text):
                        body_text = txt

        # ── Extract comments ──
        comments = self._extract_comments(soup)
        comments_text = '\n---\n'.join(comments[:20])  

        # ── Combine full text ──
        full_text = f"{title}\n\n{body_text}"
        if comments_text:
            full_text += f"\n\n--- COMMENTS ---\n{comments_text}"

        if len(full_text) < 50:
            return None

        # Clean
        full_text = re.sub(r'\s+', ' ', full_text)

        drugs = self.extract_drugs(full_text)

        doc = {
            "post_id":         post_id,
            "source":          "reddit",
            "forum":           f"r/{subreddit}",
            "title":           title,
            "text":            full_text,
            "url":             post_url,
            "drugs_mentioned": drugs,
            "content_type":    "forum_post",
            "search_query":    keyword,
            "num_comments":    len(comments),
        }

        success, _ = self.db.insert_post(doc)
        if success:
            self.total_inserted += 1
            return doc
        return None

    def _extract_comments(self, soup):
        """Extract comment texts from a Reddit post page"""
        comments = []

        # Method 1: shreddit-comment elements
        for comment in soup.find_all('shreddit-comment'):
            # Find the text within the comment
            for div in comment.find_all('div', recursive=True):
                txt = div.get_text(strip=True)
                if 50 < len(txt) < 3000:
                    # Check it's actual comment text, not metadata
                    if not any(skip in txt.lower() for skip in [
                        'reply', 'share', 'report', 'save',
                        'award', 'permalink', 'parent'
                    ]) or len(txt) > 100:
                        comments.append(txt)
                        break  # One text per comment element

        # Method 2: div with comment classes
        if not comments:
            for div in soup.find_all('div', class_=lambda x: x and 'comment' in str(x).lower()):
                # Find md (markdown) divs within comments
                md_div = div.find('div', class_=lambda x: x and 'md' in str(x).lower())
                if md_div:
                    txt = md_div.get_text(separator=' ', strip=True)
                    if 30 < len(txt) < 3000:
                        comments.append(txt)

        # Deduplicate
        seen = set()
        unique_comments = []
        for c in comments:
            fingerprint = c[:80]
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique_comments.append(c)

        return unique_comments

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    def _extract_post_id(self, url):
        """Extract Reddit post ID from URL"""
        match = re.search(r'/comments/([a-z0-9]+)', url)
        if match:
            return f"reddit_{match.group(1)}"
        return f"reddit_{hashlib.md5(url.encode()).hexdigest()[:10]}"

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
            'amoxicillin', 'azithromycin', 'ciprofloxacin',
            'lisinopril', 'losartan', 'metoprolol', 'amlodipine',
            'omeprazole', 'pantoprazole', 'levothyroxine',
            'cetirizine', 'montelukast', 'ozempic', 'semaglutide',
            'atorvastatin', 'meloxicam',
        ]

        text_lower = text.lower()
        return [drug for drug in common_drugs if drug in text_lower]

    # ------------------------------------------------------------------ #
    #  ENTRY POINT                                                         #
    # ------------------------------------------------------------------ #
    def _manual_login(self):
        """Open Reddit login page and wait for the user to log in manually."""
        print("\n" + "=" * 70)
        print(" CONNEXION MANUELLE REDDIT")
        print("=" * 70)
        print("    La page de connexion Reddit va s'ouvrir dans Chrome")
        print("    Connecte-toi avec ton compte Reddit")
        print("    Une fois connecté, reviens ici et appuie sur ENTRÉE")
        print("=" * 70)

        try:
            self.driver.get("https://www.reddit.com/login/")
            time.sleep(3)
        except Exception as e:
            print(f"   Erreur ouverture page login: {e}")

        input("\n   Appuie sur ENTRÉE une fois que tu es connecté à Reddit... ")

        # Verify login by checking for user menu
        try:
            self.driver.get("https://www.reddit.com/")
            time.sleep(3)
            html = self.driver.page_source
            if 'log in' in html.lower() and 'logout' not in html.lower():
                print("   Il semble que tu ne sois pas connecté. Le scraper continue quand même.")
            else:
                print("   Connexion détectée ! Scraping avec compte authentifié.\n")
        except Exception:
            pass

    def scrape(self):
        print("=" * 70)
        print(" REDDIT SCRAPER")
        print("=" * 70)

        # ── Manual login ──
        self._manual_login()

        all_post_urls = {} 
        checkpoint_file = "reddit_urls_checkpoint.json"
        progress_file   = "reddit_scraping_progress.json"  

        if os.path.exists(checkpoint_file):
            use_cp = input(f"\n Checkpoint trouvé ({checkpoint_file}). Charger la liste existante ? (o/n) : ").lower()
            if use_cp == 'o':
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    all_post_urls = json.load(f)
                print(f" {len(all_post_urls)} URLs chargées. Passage direct à la Phase 2.")

        # ── Phase 1: Collect post URLs (only if no checkpoint used) ──
        if not all_post_urls:
            print(f"\n{'='*70}")
            print(f" Phase 1: Recherche dans {len(self.SUBREDDITS)} subreddits × {len(self.KEYWORDS)} keywords")
            print(f"{'='*70}")

            for subreddit in self.SUBREDDITS:
                for keyword in self.KEYWORDS:
                    posts = self.search_posts(subreddit, keyword)
                    for url in posts:
                        if url not in all_post_urls:
                            all_post_urls[url] = (subreddit, keyword)
                    self.delay(3, 6)

            # Save URL checkpoint
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(all_post_urls, f, indent=4)
            print(f"\n Liste de {len(all_post_urls)} URLs sauvegardée dans {checkpoint_file}")

        # ── Load scraping progress (already-visited URLs) ──
        already_done = set()
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                already_done = set(json.load(f))
            print(f"\n Reprise détectée : {len(already_done)} URLs déjà scrapées — elles seront ignorées.")
        else:
       
            print("\n  Pas de fichier de progression trouvé. Interrogation de MongoDB pour reconstruire l'état...")
            existing_ids = set(
                doc["post_id"]
                for doc in self.db.collection.find({"source": "reddit"}, {"post_id": 1, "_id": 0})
            )
            if existing_ids:
                for url in all_post_urls:
                    pid = self._extract_post_id(url)
                    if pid in existing_ids:
                        already_done.add(url)
                # Save bootstrapped progress so future runs load it directly
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(list(already_done), f)
                print(f" Bootstrap terminé : {len(already_done)} URLs déjà en DB — fichier de progression créé.")

        remaining = {url: info for url, info in all_post_urls.items() if url not in already_done}
        total     = len(all_post_urls)
        done_count = len(already_done)

        print(f"\n{'='*70}")
        print(f" Phase 2: {len(remaining)} posts restants sur {total} (déjà fait : {done_count})")
        print(f"{'='*70}")

        # ── Phase 2: Scrape each remaining post ──
        for i, (url, info) in enumerate(remaining.items(), done_count + 1):
            subreddit, keyword = info[0], info[1]

            print(f"\n   [{i}/{total}] r/{subreddit}", end="")

            # Retry logic for MongoDB / Network
            for attempt in range(3):
                try:
                    result = self.scrape_post(url, subreddit, keyword)
                    if result:
                        print(f" {result['title'][:50]}...")
                    break  # Success
                except Exception as e:
                    if "replica set" in str(e).lower() or "Primary" in str(e):
                        print(f"  DB Timeout (essai {attempt+1}/3)...", end="")
                        time.sleep(10)
                        self.db = MongoDBManager()  
                    else:
                        print(f"  Erreur: {str(e)[:50]}")
                        break

            # Mark URL as done and save progress every 10 posts
            already_done.add(url)
            if len(already_done) % 10 == 0:
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(list(already_done), f)

            self.delay(2, 4)

        # Final save of progress
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(list(already_done), f)

        # ── Summary ──
        print(f"\n{'='*70}")
        print(" RÉSUMÉ REDDIT")
        print(f"{'='*70}")
        print(f" Insérés  : {self.total_inserted}")
        print(f" Ignorés  : {self.total_skipped}")
        print(f" Total DB : {self.db.get_stats()['total_documents']}")

        self.db.close()
        self.quit()


if __name__ == "__main__":
    scraper = RedditSeleniumScraper()
    try:
        scraper.scrape()
    except KeyboardInterrupt:
        print("\n Interruption utilisateur")
    except Exception as e:
        print(f"\n Erreur: {e}")
    finally:
        scraper.quit()