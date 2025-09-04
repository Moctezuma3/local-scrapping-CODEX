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
    phone_number: str = None


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

def main():
    ########
    # Input 
    ########
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()
    
    search_list = []
    if args.search:
        search_list = [args.search]
    else:
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = [line.strip() for line in file.readlines()]
        if len(search_list) == 0:
            print('Error occurred: You must either pass the -s search argument, or add searches to input.txt')
            sys.exit()

    total = args.total if args.total else 1_000_000
        
    ###########
    # Scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)
        
        for search_for_index, search_for in enumerate(search_list):
            search_for = search_for.strip()
            print(f"-----\n{search_for_index} - {search_for}")

            page.locator('//input[@id="searchboxinput"]').fill(search_for)
            page.wait_for_timeout(3000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            # scrolling
            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')

            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                if count >= total:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                elif count == previously_counted:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                    print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                    break
                else:
                    previously_counted = count
                    print(f"Currently Scraped: {count}")

            business_list = BusinessList()

            # Scraping each listing
            for listing_index, listing in enumerate(listings):
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    business = Business()

                    # Extract business name
                    name_selector = 'h1.DUwDvf.lfPIob'
                    if page.locator(name_selector).count() > 0:
                        business.name = page.locator(name_selector).first.inner_text()
                    else:
                        business.name = ""
                        print(f"Name not found for listing {listing_index}: {listing}")

                    # Extract address
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).first.inner_text()
                    else:
                        business.address = ""

                    # Extract website
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).first.inner_text()
                    else:
                        business.website = ""

                    # Extract phone number
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    if page.locator(phone_number_xpath).count() > 0:
                        business.phone_number = page.locator(phone_number_xpath).first.inner_text()
                    else:
                        business.phone_number = ""

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occurred for listing {listing_index}: {e}')
            
            #########
            # Output
            #########
            filename = f"google_maps_data_{search_for.replace(' ', '_')}"
            business_list.save_to_excel(filename)
            business_list.save_to_csv(filename)

        browser.close()

if __name__ == "__main__":
    main()
