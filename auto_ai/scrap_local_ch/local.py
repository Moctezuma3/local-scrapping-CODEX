from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import re
import argparse
import os
import sys

@dataclass
class Business:
    website: str = None
    name: str = None
    address: str = None
    postal_code: str = None
    city: str = None

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at = 'output'

    def dataframe(self):
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def split_address(self, address):
        match = re.search(r'(.+),\s*(\d{4,5})\s*(.+)', address)
        if match:
            return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
        else:
            return address, '', ''  

    def process_data(self):
        df = self.dataframe()
        df.dropna(axis=1, how='all', inplace=True)
        
        return df

    def save_to_excel(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        processed_df = self.process_data()
        processed_df.to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        processed_df = self.process_data()
        processed_df.to_csv(f"{self.save_at}/{filename}.csv", index=False)

def scrape_page(page, business_list):
    try:
        listings_container = page.locator('div[data-testid="search-result-container"]')
        if listings_container.count() > 0:
            listings = listings_container.locator('div.SearchResultList_listElementWrapper__KRuKD').all()

            for listing_index, listing in enumerate(listings):
                try:
                    business = Business()
                    name_selector = 'h2[data-testid="title"]'
                    if listing.locator(name_selector).count() > 0:
                        business.name = listing.locator(name_selector).first.inner_text()
                    else:
                        business.name = ""

                    address_selector = 'address'
                    if listing.locator(address_selector).count() > 0:
                        full_address = listing.locator(address_selector).first.inner_text()
                        business.address, business.postal_code, business.city = business_list.split_address(full_address)
                    else:
                        business.address = ""
                        business.postal_code = ""
                        business.city = ""

                    website_selector = 'a.ListElement_link__LabW8'
                    if listing.locator(website_selector).count() > 0:
                        business.website = "local.ch/" + listing.locator(website_selector).first.get_attribute("href")
                    else:
                        business.website = ""

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occurred for listing {listing_index}: {e}')

            return len(listings)
        else:
            return 0
    except Exception as e:
        return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str, required=True)
    args = parser.parse_args()
    
    if args.search:
        search_term = args.search
    else:
        sys.exit()

    input_file_name = 'input.txt'
    input_file_path = os.path.join(os.getcwd(), input_file_name)
    if not os.path.exists(input_file_path):
        sys.exit()

    with open(input_file_path, 'r') as file:
        lines = [line.strip() for line in file.readlines()]
    
    search_list = [f"{search_term} {line}" for line in lines]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.local.ch/fr", timeout=60000)
        page.wait_for_timeout(5000)

        business_list = BusinessList()

        try:
            for search_for_index, search_for in enumerate(search_list):
                search_for = search_for.strip()

                try:
                    page.goto("https://www.local.ch/fr")
                    page.get_by_test_id("home-stage-container").get_by_test_id("search-q-input").click()
                    page.get_by_test_id("home-stage-container").get_by_test_id("search-q-input").fill(search_for)
                    page.get_by_test_id("home-stage-container").get_by_test_id("search-q-input").press("Enter")
                    print("Search submitted")
                    page.wait_for_timeout(5000)
                except Exception as e:
                    continue

                while True:
                    listings_count = scrape_page(page, business_list)
                    if listings_count == 0:
                        break  

                    try:
                        next_button = page.get_by_role("button", name="Suivant", exact=True)
                        if next_button.is_enabled():
                            next_button.click()
                            page.wait_for_timeout(5000)
                        else:
                            break  
                    except Exception as e:
                        break

            filename = "local_ch_data"
            business_list.save_to_excel(filename)
            business_list.save_to_csv(filename)

        except Exception as e:
            print(f"An error occurred during scraping: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    main()