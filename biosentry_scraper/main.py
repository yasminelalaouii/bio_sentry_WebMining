import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scrapers.webmd_scraper import WebMDScraper
from scrapers.reddit_scraper import RedditSeleniumScraper
from scrapers.openfda_scraper import OpenFDAScraper
from scrapers.drugsforum_scraper import DrugsForumScraper


def main():
    print("=" * 70)
    print("  BIO-SENTRY WEB SCRAPER")
    print("  Source: WebMD.com")
    print("=" * 70)
    
    scraper = DrugsForumScraper()
    try:
        scraper.scrape()
    except KeyboardInterrupt:
        print("\n Interruption")
    except Exception as e:
        print(f"\n Erreur: {e}")
    finally:
        scraper.quit()
    
    print("\n" + "=" * 70)
    print(" SCRAPING TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    main()