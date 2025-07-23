from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import traceback
import pandas as pd
import time

def extract_rates_to_df(html_source, hsn_code):
    soup = BeautifulSoup(html_source, "html.parser")

    # IDs mapped to labels for easier column naming
    rate_ids = {
        "Basic Customs Duty (BCD)": "t_bcd_rate",
        "Social Welfare Surcharge (SWC)": "t_scd_rate",
        "IGST Levy": "t_igst_rate",
        # Add more here if you need further fields, e.g.:
        # "Additional Duty of Customs (ADC)": "t_adc_rate",
    }

    # Explicitly wait for the values to appear (non-empty text)
    data = {}
    for rate_name, span_id in rate_ids.items():
        span = soup.find("span", id=span_id)
        data[rate_name] = span.text.strip() if span and span.text.strip() else None

    data["HSN Code"] = hsn_code
    df = pd.DataFrame([data])
    return df

def wait_for_value(driver, by, element_id, timeout=30):
    """Wait until the element with element_id has non-empty text content."""
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: d.find_element(by, element_id).text.strip() != "")

def scrape_hsn_duty(hsn_code):
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    #chrome_options.add_argument("--headless")  # Uncomment to run headless

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        # 1. Open ICEGATE Import Trade Guide page
        driver.get("https://www.old.icegate.gov.in/Webappl/Trade-Guide-on-Imports")
        
        # 2. Enter HSN code and submit
        input_box = wait.until(EC.presence_of_element_located((By.NAME, "cth")))
        input_box.clear()
        input_box.send_keys(hsn_code)
        driver.find_element(By.ID, "submitbutton").click()

        # 3. Wait for the container after navigation
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#tmptest1")))

        # 4. Find and click the matching row for the exact HSN code, scrolling if needed
        def find_target_row():
            rows = driver.find_elements(By.CSS_SELECTOR, "div.row.rowh")
            for r in rows:
                if r.get_attribute("value") == hsn_code:
                    return r
            return None

        scroll_container = driver.find_element(By.CSS_SELECTOR, "div#tmptest1")
        target_row = find_target_row()
        if not target_row:
            last_height = -1
            for _ in range(15):
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
                time.sleep(1)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                if new_height == last_height:
                    break
                last_height = new_height
                target_row = find_target_row()
                if target_row:
                    break

        if not target_row:
            print(f"HSN code {hsn_code} not found in tariff detail list.")
            return

        driver.execute_script("arguments[0].scrollIntoView(true);", target_row)
        time.sleep(0.3)
        try:
            wait.until(EC.element_to_be_clickable(target_row))
            target_row.click()
        except:
            driver.execute_script("arguments[0].click();", target_row)

        # 5. Wait for AJAX-loaded values to appear after page loads
        for element_id in ["t_bcd_rate", "t_scd_rate", "t_igst_rate"]:
            try:
                wait_for_value(driver, By.ID, element_id, timeout=30)
            except Exception:
                pass  # If not present, skip

        # 6. Extract and present rates in DataFrame
        html_source = driver.page_source
        df_rates = extract_rates_to_df(html_source, hsn_code)
        print('\nExtracted Duty Rates:')
        print(df_rates)

        # Optionally save to CSV
        df_rates.to_csv(f"{hsn_code}_duty_rates.csv", index=False)
        print(f"\nRates saved to {hsn_code}_duty_rates.csv")

    except Exception:
        print("An error occurred:")
        traceback.print_exc()

    finally:
        print("\nScript finished. Browser will stay open for inspection.")
        input("Press Enter to exit and close the browser...")
        driver.quit()

if __name__ == "__main__":
    hsn_code = "73182100"  # Replace with your desired HSN code
    scrape_hsn_duty(hsn_code)
