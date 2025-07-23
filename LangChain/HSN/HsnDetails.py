from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


def fetch_tariff_details(hsn_code: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Go to ICEGATE import guide
        page.goto("https://www.old.icegate.gov.in/Webappl/Trade-Guide-on-Imports")

        # Step 2: Fill the HSN code
        page.fill("input[name='tariff']", hsn_code)
        page.click("input[type='submit']")

        # Step 3: Wait for the redirection
        page.wait_for_url("**/Structure-of-Duty-for-selected-Tariff")

        # Step 4: Scrape the duty structure
        content = page.content()
        soup = BeautifulSoup(content, "lxml")

        def extract_value(label_text):
            label = soup.find("td", string=lambda s: s and label_text in s)
            if label:
                value_td = label.find_next_sibling("td")
                return value_td.text.strip() if value_td else "Not found"
            return "Not found"

        results = {
            "HSN Code": hsn_code,
            "Basic Customs Duty (BCD)": extract_value("Basic Customs Duty"),
            "Social Welfare Surcharge (SWC)": extract_value("Social Welfare Surcharge"),
            "IGST Levy": extract_value("IGST")
        }

        browser.close()
        return results


if __name__ == "__main__":
    hsn_code = "84099949"  # Example: HSN for vehicles
    details = fetch_tariff_details(hsn_code)
    for key, value in details.items():
        print(f"{key}: {value}")
