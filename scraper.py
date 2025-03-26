#!/usr/bin/env python3
import time
import csv
import os
import random
import requests
import json
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Your CAPTCHA solving service API key
TWOCAPTCHA_API_KEY = "47c255be6d47c6761bd1db4141b5c8a4"

def initialize_driver(headless=False):
    """Set up Chrome WebDriver with anti-detection options."""
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Try multiple methods to initialize Chrome driver
    try:
        print("Trying chromedriver-autoinstaller...")
        # This will automatically download the correct chromedriver for the installed Chrome version
        chromedriver_path = chromedriver_autoinstaller.install()
        print(f"Using chromedriver from: {chromedriver_path}")
        driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
    except Exception as e:
        print(f"chromedriver-autoinstaller failed: {e}")
        
        try:
            print("Trying direct Chrome initialization...")
            driver = webdriver.Chrome(options=options)
        except Exception as e2:
            print(f"Direct initialization failed: {e2}")
            
            # As a last resort, try ChromeDriverManager
            try:
                print("Trying with ChromeDriverManager as last resort...")
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            except Exception as e3:
                print(f"All driver initialization methods failed!")
                print(f"Error details: {e3}")
                raise Exception("Failed to initialize Chrome driver. Please make sure Chrome is installed.")
    
    # Apply anti-detection techniques
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Set reasonable timeouts
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    
    return driver


def get_captcha_image(driver):
    """Extract the CAPTCHA image element and take a screenshot of it."""
    try:
        # Find the CAPTCHA image (based on the screenshot, looks like it's part of a static image)
        # This is an approximate XPath based on the screenshot
        captcha_img_xpath = "//img[contains(@src, 'captcha') or ancestor::div[contains(text(), 'security check')]]"
        
        # If direct image is not found, try to capture the area containing the CAPTCHA
        if not driver.find_elements(By.XPATH, captcha_img_xpath):
            # We'll take a screenshot of the entire page and save it
            driver.save_screenshot("full_page.png")
            print("Saved full page screenshot as full_page.png")
            return "full_page.png"
        
        # If we found the image element, take a screenshot of just that element
        captcha_img = driver.find_element(By.XPATH, captcha_img_xpath)
        
        # Save a screenshot of the entire page
        driver.save_screenshot("captcha_page.png")
        
        # In a real implementation, you would crop the image to just the CAPTCHA portion
        # For simplicity, we'll just return the full page screenshot path
        return "captcha_page.png"
        
    except Exception as e:
        print(f"Error getting CAPTCHA image: {e}")
        driver.save_screenshot("captcha_error.png")
        return "captcha_error.png"


