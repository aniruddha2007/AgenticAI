import streamlit as st
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import traceback
import pandas as pd
import time
import openpyxl
import xlwings as xw


def get_usd_to_inr_rate(api_key):
    url = f"http://data.fixer.io/api/latest?access_key={api_key}"
    response = requests.get(url)
    data = response.json()
    if not data.get('success', True):
        raise Exception(f"API Error: {data.get('error', {}).get('info', 'No info')}")
    rates = data.get('rates', {})
    usd_rate = rates.get('USD')
    inr_rate = rates.get('INR')
    if usd_rate is None or inr_rate is None:
        raise Exception("USD or INR rate missing in API response.")
    return round(inr_rate / usd_rate, 4)


def extract_rates_to_df(html_source, hsn_code):
    soup = BeautifulSoup(html_source, "html.parser")
    rate_ids = {
        "Basic Customs Duty (BCD)": "t_bcd_rate",
        "Social Welfare Surcharge (SWC)": "t_scd_rate",
        "IGST Levy": "t_igst_rate",
    }
    data = {}
    for rate_name, span_id in rate_ids.items():
        span = soup.find("span", id=span_id)
        data[rate_name] = span.text.strip() if span and span.text.strip() else None
    data["HSN Code"] = hsn_code
    df = pd.DataFrame([data])
    return df


def wait_for_value(driver, by, element_id, timeout=30):
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: d.find_element(by, element_id).text.strip() != "")


def read_total_from_excel(file_path):
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    total = ws["C20"].value
    return total

def read_total_from_excel_with_calc(file_path):
    app = xw.App(visible=False)
    wb = app.books.open(file_path)
    wb.app.api.CalculateFullRebuild()  # Force full recalculation
    total = wb.sheets[0].range("C20").value
    wb.save()
    wb.close()
    app.quit()
    return total


def create_new_excel(
    template_path, output_path,
    hsn_code,
    usd_inr, bcd, swc, igst,
    c4_val, b5_val
):
    wb = openpyxl.load_workbook(template_path)
    ws = wb.active
    ws["C1"] = usd_inr
    ws["B10"] = bcd + "%"
    ws["B11"] = swc + "%"
    ws["B13"] = igst + "%"
    ws["C4"] = c4_val
    ws["B5"] = b5_val
    wb.save(output_path)
    return output_path


def scrape_hsn_duty(hsn_code, c4_value, b5_value, usd_to_inr_rate, input_excel_path):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Use new headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")  # Helps with headless stability
    chrome_options.add_argument("--window-size=1920,1080")  # Set window size for headless
    chrome_options.add_argument("--disable-web-security")   # Helps with some blocking issues
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get("https://www.old.icegate.gov.in/Webappl/Trade-Guide-on-Imports")
        
        # Wait for page to load completely
        time.sleep(2)
        
        input_box = wait.until(EC.presence_of_element_located((By.NAME, "cth")))
        input_box.clear()
        input_box.send_keys(hsn_code)
        
        # Improved button click handling for headless mode
        button = wait.until(EC.element_to_be_clickable((By.ID, "submitbutton")))
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        time.sleep(0.5)
        
        try:
            button.click()
        except Exception:
            # Use JavaScript click as fallback
            driver.execute_script("arguments[0].click();", button)
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#tmptest1")))

        def find_target_row():
            divs = driver.find_elements(By.CSS_SELECTOR, "div.row.rowh")
            for d in divs:
                if d.get_attribute("value") == hsn_code:
                    return d
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
            st.error(f"HSN code {hsn_code} not found in tariff detail list.")
            return None
            
        driver.execute_script("arguments[0].scrollIntoView(true);", target_row)
        time.sleep(0.5)  # Increased wait time for headless
        
        try:
            wait.until(EC.element_to_be_clickable(target_row))
            target_row.click()
        except:
            driver.execute_script("arguments[0].click();", target_row)

        # Wait longer for AJAX content to load in headless mode
        for eid in ["t_bcd_rate", "t_scd_rate", "t_igst_rate"]:
            try:
                wait_for_value(driver, By.ID, eid, 30)
            except:
                pass

        # Additional wait to ensure all content is loaded
        time.sleep(2)
        
        html_source = driver.page_source
        df_rates = extract_rates_to_df(html_source, hsn_code)
        driver.quit()
        return df_rates

    except Exception as e:
        driver.quit()
        st.error(f"An error occurred: {e}")
        st.error(traceback.format_exc())
        return None


def main():
    st.title("HSN Duty Rates & Calculator")

    hsn_code = st.text_input("Enter HSN Code:", "73182100")
    c4_input = st.number_input("Value for Cell C4:", value=1228.0)
    b5_input = st.number_input("Value for Cell B5:", value=0.095)
    api_key = st.text_input("Enter Fixer.io API Key (leave blank to enter USD/INR manually):", "")

    usd_inr_input = None
    if api_key:
        st.write("Fetching USD to INR rate from Fixer API...")
        try:
            usd_inr_input = get_usd_to_inr_rate(f"http://data.fixer.io/api/latest?access_key={api_key}")
            st.write(f"USD to INR rate fetched: {usd_inr_input}")
        except Exception as e:
            st.error(f"Error fetching exchange rate: {e}")
    else:
        usd_inr_input = st.number_input("Enter USD to INR rate manually:", value=82.75)
    usd_inr_input += 1.5
    # Use your fixed Excel path here
    template_excel_path = "D:\\Github\\AgenticAI\\LangChain\\HSN\\data\\Import Calculator With GST revised with BCD.xlsx"

    if st.button("Start Scraping and Calculate Total"):
        if not hsn_code:
            st.error("Please enter HSN code.")
            return

        df_rates = scrape_hsn_duty(hsn_code, c4_input, b5_input, usd_inr_input, template_excel_path)
        if df_rates is not None:
            st.write("Extracted Duty Rates:")
            st.dataframe(df_rates)

            bcd_val = df_rates.at[0, "Basic Customs Duty (BCD)"]
            swc_val = df_rates.at[0, "Social Welfare Surcharge (SWC)"]
            igst_val = df_rates.at[0, "IGST Levy"]

            output_file = f"D:\\Github\\AgenticAI\\LangChain\\HSN\\data\\HSN_OUTPUT_FILES\\HSN_{hsn_code}.xlsx"
            create_new_excel(
                template_excel_path,
                output_file,
                hsn_code,
                usd_inr_input,
                bcd_val,
                swc_val,
                igst_val,
                c4_input,
                b5_input
            )
            st.success(f"Updated Excel saved: {output_file}")

            # Read total from saved Excel C20 and display
            total = read_total_from_excel_with_calc(output_file)
            st.success(f"Total : {total}")

if __name__ == "__main__":
    main()
