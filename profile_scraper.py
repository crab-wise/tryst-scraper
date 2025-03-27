#!/usr/bin/env python3
"""
Profile Scraper for Tryst.link

This script takes a profile URL and extracts contact information including:
- Email (revealed after clicking 'Show Email')
- Website links
- OnlyFans links
"""

import time
import csv
import os
import sys
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

# Import CAPTCHA solving functions from profile_finder
from profile_finder import (
    initialize_driver,
    handle_captcha,
    handle_age_verification,
    TWOCAPTCHA_API_KEY
)

def scrape_profile(driver, url):
    """Scrape a profile, revealing all hidden information and collecting all contact details."""
    print(f"Scraping {url}...")
    driver.get(url)
    
    # Handle age verification and CAPTCHA if needed
    handle_age_verification(driver)
    handle_captcha(driver)
    
    # Initialize data dictionary with all possible contact fields
    data = {
        "url": url,
        "name": None,
        "email": None,
        "phone": None,
        "mobile": None,
        "whatsapp": None,
        "linktree": None,
        "website": None,
        "onlyfans": None,
        "fansly": None,
        "twitter": None,
        "instagram": None,
        "snapchat": None,
        "telegram": None
    }
    
    try:
        # Extract profile name
        try:
            profile_name = driver.find_element(By.CSS_SELECTOR, "h1.profile-header__name").text.strip()
            data["name"] = profile_name
            print(f"Profile name: {profile_name}")
        except Exception as e:
            print(f"Could not extract profile name: {e}")
        
        # Click all "Show" buttons to reveal hidden information
        try:
            # First look for all "Show Email", "Show Mobile", "Show WhatsApp" links
            # This more specific selector targets exactly the show links in the contact details
            show_buttons = driver.find_elements(By.CSS_SELECTOR, "a[data-action*='unobfuscate-details#revealUnobfuscatedContent']")
            print(f"Found {len(show_buttons)} contact 'Show' buttons using specific CSS selector")
            
            if not show_buttons:
                # Try a second approach with class selectors
                show_buttons = driver.find_elements(By.CSS_SELECTOR, "a.text-secondary.fw-bold.text-decoration-none")
                print(f"Found {len(show_buttons)} 'Show' buttons using class selector")
                
                if not show_buttons:
                    # Fall back to the XPATH as a last resort
                    show_buttons = driver.find_elements(By.XPATH, '//a[contains(@title, "Show") or contains(text(), "Show")]')
                    print(f"Found {len(show_buttons)} 'Show' buttons using XPATH")
            
            # Take a screenshot for debugging
            driver.save_screenshot("before_clicking_show_buttons.png")
            print(f"Saved screenshot before clicking buttons")
            
            # Click each Show button
            for button in show_buttons:
                try:
                    button_text = button.text.strip()
                    button_title = button.get_attribute("title") or button_text
                    button_html = button.get_attribute("outerHTML")
                    print(f"Found button: {button_title}")
                    print(f"Button HTML: {button_html}")
                    
                    # Make sure button is in view
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.5)
                    
                    # Try JavaScript click for more reliable interaction
                    driver.execute_script("arguments[0].click();", button)
                    print(f"Successfully clicked {button_title}")
                    
                    # Small delay to let unobfuscation happen
                    time.sleep(1)
                except Exception as e:
                    print(f"Error clicking button {button_title}: {e}")
                    try:
                        # Fall back to regular click if JS click fails
                        button.click()
                        print(f"Successfully clicked {button_title} with regular click")
                        time.sleep(1)
                    except Exception as e2:
                        print(f"Both click methods failed: {e2}")
            
            # Take another screenshot after clicking
            driver.save_screenshot("after_clicking_show_buttons.png")
            print(f"Saved screenshot after clicking buttons")
            
            # Wait for all hidden content to become visible
            time.sleep(2)
        except Exception as e:
            print(f"Error revealing hidden information: {e}")
        
        # Now extract all contact details after buttons have been clicked
        # Take a full page screenshot for debugging
        screenshot_path = f"profile_{url.split('/')[-1]}.png"
        driver.save_screenshot(screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")
        
        # Find all contact sections
        contact_sections = driver.find_elements(By.CSS_SELECTOR, "ul.list-style-none.bg-light.p-3.rounded")
        print(f"Found {len(contact_sections)} contact sections")
        
        # Process all contact rows
        for section in contact_sections:
            try:
                contact_rows = section.find_elements(By.CSS_SELECTOR, "div.row.justify-content-between")
                print(f"Found {len(contact_rows)} contact rows in section")
                
                for row in contact_rows:
                    try:
                        # Get the label/type of contact from the first column
                        label_el = row.find_element(By.CSS_SELECTOR, "div.col-auto.fw-bold")
                        label = label_el.text.strip().lower()
                        print(f"Processing contact type: {label}")
                        
                        # Get the value from the second column
                        value_el = row.find_element(By.CSS_SELECTOR, "div.col-auto.text-end")
                        
                        # First check for revealed (unobfuscated) information
                        unobfuscated_spans = value_el.find_elements(By.CSS_SELECTOR, "span[data-unobfuscate-details-target='output']")
                        if unobfuscated_spans and not "●" in unobfuscated_spans[0].text:
                            # This is an unobfuscated value (after clicking Show)
                            value = unobfuscated_spans[0].text.strip()
                            print(f"Found unobfuscated value: {value}")
                        else:
                            # Check for regular links
                            links = value_el.find_elements(By.CSS_SELECTOR, "a")
                            if links:
                                # For regular links like Twitter, Instagram, etc.
                                value = links[0].get_attribute("href")
                                print(f"Found link value: {value}")
                            else:
                                # Any other text
                                value = value_el.text.strip()
                                print(f"Found text value: {value}")
                                
                                # Skip if value contains obfuscated characters
                                if "●" in value:
                                    print(f"Skipping obfuscated value: {value}")
                                    continue
                        
                        # Store the value in the appropriate field
                        if "email" in label:
                            data["email"] = value
                            print(f"Saved email: {value}")
                        elif "mobile" in label:
                            data["mobile"] = value
                            print(f"Saved mobile: {value}")
                        elif "phone" in label:
                            data["phone"] = value
                            print(f"Saved phone: {value}")
                        elif "whatsapp" in label:
                            data["whatsapp"] = value
                            print(f"Saved whatsapp: {value}")
                        elif "twitter" in label or "x " in label:
                            data["twitter"] = value
                            print(f"Saved twitter: {value}")
                        elif "instagram" in label:
                            data["instagram"] = value
                            print(f"Saved instagram: {value}")
                        elif "linktree" in label:
                            data["linktree"] = value
                            print(f"Saved linktree: {value}")
                        elif "onlyfans" in label:
                            data["onlyfans"] = value
                            print(f"Saved onlyfans: {value}")
                        elif "fansly" in label:
                            data["fansly"] = value
                            print(f"Saved fansly: {value}")
                        elif "snapchat" in label:
                            data["snapchat"] = value
                            print(f"Saved snapchat: {value}")
                        elif "telegram" in label:
                            data["telegram"] = value
                            print(f"Saved telegram: {value}")
                        elif "website" in label:
                            data["website"] = value
                            print(f"Saved website: {value}")
                    except Exception as e:
                        print(f"Error processing contact row: {e}")
                        continue
            except Exception as e:
                print(f"Error processing contact section: {e}")
                continue
            
        # As a backup, also try to find contact links using XPath for anything we missed
        if not data["onlyfans"]:
            try:
                onlyfans_links = driver.find_elements(By.XPATH, '//a[contains(@href, "onlyfans.com")]')
                if onlyfans_links:
                    data["onlyfans"] = onlyfans_links[0].get_attribute("href")
                    print(f"Found OnlyFans (XPath method): {data['onlyfans']}")
            except:
                pass
                
        if not data["twitter"]:
            try:
                twitter_links = driver.find_elements(By.XPATH, '//a[contains(@href, "twitter.com") or contains(@href, "x.com")]')
                if twitter_links:
                    data["twitter"] = twitter_links[0].get_attribute("href")
                    print(f"Found Twitter (XPath method): {data['twitter']}")
            except:
                pass
                
        if not data["instagram"]:
            try:
                instagram_links = driver.find_elements(By.XPATH, '//a[contains(@href, "instagram.com")]')
                if instagram_links:
                    data["instagram"] = instagram_links[0].get_attribute("href")
                    print(f"Found Instagram (XPath method): {data['instagram']}")
            except:
                pass

    except Exception as e:
        print(f"Error scraping profile {url}: {e}")
    
    return data

def initialize_csv(filename="profile_data.csv"):
    """Set up the CSV file if it doesn't exist."""
    if not os.path.exists(filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Profile URL", "Name", "Email", "Phone", "Mobile", "WhatsApp", 
                "Linktree", "Website", "OnlyFans", "Fansly", "Twitter", "Instagram",
                "Snapchat", "Telegram"
            ])