def solve_captcha_with_2captcha_imagetotext(image_path):
    """Solve image-to-text CAPTCHA using 2Captcha service."""
    print("Attempting to solve image CAPTCHA with 2Captcha...")
    
    # Read the image file as base64
    import base64
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Create task
    task_payload = {
        "clientKey": TWOCAPTCHA_API_KEY,
        "task": {
            "type": "ImageToTextTask",
            "body": base64_image,
            "phrase": False,
            "case": True,
            "numeric": 0,
            "math": False,
            "minLength": 1,
            "maxLength": 8
        },
        "languagePool": "en"
    }
    
    response = requests.post(
        "https://api.2captcha.com/createTask",
        json=task_payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to create 2Captcha task: HTTP {response.status_code}, {response.text}")
    
    response_data = response.json()
    if response_data.get("errorId") > 0:
        raise Exception(f"2Captcha error: {response_data.get('errorDescription')}")
    
    task_id = response_data.get("taskId")
    if not task_id:
        raise Exception("No task ID returned from 2Captcha")
        
    print(f"2Captcha task created: {task_id}")
    
    # Wait before first check
    time.sleep(5)
    
    # Get solution
    solution_payload = {
        "clientKey": TWOCAPTCHA_API_KEY,
        "taskId": task_id
    }
    
    max_attempts = 15
    for attempt in range(max_attempts):
        print(f"Checking 2Captcha result (attempt {attempt+1}/{max_attempts})...")
        
        solution_response = requests.post(
            "https://api.2captcha.com/getTaskResult",
            json=solution_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if solution_response.status_code != 200:
            print(f"HTTP error: {solution_response.status_code}")
            time.sleep(3)
            continue
        
        solution_data = solution_response.json()
        if solution_data.get("errorId") > 0:
            raise Exception(f"2Captcha error: {solution_data.get('errorDescription')}")
        
        status = solution_data.get("status")
        print(f"2Captcha task status: {status}")
        
        if status == "ready":
            solution = solution_data.get("solution", {})
            captcha_text = solution.get("text", "")
            
            if captcha_text:
                print(f"2Captcha solved: '{captcha_text}'")
                return captcha_text
            else:
                raise Exception("Empty solution from 2Captcha")
        
        # Wait between checks
        time.sleep(3)
    
    raise Exception("2Captcha solving timed out after maximum attempts")

def solve_image_text_captcha(driver):
    """Solve the text-based image CAPTCHA on the 'You're Almost There' page."""
    print("Attempting to solve text-based image CAPTCHA...")
    
    try:
        # Get the CAPTCHA image
        image_path = get_captcha_image(driver)
        print(f"CAPTCHA image saved to {image_path}")
        
        # Try to solve with 2Captcha
        try:
            print("Attempting to solve with 2Captcha ImageToText...")
            captcha_text = solve_captcha_with_2captcha_imagetotext(image_path)
            print(f"2Captcha returned text: {captcha_text}")
            
            if captcha_text:
                # Find the input field and enter the CAPTCHA text
                captcha_input = driver.find_element(By.XPATH, '//input[@placeholder="I"]')
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                
                # Click the unlock button
                unlock_button = driver.find_element(By.XPATH, '//button[contains(text(), "Unlock")]')
                unlock_button.click()
                
                # Wait for the page to process the CAPTCHA
                time.sleep(3)
                
                # Check if we're still on the CAPTCHA page
                if "You're Almost There" not in driver.page_source:
                    print("CAPTCHA successfully solved with 2Captcha ImageToText!")
                    return True
                else:
                    print("2Captcha solution failed, falling back to manual solving.")
            
        except Exception as e:
            print(f"2Captcha ImageToText failed: {e}")
        
        # Fall back to manual solving
        print("Using manual CAPTCHA solving for text-based CAPTCHA...")
        print("Please enter the text you see in the CAPTCHA image:")
        captcha_text = input()
        
        # Find the input field and enter the CAPTCHA text
        captcha_input = driver.find_element(By.XPATH, '//input[@placeholder="I"]')
        captcha_input.clear()
        captcha_input.send_keys(captcha_text)
        
        # Click the unlock button
        unlock_button = driver.find_element(By.XPATH, '//button[contains(text(), "Unlock")]')
        unlock_button.click()
        
        # Wait for the page to process the CAPTCHA
        time.sleep(3)
        
        # Check if we're still on the CAPTCHA page
        return "You're Almost There" not in driver.page_source
        
    except Exception as e:
        print(f"Error solving text-based CAPTCHA: {e}")
        print("Please solve the CAPTCHA manually in the browser.")
        print("Press Enter when done...")
        input()
        return "You're Almost There" not in driver.page_source

def solve_captcha_with_2captcha(site_key, url):
    """Solve reCAPTCHA using 2Captcha service."""
    print("Trying to solve reCAPTCHA with 2Captcha...")
    
    # Create task
    task_payload = {
        "clientKey": TWOCAPTCHA_API_KEY,
        "task": {
            "type": "RecaptchaV2TaskProxyless",
            "websiteURL": url,
            "websiteKey": site_key
        }
    }
    
    response = requests.post(
        "https://api.2captcha.com/createTask",
        json=task_payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to create 2Captcha task: HTTP {response.status_code}, {response.text}")
    
    response_data = response.json()
    if response_data.get("errorId") > 0:
        raise Exception(f"2Captcha error: {response_data.get('errorDescription')}")
    
    task_id = response_data.get("taskId")
    if not task_id:
        raise Exception("No task ID returned from 2Captcha")
        
    print(f"2Captcha task created: {task_id}")
    
    # Get solution
    solution_payload = {
        "clientKey": TWOCAPTCHA_API_KEY,
        "taskId": task_id
    }
    
    max_attempts = 15
    for attempt in range(max_attempts):
        time.sleep(5)  # 2Captcha typically takes longer for reCAPTCHA v2
        
        solution_response = requests.post(
            "https://api.2captcha.com/getTaskResult",
            json=solution_payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if solution_response.status_code != 200:
            print(f"HTTP error: {solution_response.status_code}")
            continue
        
        solution_data = solution_response.json()
        if solution_data.get("errorId") > 0:
            raise Exception(f"2Captcha error: {solution_data.get('errorDescription')}")
        
        if solution_data.get("status") == "ready":
            return solution_data.get("solution", {}).get("gRecaptchaResponse")
        
        print(f"Waiting for 2Captcha to solve reCAPTCHA... (attempt {attempt+1}/{max_attempts})")
        
    raise Exception("2Captcha reCAPTCHA solving timed out")

def solve_captcha(driver):
    """Detect and solve CAPTCHA using 2Captcha with manual fallback."""
    print("Checking for CAPTCHA...")
    
    # First check if we're on the "You're Almost There" page with text-based CAPTCHA
    if "You're Almost There" in driver.page_source:
        print("'You're Almost There' page detected with text-based CAPTCHA challenge")
        
        # Check for common age verification overlays first
        try:
            age_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "I am over 18") or contains(@class, "age-verification")]'))
            )
            print("Age verification prompt found, clicking...")
            age_button.click()
            time.sleep(1)
        except:
            pass  # No age verification or it has a different structure
        
        # Check if there's a classic reCAPTCHA
        try:
            captcha = driver.find_element(By.CLASS_NAME, "g-recaptcha")
            # Process reCAPTCHA (code from the previous version)
            # This branch is unlikely to be taken based on the screenshots
            print("reCAPTCHA detected, but site actually appears to use text-based CAPTCHA.")
            print("Falling back to text-based CAPTCHA solving...")
            return solve_image_text_captcha(driver)
            
        except NoSuchElementException:
            # If no reCAPTCHA found, try to solve as text-based CAPTCHA
            print("No reCAPTCHA found, attempting to solve text-based CAPTCHA...")
            return solve_image_text_captcha(driver)
        except Exception as e:
            print(f"Error checking for CAPTCHA type: {e}")
            # Fallback to text-based CAPTCHA solving
            return solve_image_text_captcha(driver)
    
    # If not on the "You're Almost There" page, check for regular CAPTCHA
    try:
        # Look for common CAPTCHA indicators
        captcha = driver.find_element(By.CLASS_NAME, "g-recaptcha")  # For reCAPTCHA
        site_key = captcha.get_attribute("data-sitekey")
        url = driver.current_url
        
        # Try 2Captcha
        try:
            print("reCAPTCHA detected, submitting to 2Captcha...")
            solution = solve_captcha_with_2captcha(site_key, url)
            if solution:
                driver.execute_script(f'document.getElementById("g-recaptcha-response").innerHTML="{solution}";')
                # Trigger the callback
                driver.execute_script("___grecaptcha_cfg.clients[0].callback(arguments[0]);", solution)
                print("CAPTCHA solved with 2Captcha!")
                time.sleep(2)  # Wait for form submission
                return True
        except Exception as e:
            print(f"2Captcha failed: {e}")
        
        # Manual fallback
        print("Automated CAPTCHA solving failed. Please solve the CAPTCHA manually in the browser.")
        print("Press Enter when done...")
        input()
        return True
        
    except NoSuchElementException:
        print("No CAPTCHA detected.")
        return True
    except Exception as e:
        print(f"Error checking for CAPTCHA: {e}")
        print("Please solve any CAPTCHA manually in the browser. Press Enter when done...")
        input()
        return True

def handle_age_verification(driver):
    """Handle the age verification prompt."""
    print("Checking for age verification prompt...")
    try:
        # Look for the age verification button (adjust selector as needed based on actual page)
        age_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "I am over 18") or contains(@class, "age-verification")]'))
        )
        print("Age verification prompt found, clicking...")
        age_button.click()
        time.sleep(1)
        return True
    except (TimeoutException, NoSuchElementException):
        print("No age verification prompt detected or it has a different structure.")
        return True
    except Exception as e:
        print(f"Error handling age verification: {e}")
        return False

