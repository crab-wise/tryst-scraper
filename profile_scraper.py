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
    """Scrape a profile, revealing hidden email and collecting data."""
    print(f"Scraping {url}...")
    driver.get(url)
    
    # Handle age verification and CAPTCHA if needed
    handle_age_verification(driver)
    handle_captcha(driver)
    
    data = {"url": url, "email": None, "website": None, "onlyfans": None}
    
    try:
        # Extract profile name
        try:
            profile_name = driver.find_element(By.CSS_SELECTOR, "h1.profile-header__name").text.strip()
            data["name"] = profile_name
            print(f"Profile name: {profile_name}")
        except:
            print("Could not extract profile name")
        
        # Reveal and extract email
        try:
            show_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//a[@title="Show Email"]'))
            )
            show_button.click()
            
            email_span = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-unobfuscate-details-target="output"]'))
            )
            
            # Wait for the email to fully unobfuscate (dots ● should disappear)
            WebDriverWait(driver, 10).until(lambda d: "●" not in email_span.text)
            data["email"] = email_span.text.strip()
            print(f"Email: {data['email']}")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"No email found or failed to unobfuscate: {e}")

        # Extract website links
        try:
            website_links = driver.find_elements(By.XPATH, '//a[contains(text(), "Website") or contains(@href, "http") and not(contains(@href, "tryst.link"))]')
            if website_links:
                data["website"] = website_links[0].get_attribute("href")
                print(f"Website: {data['website']}")
        except Exception as e:
            print(f"Error extracting website: {e}")

        # Extract OnlyFans link
        try:
            onlyfans_links = driver.find_elements(By.XPATH, '//a[contains(text(), "OnlyFans") or contains(@href, "onlyfans.com")]')
            if onlyfans_links:
                data["onlyfans"] = onlyfans_links[0].get_attribute("href")
                print(f"OnlyFans: {data['onlyfans']}")
        except Exception as e:
            print(f"Error extracting OnlyFans: {e}")
            
        # Extract other social media
        try:
            twitter_links = driver.find_elements(By.XPATH, '//a[contains(text(), "Twitter") or contains(@href, "twitter.com") or contains(@href, "x.com")]')
            if twitter_links:
                data["twitter"] = twitter_links[0].get_attribute("href")
                print(f"Twitter: {data['twitter']}")
        except:
            print("No Twitter link found")
            
        try:
            instagram_links = driver.find_elements(By.XPATH, '//a[contains(text(), "Instagram") or contains(@href, "instagram.com")]')
            if instagram_links:
                data["instagram"] = instagram_links[0].get_attribute("href")
                print(f"Instagram: {data['instagram']}")
        except:
            print("No Instagram link found")

    except Exception as e:
        print(f"Error scraping profile {url}: {e}")
    
    return data

def initialize_csv(filename="profile_data.csv"):
    """Set up the CSV file if it doesn't exist."""
    if not os.path.exists(filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Profile URL", "Name", "Email", "Website", "OnlyFans", "Twitter", "Instagram"])

def save_to_csv(data, filename="profile_data.csv"):
    """Append profile data to the CSV."""
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            data.get("url", ""),
            data.get("name", ""),
            data.get("email", ""),
            data.get("website", ""),
            data.get("onlyfans", ""),
            data.get("twitter", ""),
            data.get("instagram", "")
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
    driver = initialize_driver(headless=False, prevent_focus=True)  # Visible browser but prevent focus stealing
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
    driver = initialize_driver(headless=False, prevent_focus=True)  # Visible browser but prevent focus stealing
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
    print("  --help             Show this help message")

def main():
    """Parse command line arguments and run the scraper."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return
    
    # Default options
    url = None
    url_file = "profile_urls.txt"
    limit = None
    start_index = 0
    prevent_focus = True
    
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
    
    # Override the initialize_driver function to use our focus prevention setting
    from profile_finder import initialize_driver as original_init_driver
    
    # Create a custom initializer that uses our prevent_focus setting
    def custom_init_driver(headless=False, prevent_focus=prevent_focus):
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