def save_to_csv(data, filename="profile_data.csv"):
    """Append profile data to the CSV."""
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            data.get("url", ""),
            data.get("name", ""),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("mobile", ""),
            data.get("whatsapp", ""),
            data.get("linktree", ""),
            data.get("website", ""),
            data.get("onlyfans", ""),
            data.get("fansly", ""),
            data.get("twitter", ""),
            data.get("instagram", ""),
            data.get("snapchat", ""),
            data.get("telegram", "")
        ])
    print(f"Saved data to {filename}")

def load_scraped_urls(filename="scraped_urls.txt"):
    """Load previously scraped URLs to avoid duplicates."""
    return set(line.strip() for line in open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else set()

def save_scraped_url(url, filename="scraped_urls.txt"):
    """Save a scraped URL to the tracking file."""
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{url}\n")

def scrape_single_profile(url):
    """Scrape a single profile URL."""
    # Check if already scraped
    scraped_urls = load_scraped_urls()
    if url in scraped_urls:
        print(f"Profile {url} has already been scraped. Skipping.")
        return
    
    # Initialize driver and CSV
    driver = initialize_driver(headless=False, prevent_focus=True)  # Invisible mode that prevents focus stealing
    initialize_csv()
    
    try:
        # Scrape the profile
        data = scrape_profile(driver, url)
        
        # Save the data
        save_to_csv(data)
        save_scraped_url(url)
        
        print(f"Successfully scraped profile: {url}")
        
    except Exception as e:
        print(f"Error scraping profile {url}: {e}")
    finally:
        driver.quit()

def scrape_from_url_file(url_file="profile_urls.txt", limit=None, start_index=0):
    """Scrape profiles from a file of URLs."""
    # Check if file exists
    if not os.path.exists(url_file):
        print(f"URL file {url_file} not found. Please run profile_finder.py first.")
        return
    
    # Load URLs and already scraped URLs
    with open(url_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    
    scraped_urls = load_scraped_urls()
    remaining_urls = [url for url in urls if url not in scraped_urls]
    
    if limit and limit > 0:
        remaining_urls = remaining_urls[start_index:start_index+limit]
    else:
        remaining_urls = remaining_urls[start_index:]
    
    print(f"Found {len(remaining_urls)} profiles to scrape out of {len(urls)} total.")
    print(f"Starting from index {start_index}")
    
    if not remaining_urls:
        print("No new profiles to scrape.")
        return
    
    # Initialize driver and CSV
    driver = initialize_driver(headless=False, prevent_focus=True)  # Invisible mode that prevents focus stealing
    initialize_csv()
    
    # Create a file to track progress
    with open("scraping_progress.txt", "w") as f:
        f.write(f"Starting from index: {start_index}\n")
        f.write(f"Total profiles to scrape: {len(remaining_urls)}\n")
        f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        for i, url in enumerate(remaining_urls):
            # Current real index (including the start_index offset)
            current_index = start_index + i
            
            # Update progress file
            with open("scraping_progress.txt", "w") as f:
                f.write(f"Current index: {current_index}\n")
                f.write(f"Profiles scraped: {i}/{len(remaining_urls)}\n")
                f.write(f"Last URL: {url}\n")
                f.write(f"Last update: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Completion: {i/len(remaining_urls)*100:.2f}%\n")
            
            print(f"\n{'='*50}")
            print(f"SCRAPING PROFILE {i+1}/{len(remaining_urls)}")
            print(f"OVERALL PROGRESS: {i/len(remaining_urls)*100:.2f}%")
            print(f"INDEX: {current_index}")
            print(f"URL: {url}")
            print(f"{'='*50}\n")
            
            try:
                # Scrape the profile
                data = scrape_profile(driver, url)
                
                # Save the data
                save_to_csv(data)
                save_scraped_url(url)
                
                # Add random delay to avoid detection
                delay = random.uniform(2, 5)
                print(f"Waiting {delay:.2f} seconds before next profile...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"Error scraping profile {url}: {e}")
                continue
    
    except Exception as e:
        print(f"Error during batch scraping: {e}")
        print(f"Last successful index: {start_index + i - 1}")
        print(f"To resume, use: python profile_scraper.py --start-index={start_index + i}")
    finally:
        # Save final progress
        with open("scraping_progress.txt", "a") as f:
            f.write(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if 'i' in locals():
                f.write(f"Last successful index: {start_index + i}\n")
                f.write(f"To resume, use: python profile_scraper.py --start-index={start_index + i + 1}\n")
        
        driver.quit()

def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print(f"  {sys.argv[0]} [OPTIONS]")
    print("Options:")
    print("  --url=URL          Scrape a single profile URL")
    print("  --file=FILE        Scrape profiles from a file (default: profile_urls.txt)")
    print("  --limit=N          Limit the number of profiles to scrape")
    print("  --start-index=N    Start scraping from index N in the URL list (default: 0)")
    print("  --visible          Use fully visible browser (may steal focus)")
    print("  --invisible        Use invisible browser (default, prevents focus stealing)")
    print("  --reset            Reset progress and start fresh (clears profile_data.csv and scraped_urls.txt)")
    print("  --help             Show this help message")

def reset_progress():
    """Reset progress by removing CSV and scraped URLs files."""
    csv_file = "profile_data.csv"
    scraped_urls_file = "scraped_urls.txt"
    
    if os.path.exists(csv_file):
        os.remove(csv_file)
        print(f"Removed {csv_file}")
    
    if os.path.exists(scraped_urls_file):
        os.remove(scraped_urls_file)
        print(f"Removed {scraped_urls_file}")
    
    print("Progress has been reset. Starting fresh.")

def main():
    """Parse command line arguments and run the scraper."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return
    
    # Check for reset flag first
    if "--reset" in sys.argv:
        reset_progress()
    
    # Default options
    url = None
    url_file = "profile_urls.txt"
    limit = None
    start_index = 0
    prevent_focus = True  # Default to invisible mode
    
    # Parse command line arguments
    for arg in sys.argv[1:]:
        if arg.startswith("--url="):
            url = arg.split("=", 1)[1]
        elif arg.startswith("--file="):
            url_file = arg.split("=", 1)[1]
        elif arg.startswith("--limit="):
            try:
                limit = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"Invalid limit: {arg}")
                print_usage()
                return
        elif arg.startswith("--start-index="):
            try:
                start_index = int(arg.split("=", 1)[1])
                if start_index < 0:
                    print("Start index must be at least 0. Setting to 0.")
                    start_index = 0
            except ValueError:
                print(f"Invalid start index: {arg}. Using default (0).")
                start_index = 0
        elif arg == "--visible":
            prevent_focus = False
            print("Using fully visible browser mode (may steal focus)")
        elif arg == "--invisible":
            prevent_focus = True
            print("Using invisible browser mode (prevents focus stealing)")
    
    # Override the initialize_driver function to use our focus prevention setting
    from profile_finder import initialize_driver as original_init_driver
    
    # Create a custom initializer that uses our prevent_focus setting
    def custom_init_driver(headless=False, prevent_focus=prevent_focus):
        # When --visible flag is used, force prevent_focus to False
        if not prevent_focus:
            print("Running in FULLY VISIBLE MODE - browser will be completely visible")
        return original_init_driver(headless=headless, prevent_focus=prevent_focus)
    
    # Replace the imported function with our custom one
    globals()['initialize_driver'] = custom_init_driver
    
    # Run the scraper
    if url:
        print(f"Scraping single profile: {url}")
        scrape_single_profile(url)
    else:
        print(f"Scraping profiles from file: {url_file}")
        print(f"Starting from index: {start_index}")
        scrape_from_url_file(url_file, limit, start_index)

if __name__ == "__main__":
    main()