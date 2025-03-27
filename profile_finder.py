#!/usr/bin/env python3
"""
Profile Finder for Tryst.link

This script finds all profile URLs from the search page and saves them to a file.
It handles CAPTCHAs and age verification prompts.
"""

import time
import os
import random
import requests
import json
import base64
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

def initialize_driver(headless=False, prevent_focus=True):
    """Set up Chrome WebDriver with anti-detection options."""
    options = Options()
    
    # Check if we should use visible mode
    if not prevent_focus:
        # Fully visible mode
        print("Using FULLY VISIBLE browser mode - window will be visible")
        # Set window size for better visibility
        options.add_argument("--window-size=1600,1200")
        options.add_argument("--start-maximized")
    # For macOS, the most effective way to prevent focus stealing is to use a special
    # variant of headless mode that still renders pages but doesn't have a window
    elif prevent_focus:
        # This is a headless mode that renders properly but doesn't steal focus
        options.add_argument("--headless=new")
        # These ensure proper rendering in headless mode
        options.add_argument("--window-size=1920,1080")  
        options.add_argument("--disable-gpu")
        options.add_argument("--enable-javascript")
        # Let the user know we're using "enhanced visibility headless" mode
        print("Using enhanced visibility headless mode (pages render but won't steal focus)")
    elif headless:
        # Traditional headless mode if specifically requested
        options.add_argument("--headless")
    
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Disable various prompts and popups that could steal focus
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,  # Block notifications
        "credentials_enable_service": False,  # Disable password manager
        "profile.password_manager_enabled": False  # Disable password manager
    })
    
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
    """Extract the CAPTCHA image and take a screenshot of it."""
    try:
        # Find the CAPTCHA image (based on the screenshot, it's displayed inline)
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
    
    try:
        # Read the image file as base64
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Debug image size
            image_size_kb = len(image_data) / 1024
            print(f"Image size for 2Captcha: {image_size_kb:.2f} KB")
        
        # Create task with 2Captcha specific parameters
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
        
        # Create the task
        print("Creating 2Captcha task...")
        response = requests.post(
            "https://api.2captcha.com/createTask",
            json=task_payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        # Check HTTP status
        if response.status_code != 200:
            print(f"Failed to create 2Captcha task: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        # Parse response data
        try:
            response_data = response.json()
            print(f"2Captcha response: {response_data}")
        except Exception as e:
            print(f"Error parsing 2Captcha response JSON: {e}")
            print(f"Raw response: {response.text}")
            return None
        
        # Check for API errors
        if response_data.get("errorId") > 0:
            print(f"2Captcha error: {response_data.get('errorDescription')}")
            return None
        
        # Get task ID
        task_id = response_data.get("taskId")
        if not task_id:
            print("No task ID returned from 2Captcha")
            return None
            
        print(f"2Captcha task created: {task_id}")
        
        # Wait before first check (2Captcha typically needs 5-10 seconds)
        time.sleep(5)
        
        # Get solution
        solution_payload = {
            "clientKey": TWOCAPTCHA_API_KEY,
            "taskId": task_id
        }
        
        max_attempts = 15
        for attempt in range(max_attempts):
            print(f"Checking 2Captcha result (attempt {attempt+1}/{max_attempts})...")
            
            try:
                solution_response = requests.post(
                    "https://api.2captcha.com/getTaskResult",
                    json=solution_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                # Check HTTP status
                if solution_response.status_code != 200:
                    print(f"HTTP error: {solution_response.status_code}")
                    print(f"Response: {solution_response.text}")
                    time.sleep(3)
                    continue
                
                # Parse response
                try:
                    solution_data = solution_response.json()
                    print(f"2Captcha result data: {solution_data}")
                except Exception as e:
                    print(f"Error parsing 2Captcha result JSON: {e}")
                    print(f"Raw response: {solution_response.text}")
                    time.sleep(3)
                    continue
                
                # Check for errors
                if solution_data.get("errorId") > 0:
                    print(f"2Captcha error: {solution_data.get('errorDescription')}")
                    return None
                
                # Check status
                status = solution_data.get("status")
                print(f"2Captcha task status: {status}")
                
                if status == "ready":
                    # Get the solution
                    solution = solution_data.get("solution", {})
                    captcha_text = solution.get("text", "")
                    
                    if captcha_text:
                        print(f"2Captcha solved: '{captcha_text}'")
                        return captcha_text
                    else:
                        print("Empty solution from 2Captcha")
                        return None
                
                # Wait between checks
                time.sleep(3)
                
            except Exception as e:
                print(f"Error checking 2Captcha result: {e}")
                time.sleep(3)
        
        print("2Captcha solving timed out after maximum attempts")
        return None
        
    except Exception as e:
        print(f"Error in 2Captcha process: {e}")
        import traceback
        traceback.print_exc()
        return None

def solve_image_text_captcha(driver):
    """Solve the text-based image CAPTCHA on the 'You're Almost There' page using 2Captcha."""
    print("Attempting to solve text-based image CAPTCHA...")
    
    # Take a simple screenshot of the page
    captcha_image_path = "captcha_page.png"
    driver.save_screenshot(captcha_image_path)
    print("Screenshot saved for CAPTCHA processing")
    
    # Flag to track if 2Captcha was successful
    automated_success = False
    captcha_text = None
    
    # Try 2Captcha for text recognition
    print("Using 2Captcha for text recognition...")
    try:
        captcha_text = solve_captcha_with_2captcha_imagetotext(captcha_image_path)
        if captcha_text:
            print(f"2Captcha returned text: {captcha_text}")
            automated_success = True
        else:
            print("2Captcha returned empty result")
    except Exception as e:
        print(f"2Captcha failed: {e}")
    
    # If 2Captcha failed, return false
    if not automated_success:
        print("Automated CAPTCHA service failed.")
        return False
    
    # Now find the input field for the CAPTCHA text
    try:
        # Find the input field using direct selector (from your example)
        input_field = driver.find_element(By.XPATH, '//input[@type="text" and @name="response"]')
        print("Found input field using exact selector")
    except:
        # If that fails, try a more general approach
        try:
            input_field = driver.find_element(By.NAME, "response")
            print("Found input field by name='response'")
        except:
            try:
                # Try any input field
                inputs = driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    if inp.is_displayed() and inp.get_attribute("type") in ["text", ""]:
                        input_field = inp
                        print("Found text input field")
                        break
            except:
                print("Could not find any input field")
                return False
    
    if not 'input_field' in locals():
        print("No input field found")
        return False
    
    # Enter the CAPTCHA text quickly
    print(f"Entering CAPTCHA text: {captcha_text}")
    input_field.clear()
    input_field.send_keys(captcha_text)
    
    # Quickly find and click the Unlock button
    try:
        # Direct approach using the specific selector
        unlock_button = driver.find_element(By.XPATH, '//button[contains(text(), "Unlock")]')
        print("Found Unlock button")
    except:
        try:
            # Try to find any button
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if btn.is_displayed():
                    if "unlock" in btn.text.lower() or btn.find_elements(By.TAG_NAME, "svg"):
                        unlock_button = btn
                        print(f"Found potential unlock button: {btn.text}")
                        break
        except:
            print("Could not find unlock button")
            # Try submitting with Enter key
            input_field.send_keys("\n")
            print("Submitted using Enter key")
            time.sleep(3)
            
            # Check if we're still on the CAPTCHA page
            if "You're Almost There" not in driver.page_source:
                print("CAPTCHA bypassed using Enter key submission")
                return True
            return False
    
    # Click the unlock button if found
    if 'unlock_button' in locals() and unlock_button:
        try:
            unlock_button.click()
            print("Clicked Unlock button")
        except:
            try:
                # Try JavaScript click
                driver.execute_script("arguments[0].click();", unlock_button)
                print("Clicked using JavaScript")
            except:
                print("Failed to click unlock button")
                return False
    
    # Wait a short time and check result
    time.sleep(3)
    
    # Check if we're still on the CAPTCHA page
    if "You're Almost There" not in driver.page_source:
        print("CAPTCHA successfully solved!")
        return True
    else:
        print("CAPTCHA solution failed - still on challenge page")
        return False

def handle_captcha(driver):
    """Detect and solve CAPTCHA using only automated services."""
    print("Checking for CAPTCHA...")
    
    # Take a screenshot for debug purposes
    driver.save_screenshot("current_page.png")
    print("Saved screenshot of current page as current_page.png")
    
    # Check if we're on the security check page - this is highest priority
    if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
        print("Security check (CAPTCHA) page detected.")
        # Fixed: Call solve_image_text_captcha instead of recursive handle_captcha call
        result = solve_image_text_captcha(driver)
        if not result:
            print("Automated CAPTCHA solving failed.")
            return False
        return result
    
    # Check for age verification only if we have a clearly visible "Agree and close" button
    try:
        # Look specifically for the "Agree and close" button using the selector you provided
        agree_button = driver.find_element(By.XPATH, '//button[contains(text(), "Agree and close")]')
        
        if agree_button.is_displayed():
            print("Found 'Agree and close' button - clicking it")
            agree_button.click()
            time.sleep(1)
            return True
    except:
        # No agree button found - that's fine, continue normally
        pass
        
    # If no action was needed
    print("No immediate challenges detected.")
    return True

def handle_age_verification(driver):
    """Handle the age verification prompt - simplified for specific button."""
    print("Handling age verification prompt...")
    
    # Take a screenshot for debugging
    driver.save_screenshot("age_verification_before.png")
    
    try:
        # Look for the specific "Agree and close" button
        agree_button = driver.find_element(By.XPATH, '//button[contains(text(), "Agree and close")]')
        
        # Click it if found and visible
        if agree_button.is_displayed():
            print("Clicking 'Agree and close' button")
            agree_button.click()
            time.sleep(1)
            
            # Take a screenshot after clicking
            driver.save_screenshot("age_verification_after.png")
            print("Clicked age verification button")
            return True
    except Exception as e:
        print(f"Note: No 'Agree and close' button found ({e})")
        
    # If nothing was found or clicked, just continue
    return True

def check_and_handle_challenges(driver):
    """Check for and handle both age verification and CAPTCHA challenges."""
    print("Checking for challenges (age verification or CAPTCHA)...")
    
    # First, take a screenshot to see what we're dealing with
    driver.save_screenshot("current_page.png")
    print("Saved screenshot as current_page.png")
    
    # Check if we're on the security check page - this is highest priority
    if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
        print("Security check (CAPTCHA) page detected.")
        result = solve_image_text_captcha(driver)  # Fixed function call
        if not result:
            print("Automated CAPTCHA solving failed.")
            return False
        return result
    
    # Check for age verification only if we have a clearly visible "Agree and close" button
    try:
        # Look specifically for the "Agree and close" button using the selector you provided
        agree_button = driver.find_element(By.XPATH, '//button[contains(text(), "Agree and close")]')
        
        if agree_button.is_displayed():
            print("Found 'Agree and close' button - clicking it")
            agree_button.click()
            time.sleep(1)
            return True
    except:
        # No agree button found - that's fine, continue normally
        pass
        
    # If no action was needed
    print("No immediate challenges detected.")
    return True

def load_page_and_handle_challenges(driver, url):
    """Load a page and handle any challenges (CAPTCHA, age verification)."""
    print(f"Loading page: {url}")
    driver.get(url)
    time.sleep(3)  # Wait for page to load
    
    # Take screenshot of initial page
    driver.save_screenshot(f"page_initial_{url.split('page=')[1] if 'page=' in url else '1'}.png")
    
    # First, check if we're already on a search results page with profiles
    try:
        initial_profiles = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
        if initial_profiles:
            print(f"Already on search results page with {len(initial_profiles)} profiles visible")
            return True
    except:
        pass
    
    # Handle challenges if needed
    retries = 0
    max_retries = 3
    
    while retries < max_retries:
        # Handle any challenges on the page
        challenge_result = check_and_handle_challenges(driver)
        
        # Check if we have profile links (success criteria)
        try:
            visible_profiles = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
            if visible_profiles:
                print(f"Success! Found {len(visible_profiles)} profile links after handling challenges")
                return True
        except Exception as e:
            print(f"Error checking for profile links: {e}")
        
        # If challenges were handled but still no profiles, try refreshing or waiting
        if challenge_result:
            print("Challenge handled, but no profiles found yet. Waiting...")
            time.sleep(3)
        else:
            print(f"Failed to handle challenges on attempt {retries+1}/{max_retries}")
            # Maybe try a page refresh
            if retries >= 1:
                print("Trying page refresh...")
                driver.refresh()
                time.sleep(3)
            
        retries += 1
    
    # After max retries, check one last time for profiles
    try:
        final_check = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
        if final_check:
            print(f"Found {len(final_check)} profiles after retries")
            return True
    except:
        pass
    
    print("Failed to load page with profile results after multiple attempts")
    return False

def extract_pagination_links(driver):
    """Extract pagination links from Tryst.link search results page."""
    pagination_links = []
    
    try:
        # First take a screenshot of the bottom of the page where pagination should be
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.save_screenshot("pagination_area.png")
        
        # Look specifically for next page button - it's the most useful
        next_page = None
        try:
            # Look for "Next" link
            next_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
            if next_links:
                for link in next_links:
                    if link.is_displayed() and link.get_attribute("href"):
                        next_page = link.get_attribute("href")
                        print(f"Found Next page link: {next_page}")
                        pagination_links.append(next_page)
                        break
        except:
            pass
            
        # If "Next" not found, look for specific page number links
        if not pagination_links:
            # Look specifically for page number links at the bottom of search results
            page_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'page=')]")
            
            for link in page_links:
                href = link.get_attribute("href")
                if href and "page=" in href:
                    # Get current page from URL if present
                    current_url = driver.current_url
                    current_page = 1
                    if "page=" in current_url:
                        try:
                            page_param = current_url.split("page=")[1].split("&")[0]
                            current_page = int(page_param)
                        except:
                            pass
                    
                    # Get linked page number
                    try:
                        linked_page = int(href.split("page=")[1].split("&")[0])
                        
                        # Only add links to higher page numbers (going forward)
                        if linked_page > current_page:
                            pagination_links.append(href)
                            print(f"Found page link: {href} (page {linked_page})")
                    except:
                        # If we can't parse the page number, add it anyway
                        pagination_links.append(href)
            
            # Sort pagination links - important to visit pages in order
            try:
                # Sort by page number
                def get_page_num(url):
                    try:
                        return int(url.split("page=")[1].split("&")[0])
                    except:
                        return 999  # High number for unparseable pages
                
                pagination_links = sorted(set(pagination_links), key=get_page_num)
            except:
                # If sorting fails, at least remove duplicates
                pagination_links = list(set(pagination_links))
        
        print(f"Found {len(pagination_links)} pagination links")
        return pagination_links
    
    except Exception as e:
        print(f"Error finding pagination links: {e}")
        return []

def load_all_profiles(driver, start_url=None, start_page=1):
    """Load all profiles by handling pagination and scrolling on each page."""
    print("Loading search page...")
    base_url = "https://tryst.link/search?loc=%3AAnywhere&within=50km&trans=false&q="
    
    # Use the provided start URL or default to base URL
    initial_url = start_url if start_url else base_url
    
    # Set to store all collected profile links
    all_profile_links = set()
    max_pages = float('inf')  # Unlimited pages
    page_count = start_page - 1  # Start counting from the specified page
    
    # Create a file to track the current page
    with open("current_page.txt", "w") as f:
        f.write(f"{start_page}")  # Initialize with the starting page
    
    # Process the first page
    if not load_page_and_handle_challenges(driver, initial_url):
        print("Failed to load initial page due to challenges.")
        return False
    
    # Main pagination loop
    pages_to_visit = [initial_url]
    visited_pages = set()
    
    while pages_to_visit and page_count < max_pages:
        current_url = pages_to_visit.pop(0)
        if current_url in visited_pages:
            continue
            
        page_count += 1
        
        # Update the current page tracker file
        with open("current_page.txt", "w") as f:
            f.write(f"{page_count}")
        
        print(f"\n{'='*50}")
        print(f"CURRENT PAGE: {page_count}")
        print(f"URL: {current_url}")
        print(f"{'='*50}\n")
        
        # Load the page if it's not the first one (already loaded)
        if current_url != base_url or page_count > 1:
            if not load_page_and_handle_challenges(driver, current_url):
                print(f"Failed to load page {current_url} due to challenges.")
                continue
        
        visited_pages.add(current_url)
        
        # Scroll down the page to load all content
        print("Scrolling to load all profiles on this page...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        max_scrolls = 5  # Reduced since we're paginating
        
        while scroll_count < max_scrolls:
            scroll_count += 1
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            print(f"Scroll {scroll_count}/{max_scrolls}...")
            time.sleep(2)
            
            # Check for CAPTCHA
            if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
                print("Security check appeared during scrolling.")
                if not solve_image_text_captcha(driver):
                    print("Failed to handle CAPTCHA during scrolling.")
                    break
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("Reached the bottom of the page.")
                break
            last_height = new_height
        
        # Extract profile links from this page
        try:
            links = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
            page_links = set(link.get_attribute("href") for link in links if "/escort/" in link.get_attribute("href"))
            if page_links:
                print(f"Found {len(page_links)} profile links on page {page_count}.")
                all_profile_links.update(page_links)
                # Save URLs incrementally after each page
                save_urls(all_profile_links)
                
                # Write the current status to the status file
                with open("scraping_status.txt", "w") as f:
                    f.write(f"Last completed page: {page_count}\n")
                    f.write(f"Total profiles found so far: {len(all_profile_links)}\n")
                    f.write(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                driver.save_screenshot(f"page_{page_count}_results.png")
            else:
                print(f"No profile links found on page {page_count}.")
                driver.save_screenshot(f"page_{page_count}_no_links.png")
        except Exception as e:
            print(f"Error extracting profile links on page {page_count}: {e}")
            driver.save_screenshot(f"page_{page_count}_error.png")
        
        # Get pagination links for next pages
        pagination_links = extract_pagination_links(driver)
        
        # Filter out already visited pages and add new ones to visit
        for link in pagination_links:
            if link not in visited_pages and link not in pages_to_visit:
                pages_to_visit.append(link)
        
        print(f"Total profiles found so far: {len(all_profile_links)}")
        print(f"Pages remaining in queue: {len(pages_to_visit)}")
    
    print(f"\nPagination complete! Processed {page_count} pages.")
    print(f"Total unique profile links collected: {len(all_profile_links)}")
    
    # Write the final page count to a status file
    with open("scraping_status.txt", "w") as f:
        f.write(f"Last completed page: {page_count}\n")
        f.write(f"Total profiles found: {len(all_profile_links)}\n")
        f.write(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Store the links in the driver.profile_links property for easier access
    driver.profile_links = all_profile_links
    
    return len(all_profile_links) > 0

def extract_profile_links(driver):
    """Get all unique profile links."""
    print("Extracting profile links...")
    
    # Check if we already stored the links in the driver object
    if hasattr(driver, 'profile_links') and driver.profile_links:
        profile_links = driver.profile_links
        print(f"Using {len(profile_links)} profile links collected during pagination.")
    else:
        # Fallback to extracting from current page if needed
        links = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
        profile_links = set(link.get_attribute("href") for link in links if "/escort/" in link.get_attribute("href"))
        print(f"Found {len(profile_links)} profile links on current page.")
    
    return profile_links

def load_saved_urls(filename="profile_urls.txt"):
    """Load previously saved URLs to avoid duplicates."""
    return set(line.strip() for line in open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else set()

def save_urls(urls, filename="profile_urls.txt"):
    """Save profile URLs to a file."""
    existing_urls = load_saved_urls(filename)
    combined_urls = existing_urls.union(urls)
    
    with open(filename, "w", encoding="utf-8") as f:
        for url in sorted(combined_urls):
            f.write(f"{url}\n")
    
    print(f"Saved {len(combined_urls)} URLs to {filename} ({len(combined_urls) - len(existing_urls)} new)")

def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  python profile_finder.py [OPTIONS]")
    print("Options:")
    print("  --start-page=N    Start processing from page N (default: 1)")
    print("  --visible         Use fully visible browser (may steal focus)")
    print("  --help            Show this help message")

def main():
    """Run the profile finder with automated CAPTCHA solving."""
    # Parse command line arguments
    import sys
    
    # Check for help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return
    
    # Default start page
    start_page = 1
    # Default to prevent focus stealing
    prevent_focus = True
    
    # Parse command line arguments
    for arg in sys.argv[1:]:
        if arg.startswith("--start-page="):
            try:
                start_page = int(arg.split("=", 1)[1])
                if start_page < 1:
                    print("Start page must be at least 1. Setting to 1.")
                    start_page = 1
            except ValueError:
                print(f"Invalid start page: {arg}. Using default (1).")
                start_page = 1
        elif arg == "--visible":
            prevent_focus = False
            print("Using fully visible browser mode (may steal focus)")
    
    print("Starting Tryst.link Profile Finder with automated CAPTCHA solving...")
    print(f"2Captcha API Key: {'*' * (len(TWOCAPTCHA_API_KEY) - 8) + TWOCAPTCHA_API_KEY[-8:]}")
    if start_page > 1:
        print(f"Starting from page {start_page}")
    
    driver = initialize_driver(headless=False, prevent_focus=prevent_focus)  # Use headless=new by default to prevent focus stealing
    
    try:
        # Generate the starting page URL if not starting from page 1
        base_url = "https://tryst.link/search?loc=%3AAnywhere&within=50km&trans=false&q="
        start_url = base_url
        if start_page > 1:
            start_url = f"{base_url}&page={start_page}"
            print(f"Using start URL: {start_url}")
        
        # Load the search page and scroll to load all profiles
        loading_success = load_all_profiles(driver, start_url=start_url, start_page=start_page)
        
        if loading_success:
            # Extract all profile links (for final summary only)
            profile_links = extract_profile_links(driver)
            
            if profile_links:
                print(f"Successfully collected {len(profile_links)} profile URLs to profile_urls.txt")
            else:
                print("No profile links were found to save.")
        else:
            print("Failed to load profiles due to automated CAPTCHA challenges.")
            print("Please check your CAPTCHA service API keys and try again.")
        
    except Exception as e:
        print(f"Error during profile finding: {e}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("error_screenshot.png")
        print("Saved error screenshot as error_screenshot.png")
    finally:
        print("Closing browser...")
        driver.quit()
        print("Profile finder complete.")

if __name__ == "__main__":
    main()