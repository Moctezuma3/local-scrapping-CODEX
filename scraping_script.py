from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://moteur.pylote.io/?q=dev%20back&f=%5B%5D")

    # Attendre que la page soit complètement chargée
    page.wait_for_load_state('networkidle')

    # Extraire et imprimer le contenu des éléments <p> et des liens 'mailto'
    try:
        # Paragraphs
        paragraphs = page.query_selector_all('p.MuiTypography-root')
        for paragraph in paragraphs:
            text_content = paragraph.text_content()
            print(f"Paragraph content: {text_content}")

        # Extracting hidden elements, if any
        hidden_elements = page.query_selector_all("[style*='display: none']")
        for element in hidden_elements:
            hidden_text = element.text_content()
            if hidden_text:
                print(f"Hidden element content: {hidden_text}")

        # Mailto links
        links = page.query_selector_all('a')
        for link in links:
            href = link.get_attribute('href')
            if href and 'mailto:' in href:
                print(f"Mailto link: {href}")

    except Exception as e:
        print(f"An error occurred: {e}")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

