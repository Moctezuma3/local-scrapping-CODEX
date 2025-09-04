from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys


@dataclass
class Business:
    """Holds business data."""
    name: str = None
    address: str = None
    website: str = None


@dataclass
class BusinessList:
    """Holds list of Business objects, and saves to both Excel and CSV."""
    business_list: list[Business] = field(default_factory=list)
    save_at = 'output'

    def dataframe(self):
        """Transform business_list to pandas dataframe."""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_excel(self, filename):
        """Save pandas dataframe to Excel (xlsx) file."""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        """Save pandas dataframe to CSV file."""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)


def scrape_page(page, business_list: BusinessList):
    """Scrape all listings from the current page."""
    try:
        listings = page.locator('div.SearchResultList_listElementWrapper__KRuKD').all()
        for idx, listing in enumerate(listings):
            try:
                business = Business()

                # --- Nom ---
                name_selector = 'h2[data-testid="title"]'
                if listing.locator(name_selector).count() > 0:
                    business.name = listing.locator(name_selector).first.inner_text()
                else:
                    business.name = ""

                # --- Adresse ---
                address_selector = 'address'
                if listing.locator(address_selector).count() > 0:
                    business.address = listing.locator(address_selector).first.inner_text()
                else:
                    business.address = ""

                # --- Website ---
                website_selector = 'a.ListElement_link__LabW8'
                if listing.locator(website_selector).count() > 0:
                    href = listing.locator(website_selector).first.get_attribute("href")
                    business.website = f"https://www.local.ch{href}"
                else:
                    business.website = ""

                business_list.business_list.append(business)

            except Exception as e:
                print(f"Erreur sur un listing {idx}: {e}")

        return len(listings)

    except Exception as e:
        print(f"Erreur pendant le scraping de la page: {e}")
        return 0


def main():
    ########
    # Input
    ########
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str, required=True)
    args = parser.parse_args()

    search_term = args.search.strip()

    ###########
    # Scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        business_list = BusinessList()

        try:
            # Aller sur local.ch
            page.goto("https://www.local.ch/fr", timeout=60000)
            page.wait_for_timeout(2000)

            # Faire la recherche
            page.get_by_test_id("home-stage-container").get_by_test_id("search-q-input").fill(search_term)
            page.get_by_test_id("home-stage-container").get_by_test_id("search-q-input").press("Enter")
            page.wait_for_timeout(4000)

            # Pagination
            while True:
                listings_count = scrape_page(page, business_list)
                if listings_count == 0:
                    break

                try:
                    next_button = page.get_by_role("button", name="Suivant", exact=True)
                    if next_button.is_enabled():
                        next_button.click()
                        page.wait_for_timeout(3000)
                    else:
                        break
                except Exception:
                    break

        finally:
            browser.close()

        #########
        # Output
        #########
        filename = f"local_ch_data_{search_term.replace(' ', '_')}"
        business_list.save_to_excel(filename)
        business_list.save_to_csv(filename)
        print(f"✅ Données sauvegardées : {filename}.xlsx / .csv")


if __name__ == "__main__":
    main()
