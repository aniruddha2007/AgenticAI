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
import io
from PIL import Image
import openpyxl

# Constants
DEFAULT_HSN_CODE = "73182100"
DEFAULT_FOB_PRICE = 350.0
DEFAULT_FREIGHT_INSURANCE_PERCENTAGE = 6.0
DEFAULT_USD_INR_RATE = 75.5
USD_INR_BUFFER = 1.5
SCRAPING_URL = "https://www.old.icegate.gov.in/Webappl/Trade-Guide-on-Imports"

def get_usd_to_inr_rate(api_key):
    """Fetch USD to INR exchange rate from Fixer.io API"""
    url = f"http://data.fixer.io/api/latest?access_key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success', True):
            raise Exception(f"API Error: {data.get('error', {}).get('info', 'No info')}")
        
        rates = data.get('rates', {})
        usd_rate = rates.get('USD')
        inr_rate = rates.get('INR')
        
        if usd_rate is None or inr_rate is None:
            raise Exception("USD or INR rate missing in API response.")
        
        return round(inr_rate / usd_rate, 4)
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")

def calculate_import_cost(fob_price_usd, freight_insurance_percentage, usd_inr_rate, bcd_rate, swc_rate, igst_rate):
    """
    Calculate complete import cost based on the Excel template formulas
    Replicates the exact logic from PAKO's import calculator Excel template
    """
    
    # Step 1: Calculate Freight & Insurance
    freight_insurance_amount = fob_price_usd * (freight_insurance_percentage / 100)
    
    # Step 2: Calculate CIF Value
    cif_value_usd = fob_price_usd + freight_insurance_amount
    
    # Step 3: Calculate Assessable Value (CIF + 1%)
    assessable_addition_percentage = 0.01  # 1%
    assessable_addition_amount = cif_value_usd * assessable_addition_percentage
    assessable_value_usd = cif_value_usd + assessable_addition_amount
    
    # Step 4: Convert to INR (A)
    assessable_value_inr = assessable_value_usd * usd_inr_rate
    
    # Step 5: Calculate BCD (Basic Customs Duty) (B)
    bcd_amount = assessable_value_inr * (float(bcd_rate) / 100)
    
    # Step 6: Calculate Social Welfare Surcharge (SWC) (i)
    swc_amount = bcd_amount * (float(swc_rate) / 100)
    
    # Step 7: Calculate Subtotal (A + B + i)
    subtotal_before_igst = assessable_value_inr + bcd_amount + swc_amount
    
    # Step 8: Calculate IGST (C)
    igst_amount = subtotal_before_igst * (float(igst_rate) / 100)
    
    # Step 9: Calculate Sub Total of Duties (B + i + C)
    total_duties = bcd_amount + swc_amount + igst_amount
    
    # Step 10: Calculate Total Price
    total_price = assessable_value_inr + total_duties
    
    # Step 11: Calculate Clearance/Transportation (5%)
    clearance_transportation_percentage = 0.05  # 5%
    clearance_transportation = total_price * clearance_transportation_percentage
    
    # Step 12: Calculate Landed Price at Factory
    landed_price = total_price + clearance_transportation
    
    # Step 13: Calculate Final Breakdown (for GST compliance)
    igst_component_final = landed_price - (landed_price / (1 + (igst_amount / subtotal_before_igst)))
    basic_price_less_igst_accurate = landed_price - igst_component_final
    
    return {
        'fob_price_usd': fob_price_usd,
        'freight_insurance_percentage': freight_insurance_percentage,
        'freight_insurance_amount': freight_insurance_amount,
        'cif_value_usd': cif_value_usd,
        'assessable_addition_percentage': assessable_addition_percentage * 100,
        'assessable_addition_amount': assessable_addition_amount,
        'assessable_value_usd': assessable_value_usd,
        'assessable_value_inr': assessable_value_inr,
        'bcd_rate': bcd_rate,
        'bcd_amount': bcd_amount,
        'swc_rate': swc_rate,
        'swc_amount': swc_amount,
        'subtotal_before_igst': subtotal_before_igst,
        'igst_rate': igst_rate,
        'igst_amount': igst_amount,
        'total_duties': total_duties,
        'total_price': total_price,
        'clearance_transportation_percentage': clearance_transportation_percentage * 100,
        'clearance_transportation': clearance_transportation,
        'landed_price': landed_price,
        'basic_price_less_igst': basic_price_less_igst_accurate,
        'igst_component_final': igst_component_final,
        'usd_inr_rate': usd_inr_rate
    }