def load_all_profiles(driver):
    """Scroll search page until all profiles load, handling CAPTCHAs."""
    print("Loading search page...")
    driver.get("https://tryst.link/search?loc=%3AAnywhere&within=50km&trans=false&q=")
    
    # Handle age verification prompt
    handle_age_verification(driver)
    
    # Handle CAPTCHA
    if not solve_captcha(driver):
        print("Failed to bypass CAPTCHA. Results may be incomplete.")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        if not solve_captcha(driver):  # Check CAPTCHA during scrolling
            print("CAPTCHA issue during scrolling. Continuing with partial results.")
            break
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("All profiles loaded.")
            break
        last_height = new_height

def extract_profile_links(driver):
    """Get all unique profile links from the search page."""
    print("Extracting profile links...")
    links = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
    profile_links = set(link.get_attribute("href") for link in links if "/escort/" in link.get_attribute("href"))
    print(f"Found {len(profile_links)} profile links.")
    return profile_links

def load_scraped_urls(filename="scraped_urls.txt"):
    """Load previously scraped URLs to avoid duplicates."""
    return set(line.strip() for line in open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else set()

def save_scraped_url(url, filename="scraped_urls.txt"):
    """Save a scraped URL to the tracking file."""
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

def scrape_profile(driver, url):
    """Scrape a profile, revealing hidden email and collecting data."""
    print(f"Scraping {url}...")
    driver.get(url)
    data = {"url": url, "email": None, "website": None, "onlyfans": None}
    
    try:
        # Reveal and extract email
        show_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//a[@title="Show Email"]'))
        )
        show_button.click()
        email_span = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-unobfuscate-details-target="output"]'))
        )
        WebDriverWait(driver, 10).until(lambda d: "●" not in email_span.text)
        data["email"] = email_span.text.strip()
    except (TimeoutException, NoSuchElementException):
        print("No email found or failed to unobfuscate.")

    try:
        website_link = driver.find_element(By.XPATH, '//a[contains(text(), "Website") or contains(@href, "http") and not(contains(@href, "tryst.link"))]')
        data["website"] = website_link.get_attribute("href")
    except NoSuchElementException:
        pass

    try:
        onlyfans_link = driver.find_element(By.XPATH, '//a[contains(text(), "OnlyFans") or contains(@href, "onlyfans.com")]')
        data["onlyfans"] = onlyfans_link.get_attribute("href")
    except NoSuchElementException:
        pass

    return data

def initialize_csv(filename="profiles.csv"):
    """Set up the CSV file if it doesn't exist."""
    if not os.path.exists(filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Profile URL", "Email", "Website", "OnlyFans"])

def save_to_csv(data, filename="profiles.csv"):
    """Append profile data to the CSV."""
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([data["url"], data["email"], data["website"], data["onlyfans"]])

def main():
    """Run the scraper."""
    driver = initialize_driver(headless=False)  # Non-headless for CAPTCHA visibility
    initialize_csv()
    scraped_urls = load_scraped_urls()
    
    try:
        load_all_profiles(driver)
        profile_links = extract_profile_links(driver)
        
        for url in profile_links:
            if url in scraped_urls:
                print(f"Skipping {url} (already scraped).")
                continue
            try:
                data = scrape_profile(driver, url)
                save_to_csv(data)
                save_scraped_url(url)
                time.sleep(random.uniform(1, 3))  # Random delay to avoid bans
            except Exception as e:
                print(f"Error scraping {url}: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()