def extract_rates_to_df(html_source, hsn_code):
    """Extract duty rates from HTML and return as DataFrame"""
    soup = BeautifulSoup(html_source, "html.parser")
    rate_mapping = {
        "Basic Customs Duty (BCD)": "t_bcd_rate",
        "Social Welfare Surcharge (SWC)": "t_scd_rate",
        "IGST Levy": "t_igst_rate",
    }
    
    data = {"HSN Code": hsn_code}
    for rate_name, span_id in rate_mapping.items():
        span = soup.find("span", id=span_id)
        data[rate_name] = span.text.strip() if span and span.text.strip() else "0"
    
    return pd.DataFrame([data])

def wait_for_value(driver, by, element_id, timeout=30):
    """Wait for element to have non-empty text content"""
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: d.find_element(by, element_id).text.strip() != "")

def setup_chrome_driver():
    """Configure and return Chrome WebDriver with optimized options"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    return webdriver.Chrome(options=chrome_options)

def find_hsn_row(driver, hsn_code, max_scrolls=15):
    """Find and return the target HSN row element"""
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
        for _ in range(max_scrolls):
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
            time.sleep(1)
            new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
            if new_height == last_height:
                break
            last_height = new_height
            target_row = find_target_row()
            if target_row:
                break
    
    return target_row

def scrape_hsn_duty(hsn_code):
    """Main scraping function to extract HSN duty rates"""
    driver = setup_chrome_driver()
    wait = WebDriverWait(driver, 25)

    try:
        driver.get(SCRAPING_URL)
        time.sleep(2)
        
        input_box = wait.until(EC.presence_of_element_located((By.NAME, "cth")))
        input_box.clear()
        input_box.send_keys(hsn_code)
        
        button = wait.until(EC.element_to_be_clickable((By.ID, "submitbutton")))
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        time.sleep(0.5)
        
        try:
            button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", button)
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#tmptest1")))

        target_row = find_hsn_row(driver, hsn_code)
        
        if not target_row:
            st.error(f"HSN code {hsn_code} not found in tariff detail list.")
            return None
            
        driver.execute_script("arguments[0].scrollIntoView(true);", target_row)
        time.sleep(0.5)
        
        try:
            wait.until(EC.element_to_be_clickable(target_row))
            target_row.click()
        except:
            driver.execute_script("arguments[0].click();", target_row)

        rate_elements = ["t_bcd_rate", "t_scd_rate", "t_igst_rate"]
        for element_id in rate_elements:
            try:
                wait_for_value(driver, By.ID, element_id, 30)
            except:
                pass

        time.sleep(2)
        
        html_source = driver.page_source
        df_rates = extract_rates_to_df(html_source, hsn_code)
        
        return df_rates

    except Exception as e:
        st.error(f"An error occurred during scraping: {e}")
        st.error(traceback.format_exc())
        return None
    finally:
        driver.quit()

def create_excel_download(calc_results, hsn_code):
    """Create Excel file for download with comprehensive data"""
    
    # Create summary data
    summary_data = {
        'Parameter': [
            'FOB Price (USD)',
            'Freight & Insurance Amount',
            'CIF Value (USD)', 
            'Assessable Addition (1%)',
            'Assessable Value (USD)',
            'Assessable Value (INR)',
            f'BCD ({calc_results["bcd_rate"]}%)',
            f'Social Welfare Surcharge ({calc_results["swc_rate"]}%)',
            'Subtotal (before IGST)',
            f'IGST ({calc_results["igst_rate"]}%)',
            'Total Duties',
            'Total Price',
            'Clearance/Transportation (5%)',
            'LANDED PRICE AT FACTORY',
            'Basic Price (less IGST)',
            'IGST Component'
        ],
        'Value (Numeric)': [
            calc_results['fob_price_usd'],
            calc_results['freight_insurance_amount'],
            calc_results['cif_value_usd'],
            calc_results['assessable_addition_amount'],
            calc_results['assessable_value_usd'],
            calc_results['assessable_value_inr'],
            calc_results['bcd_amount'],
            calc_results['swc_amount'],
            calc_results['subtotal_before_igst'],
            calc_results['igst_amount'],
            calc_results['total_duties'],
            calc_results['total_price'],
            calc_results['clearance_transportation'],
            calc_results['landed_price'],
            calc_results['basic_price_less_igst'],
            calc_results['igst_component_final']
        ],
        'Value (Formatted)': [
            f"${calc_results['fob_price_usd']:,.2f}",
            f"${calc_results['freight_insurance_amount']:,.2f}",
            f"${calc_results['cif_value_usd']:,.2f}",
            f"${calc_results['assessable_addition_amount']:,.2f}",
            f"${calc_results['assessable_value_usd']:,.2f}",
            f"₹{calc_results['assessable_value_inr']:,.2f}",
            f"₹{calc_results['bcd_amount']:,.2f}",
            f"₹{calc_results['swc_amount']:,.2f}",
            f"₹{calc_results['subtotal_before_igst']:,.2f}",
            f"₹{calc_results['igst_amount']:,.2f}",
            f"₹{calc_results['total_duties']:,.2f}",
            f"₹{calc_results['total_price']:,.2f}",
            f"₹{calc_results['clearance_transportation']:,.2f}",
            f"₹{calc_results['landed_price']:,.2f}",
            f"₹{calc_results['basic_price_less_igst']:,.2f}",
            f"₹{calc_results['igst_component_final']:,.2f}"
        ]
    }
    
    # Create metadata
    metadata = {
        'Report Information': [
            'Company',
            'Report Type', 
            'HSN Code',
            'Generated Date',
            'Generated Time',
            'Exchange Rate Used',
            'Buffer Applied',
            'Final Exchange Rate'
        ],
        'Value': [
            'PAKO India',
            'Import Cost Calculator',
            hsn_code,
            pd.Timestamp.now().strftime('%Y-%m-%d'),
            pd.Timestamp.now().strftime('%H:%M:%S'),
            f"₹{calc_results['usd_inr_rate'] - USD_INR_BUFFER:.4f}",
            f"₹{USD_INR_BUFFER}",
            f"₹{calc_results['usd_inr_rate']:.4f}"
        ]
    }
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main calculation sheet
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Import Calculation', index=False)
        
        # Metadata sheet
        pd.DataFrame(metadata).to_excel(writer, sheet_name='Report Information', index=False)
        
        # Format the Excel file
        workbook = writer.book
        worksheet = workbook['Import Calculation']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return output.getvalue()

def display_calculation_results(calc_results, hsn_code):
    """Display all calculation results in organized sections"""
    
    st.markdown("---")
    st.subheader("Complete Import Cost Calculation")
    
    # Exchange Rate Info
    st.markdown("### Exchange Rate Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Base USD/INR Rate", f"₹{calc_results['usd_inr_rate'] - USD_INR_BUFFER:.4f}")
    with col2:
        st.metric("Buffer Applied", f"₹{USD_INR_BUFFER}")
    with col3:
        st.metric("Final Rate Used", f"₹{calc_results['usd_inr_rate']:.2f}")
    
    # Basic Calculations
    st.markdown("### Basic Price Calculations")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("FOB Price (USD)", f"${calc_results['fob_price_usd']:,.2f}")
    with col2:
        st.metric(f"Freight & Insurance ({calc_results['freight_insurance_percentage']}%)", f"${calc_results['freight_insurance_amount']:,.2f}")
    with col3:
        st.metric("CIF Value (USD)", f"${calc_results['cif_value_usd']:,.2f}")
    
    # Assessable Value
    st.markdown("### Assessable Value Calculation")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"Assessable Addition ({calc_results['assessable_addition_percentage']}%)", f"${calc_results['assessable_addition_amount']:,.2f}")
    with col2:
        st.metric("Assessable Value (USD)", f"${calc_results['assessable_value_usd']:,.2f}")
    
    # INR Conversion
    st.metric("Assessable Value (INR) - Component A", f"₹{calc_results['assessable_value_inr']:,.2f}")
    
    # Duties Calculation
    st.markdown("### Customs Duties & Charges")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"Basic Customs Duty ({calc_results['bcd_rate']}%) - Component B", f"₹{calc_results['bcd_amount']:,.2f}")
    with col2:
        st.metric(f"Social Welfare Surcharge ({calc_results['swc_rate']}%) - Component i", f"₹{calc_results['swc_amount']:,.2f}")
    with col3:
        st.metric("Subtotal (A+B+i)", f"₹{calc_results['subtotal_before_igst']:,.2f}")
    
    # IGST Calculation
    st.markdown("### IGST Calculation")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"IGST ({calc_results['igst_rate']}%) - Component C", f"₹{calc_results['igst_amount']:,.2f}")
    with col2:
        st.metric("Total Duties (B+i+C) - Component D", f"₹{calc_results['total_duties']:,.2f}")
    
    # Total Price
    st.markdown("### Price Calculations")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Price", f"₹{calc_results['total_price']:,.2f}")
    with col2:
        st.metric(f"Clearance/Transportation ({calc_results['clearance_transportation_percentage']}%)", f"₹{calc_results['clearance_transportation']:,.2f}")
    
    # Final Results
    st.markdown("### Final Results")
    st.success(f"**LANDED PRICE AT FACTORY: ₹{calc_results['landed_price']:,.2f}**")
    st.info("This is the base price to be considered for further calculations")
    
    # GST Breakdown
    st.markdown("### GST Compliance Breakdown")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Basic Price (less IGST)", f"₹{calc_results['basic_price_less_igst']:,.2f}")
    with col2:
        st.metric("IGST Component", f"₹{calc_results['igst_component_final']:,.2f}")
    with col3:
        st.metric("Total Verification", f"₹{calc_results['landed_price']:,.2f}")
    
    # Download options
    st.markdown("### Download Report")
    col1, col2 = st.columns(2)
    
    # Create summary data for CSV
    summary_data = {
        'Step': [
            '1. FOB Price (USD)',
            '2. Freight & Insurance',
            '3. CIF Value (USD)', 
            '4. Assessable Addition (1%)',
            '5. Assessable Value (USD)',
            '6. Assessable Value (INR)',
            f'7. BCD ({calc_results["bcd_rate"]}%)',
            f'8. Social Welfare Surcharge ({calc_results["swc_rate"]}%)',
            '9. Subtotal (before IGST)',
            f'10. IGST ({calc_results["igst_rate"]}%)',
            '11. Total Duties',
            '12. Total Price',
            '13. Clearance/Transportation (5%)',
            '14. LANDED PRICE AT FACTORY',
            '15. Basic Price (less IGST)',
            '16. IGST Component'
        ],
        'Value': [
            f"${calc_results['fob_price_usd']:,.2f}",
            f"${calc_results['freight_insurance_amount']:,.2f}",
            f"${calc_results['cif_value_usd']:,.2f}",
            f"${calc_results['assessable_addition_amount']:,.2f}",
            f"${calc_results['assessable_value_usd']:,.2f}",
            f"₹{calc_results['assessable_value_inr']:,.2f}",
            f"₹{calc_results['bcd_amount']:,.2f}",
            f"₹{calc_results['swc_amount']:,.2f}",
            f"₹{calc_results['subtotal_before_igst']:,.2f}",
            f"₹{calc_results['igst_amount']:,.2f}",
            f"₹{calc_results['total_duties']:,.2f}",
            f"₹{calc_results['total_price']:,.2f}",
            f"₹{calc_results['clearance_transportation']:,.2f}",
            f"₹{calc_results['landed_price']:,.2f}",
            f"₹{calc_results['basic_price_less_igst']:,.2f}",
            f"₹{calc_results['igst_component_final']:,.2f}"
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    
    with col1:
        csv_data = summary_df.to_csv(index=False)
        st.download_button(
            label="Download CSV Report",
            data=csv_data,
            file_name=f"pako_import_calculation_{hsn_code}_{int(time.time())}.csv",
            mime="text/csv"
        )
    
    with col2:
        excel_data = create_excel_download(calc_results, hsn_code)
        st.download_button(
            label="Download Excel Report",
            data=excel_data,
            file_name=f"pako_import_calculation_{hsn_code}_{int(time.time())}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def main():
    # Page configuration
    st.set_page_config(
        page_title="PAKO Import Calculator",
        page_icon="⚙️",
        layout="wide"
    )
    
    # Custom CSS for professional styling
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        margin: -1rem -1rem 2rem -1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric {
        background: #f8f9fa;
        padding: 0.8rem;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    .metric-highlight {
        background: #e8f4f8;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2a5298;
    }
    .footer {
        text-align: center;
        padding: 2rem;
        background: #f8f9fa;
        margin: 2rem -1rem -1rem -1rem;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header section
    col1, col2 = st.columns([1, 5])
    with col1:
        try:
            st.image("/Pako India Logo.png", width=120)
        except Exception:
            st.markdown("**PAKO**")
    
    with col2:
        st.markdown("""
        <div class="main-header">
            <h1>PAKO INTERNAL IMPORT CALCULATOR</h1>
            <p>Import Cost Analysis & Duty Calculation System</p>
        </div>
        """, unsafe_allow_html=True)

    # Input Section
    st.markdown("## Input Parameters")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Product Information")
        hsn_code = st.text_input("HSN Code:", value=DEFAULT_HSN_CODE)
        fob_price = st.number_input("Basic Price per Piece (USD FOB):", value=DEFAULT_FOB_PRICE, format="%.2f", min_value=0.01)
        freight_percentage = st.number_input("Freight & Insurance Percentage:", value=DEFAULT_FREIGHT_INSURANCE_PERCENTAGE, format="%.2f", min_value=0.0, max_value=100.0)
    
    with col2:
        st.markdown("### Exchange Rate Configuration")
        api_key = st.text_input("Fixer.io API Key (Optional):", type="password", help="Leave blank to enter rate manually")
        
        if api_key and st.button("Fetch Current Exchange Rate"):
            try:
                with st.spinner("Fetching live exchange rate..."):
                    fetched_rate = get_usd_to_inr_rate(api_key)
                    st.session_state.usd_inr_rate = fetched_rate
                    st.success(f"Live rate fetched: {fetched_rate}")
            except Exception as e:
                st.error(f"Error fetching rate: {e}")
        
        usd_inr_input = st.number_input(
            "USD to INR Rate:", 
            value=st.session_state.get('usd_inr_rate', DEFAULT_USD_INR_RATE),
            format="%.4f",
            min_value=1.0
        )

    # Buffer information
    final_rate = usd_inr_input + USD_INR_BUFFER
    st.info(f"**Final Exchange Rate:** ₹{final_rate:.2f} (includes ₹{USD_INR_BUFFER} company buffer)")

    # Main calculation button
    if st.button("CALCULATE IMPORT COST", type="primary", use_container_width=True):
        if not hsn_code:
            st.error("Please enter a valid HSN code.")
            return

        # Step 1: Fetch duty rates
        with st.spinner("Fetching current duty rates from government database..."):
            df_rates = scrape_hsn_duty(hsn_code)
            
        if df_rates is not None:
            st.success("Current duty rates successfully retrieved")
            
            # Display duty rates
            st.markdown("## Current Government Duty Rates")
            st.dataframe(df_rates, use_container_width=True)

            # Process duty rates
            bcd_val = df_rates.at[0, "Basic Customs Duty (BCD)"].replace('%', '').strip() if df_rates.at[0, "Basic Customs Duty (BCD)"] else "0"
            swc_val = df_rates.at[0, "Social Welfare Surcharge (SWC)"].replace('%', '').strip() if df_rates.at[0, "Social Welfare Surcharge (SWC)"] else "10"
            igst_val = df_rates.at[0, "IGST Levy"].replace('%', '').strip() if df_rates.at[0, "IGST Levy"] else "12"

            # Validate and convert rates
            try:
                bcd_val = float(bcd_val) if bcd_val else 0.0
                swc_val = float(swc_val) if swc_val else 10.0
                igst_val = float(igst_val) if igst_val else 12.0
            except ValueError:
                st.warning("Some duty rates could not be parsed. Default values applied.")
                bcd_val = 0.0
                swc_val = 10.0  
                igst_val = 12.0

            # Step 2: Calculate import cost
            with st.spinner("Performing import cost calculations..."):
                calc_results = calculate_import_cost(
                    fob_price,
                    freight_percentage,
                    final_rate,
                    bcd_val,
                    swc_val,
                    igst_val
                )
            
            # Step 3: Display results
            display_calculation_results(calc_results, hsn_code)

    # Company Guidelines
    with st.expander("PAKO Company Guidelines"):
        st.markdown("""
        **Import Calculation Guidelines:**
        
        1. **Exchange Rate Buffer:** A buffer of ₹1.50 is automatically applied to all exchange rates
        2. **Duty Rates:** All accessories, cables, power supplies, and cameras attract 15% basic duty
        3. **Freight Calculation:** Consult with senior management for freight calculations on:
           - Low-value products
           - Project-based imports
        4. **Base Price:** Use the Landed Price at Factory as the base for all further calculations
        5. **Rate Monitoring:** Monitor USD fluctuation regularly for accurate pricing
        """)

    # Technical Information
    with st.expander("System Information"):
        st.markdown("""
        **Technical Details:**
        
        - **Data Source:** Live duty rates from Indian Customs (ICEGate)
        - **Calculation Method:** Replicates PAKO Excel template formulas exactly
        - **Compliance:** GST-compliant breakdown provided
        - **Export Options:** CSV and Excel formats available
        - **Update Frequency:** Real-time duty rate fetching
        """)
    
    # Footer
    st.markdown("""
    <div class="footer">
        <p><strong>PAKO Technologies Private Limited</strong><br>
        Internal Import Cost Calculator | For Authorized Personnel Only<br>
        All calculations are based on current government regulations and company policies<br>
                www.pakoindia.com</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    # Initialize session state
    if 'usd_inr_rate' not in st.session_state:
        st.session_state.usd_inr_rate = DEFAULT_USD_INR_RATE
    
    main()
