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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import multiprocessing
from queue import Queue, Empty
from functools import partial

# Import CAPTCHA solving functions from profile_finder
from profile_finder import (
    initialize_driver,
    handle_captcha,
    handle_age_verification,
    TWOCAPTCHA_API_KEY
)

def scrape_profile(driver, url):
    """Scrape a profile, revealing all hidden information and collecting all contact details."""
    import time as timing_module  # For performance measurement
    
    print(f"Scraping {url}...")
    start_time = timing_module.time()
    
    # Load the page
    page_load_start = timing_module.time()
    driver.get(url)
    page_load_time = timing_module.time() - page_load_start
    print(f"⏱️ Page load time: {page_load_time:.2f} seconds")
    
    # Handle age verification and CAPTCHA if needed
    verification_start = timing_module.time()
    handle_age_verification(driver)
    handle_captcha(driver)
    verification_time = timing_module.time() - verification_start
    print(f"⏱️ Age verification and CAPTCHA handling: {verification_time:.2f} seconds")
    
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
            # Time the button finding and clicking process
            button_find_start = timing_module.time()
            
            # First look for all "Show Email", "Show Mobile", "Show WhatsApp" links
            # This more specific selector targets exactly the show links in the contact details
            show_buttons = driver.find_elements(By.CSS_SELECTOR, "a[data-action*='unobfuscate-details#revealUnobfuscatedContent']")
            print(f"Found {len(show_buttons)} contact 'Show' buttons using specific CSS selector")
            
            button_find_time = timing_module.time() - button_find_start
            print(f"⏱️ Button finding time: {button_find_time:.2f} seconds")
            
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
            
            # Time the button clicking process
            button_click_start = timing_module.time()
            
            # Click each Show button
            for button in show_buttons:
                try:
                    button_text = button.text.strip()
                    button_title = button.get_attribute("title") or button_text
                    button_html = button.get_attribute("outerHTML")
                    print(f"Found button: {button_title}")
                    print(f"Button HTML: {button_html}")
                    
                    # Execute a faster version of scrolling and clicking in one JS call
                    driver.execute_script("""
                        arguments[0].scrollIntoView({block: 'center'});
                        arguments[0].click();
                    """, button)
                    print(f"Successfully clicked {button_title}")
                    
                    # Minimum delay (just enough for the DOM to update)
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error clicking button {button_title}: {e}")
                    try:
                        # Fall back to regular click if JS click fails
                        button.click()
                        print(f"Successfully clicked {button_title} with regular click")
                        time.sleep(0.1)  # Minimal delay
                    except Exception as e2:
                        print(f"Both click methods failed: {e2}")
            
            # Take another screenshot after clicking
            driver.save_screenshot("after_clicking_show_buttons.png")
            print(f"Saved screenshot after clicking buttons")
            
            # Calculate total button clicking time
            button_click_time = timing_module.time() - button_click_start
            print(f"⏱️ Button clicking time: {button_click_time:.2f} seconds")
            
            # Wait for all hidden content to become visible (reduced time)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error revealing hidden information: {e}")
        
        # Now extract all contact details after buttons have been clicked - optimized version
        # Start timing data extraction
        extraction_start = timing_module.time()
        
        # Optional screenshot - comment out to save time if not needed for debugging
        # screenshot_path = f"profile_{url.split('/')[-1]}.png"
        # driver.save_screenshot(screenshot_path)
        # print(f"Saved screenshot to {screenshot_path}")
        
        # OPTIMIZED: Extract contact details using a direct JavaScript approach
        # This collects all contact information at once using JavaScript to avoid Selenium overhead
        contact_data = driver.execute_script("""
            const result = {};
            
            // Process contact sections
            const contactSections = document.querySelectorAll("ul.list-style-none.bg-light.p-3.rounded");
            
            for (const section of contactSections) {
                const rows = section.querySelectorAll("div.row.justify-content-between");
                
                for (const row of rows) {
                    try {
                        // Get label
                        const labelEl = row.querySelector("div.col-auto.fw-bold");
                        if (!labelEl) continue;
                        
                        // Extract label text and clean it
                        let label = labelEl.textContent.trim().toLowerCase();
                        // Handle "X (formerly Twitter)" case
                        if (label.includes("(formerly twitter)")) {
                            label = "twitter";
                        }
                        
                        // Get value element
                        const valueEl = row.querySelector("div.col-auto.text-end");
                        if (!valueEl) continue;
                        
                        let value = null;
                        
                        // Check for unobfuscated info
                        const unobfuscatedSpan = valueEl.querySelector("span[data-unobfuscate-details-target='output']");
                        if (unobfuscatedSpan && !unobfuscatedSpan.textContent.includes('●')) {
                            value = unobfuscatedSpan.textContent.trim();
                        } else {
                            // Check for links
                            const link = valueEl.querySelector("a");
                            if (link) {
                                value = link.href;
                            } else {
                                // Any other text
                                const text = valueEl.textContent.trim();
                                if (!text.includes('●')) {
                                    value = text;
                                }
                            }
                        }
                        
                        // Store if we found a value
                        if (value) {
                            result[label] = value;
                        }
                    } catch(e) {
                        // Skip errors
                        continue;
                    }
                }
            }
            
            return result;
        """)
        
        # For debugging
        print(f"Extracted contact data via JavaScript: {contact_data}")
        
        # Map the JavaScript results to our data dictionary
        field_mapping = {
            "email": "email",
            "mobile": "mobile", 
            "phone": "phone",
            "whatsapp": "whatsapp",
            "twitter": "twitter",
            "x": "twitter",  # Handle "X (formerly Twitter)" case
            "instagram": "instagram",
            "linktree": "linktree",
            "onlyfans": "onlyfans",
            "fansly": "fansly", 
            "snapchat": "snapchat",
            "telegram": "telegram",
            "website": "website"
        }
        
        # Apply mapping and save data
        if contact_data:
            for js_field, value in contact_data.items():
                for key, data_field in field_mapping.items():
                    if key in js_field:
                        data[data_field] = value
                        print(f"Saved {data_field}: {value}")
                        break
            
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
                
        # Calculate data extraction time
        extraction_time = timing_module.time() - extraction_start
        print(f"⏱️ Data extraction time: {extraction_time:.2f} seconds")
        
        # Calculate total profile scraping time
        total_time = timing_module.time() - start_time
        print(f"⏱️ TOTAL SCRAPING TIME: {total_time:.2f} seconds")

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

def optimize_driver_settings(driver):
    """Apply additional optimizations to the driver for faster performance."""
    # Adjust timeouts for faster responses
    driver.set_page_load_timeout(30)  # Set a reasonable timeout
    driver.set_script_timeout(10)     # Faster script execution timeout
    
    # Disable unnecessary features via JavaScript
    driver.execute_script("""
        // Disable animations for better performance
        const style = document.createElement('style');
        style.innerHTML = `
            * {
                animation-duration: 0.001s !important;
                transition-duration: 0.001s !important;
            }
        `;
        document.head.appendChild(style);
        
        // Disable image loading for speed (uncomment if needed)
        // document.querySelectorAll('img').forEach(img => {
        //    img.style.display = 'none';
        // });
        
        // Disable CSS transitions
        document.querySelectorAll('*').forEach(el => {
            if (el.style) {
                el.style.transition = 'none';
                el.style.animation = 'none';
            }
        });
    """)
    
    return driver

def scrape_profile_worker(url):
    """Worker function for parallel processing to scrape a single profile."""
    # Create a new driver instance for this thread with performance optimizations
    driver = initialize_driver(headless=False, prevent_focus=True)  # Invisible mode that prevents focus stealing
    
    try:
        # Check if already scraped (memory cached version for speed)
        scraped_urls = load_scraped_urls()
        if url in scraped_urls:
            print(f"Profile {url} has already been scraped. Skipping.")
            driver.quit()
            return None
        
        # Apply performance optimizations to driver
        optimize_driver_settings(driver)
        
        # Scrape the profile
        data = scrape_profile(driver, url)
        
        # Save the data (use thread lock to avoid race conditions)
        with csv_lock:
            save_to_csv(data)
            save_scraped_url(url)
        
        return data
    except Exception as e:
        print(f"Worker error scraping profile {url}: {e}")
        return None
    finally:
        # Clean up driver
        try:
            driver.quit()
        except:
            pass  # Ignore errors during cleanup

def scrape_from_url_file(url_file="profile_urls.txt", limit=None, start_index=0, max_workers=4):
    """Scrape profiles from a file of URLs using hyper-optimized parallel processing."""
    global csv_lock  # To prevent race conditions when writing to CSV file
    csv_lock = threading.Lock()
    
    # Check if file exists
    if not os.path.exists(url_file):
        print(f"URL file {url_file} not found. Please run profile_finder.py first.")
        return
    
    # OPTIMIZATION: Load URLs in chunks and process in batches
    # Only load what we need to reduce memory usage
    all_urls = []
    with open(url_file, "r", encoding="utf-8") as f:
        all_urls = [line.strip() for line in f if line.strip()]
    
    # Load scraped URLs
    scraped_urls = load_scraped_urls()
    
    # Define batch size - large enough for efficiency but small enough to show progress
    batch_size = 100  # Process URLs in batches of 100
    
    # Calculate total remaining URLs for reporting
    remaining_urls = [url for url in all_urls if url not in scraped_urls]
    total_remaining = len(remaining_urls)
    
    if limit and limit > 0:
        total_to_process = min(limit, total_remaining - start_index)
    else:
        total_to_process = total_remaining - start_index
    
    print(f"Found {total_remaining} profiles to scrape out of {len(all_urls)} total.")
    print(f"Starting from index {start_index}")
    print(f"Will process {total_to_process} profiles")
    print(f"Using hyper-optimized parallel processing with {max_workers} workers")
    
    if total_to_process <= 0:
        print("No new profiles to scrape.")
        return
    
    # Initialize CSV file
    initialize_csv()
    
    # Create a file to track progress
    with open("scraping_progress.txt", "w") as f:
        f.write(f"Starting from index: {start_index}\n")
        f.write(f"Total profiles to scrape: {total_to_process}\n")
        f.write(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Using {max_workers} parallel workers with batch processing\n")
    
    # Use concurrent processing
    total_start_time = time.time()
    completed = 0
    errors = 0
    
    # Configure the work queue and result collection
    work_queue = Queue()
    result_queue = Queue()
    
    # Process URLs in batches 
    current_batch_start = start_index
    remaining_to_process = total_to_process
    
    try:
        # Create a batch processing loop
        while remaining_to_process > 0:
            # Determine this batch size
            current_batch_size = min(batch_size, remaining_to_process)
            
            # Get the batch URLs
            batch_urls = []
            for i in range(current_batch_size):
                idx = current_batch_start + i
                if idx < len(all_urls):
                    url = all_urls[idx]
                    if url not in scraped_urls:
                        batch_urls.append((current_batch_start + i, url))
            
            print(f"\n{'='*50}")
            print(f"PROCESSING BATCH OF {len(batch_urls)} PROFILES")
            print(f"OVERALL PROGRESS: {completed/total_to_process*100:.2f}%")
            print(f"{'='*50}\n")
            
            # Process this batch in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # More efficient future handling with as_completed
                future_to_url = {executor.submit(scrape_profile_worker, url): (i, url) for i, url in batch_urls}
                
                # Process results as they complete (better resource utilization)
                for future in as_completed(future_to_url):
                    i, url = future_to_url[future]
                    
                    try:
                        # Get result
                        result = future.result()
                        completed += 1
                        
                        # Update progress occasionally (not after every URL for efficiency)
                        if completed % 5 == 0 or completed == total_to_process:
                            with open("scraping_progress.txt", "w") as f:
                                f.write(f"Current batch: {current_batch_start//batch_size + 1}\n")
                                f.write(f"Profiles scraped: {completed}/{total_to_process}\n")
                                f.write(f"Last completed URL: {url}\n")
                                f.write(f"Last update: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write(f"Completion: {completed/total_to_process*100:.2f}%\n")
                                f.write(f"Speed: {completed/(time.time()-total_start_time):.2f} profiles/second\n")
                            
                            current_speed = completed/(time.time()-total_start_time)
                            print(f"Progress: {completed}/{total_to_process} ({completed/total_to_process*100:.2f}%) - Speed: {current_speed:.2f} profiles/sec")
                            
                    except Exception as e:
                        print(f"Error processing future for {url}: {e}")
                        errors += 1
            
            # Update for next batch
            current_batch_start += current_batch_size
            remaining_to_process -= current_batch_size
            
            # Update scraped_urls with newly completed URLs to avoid reprocessing
            scraped_urls = load_scraped_urls()
    
    except Exception as e:
        print(f"Error during batch processing: {e}")
    finally:
        # Calculate total time and stats
        total_time = time.time() - total_start_time
        profiles_per_second = completed / total_time if total_time > 0 else 0
        
        # Save final progress with more statistics
        with open("scraping_progress.txt", "a") as f:
            f.write(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total profiles processed: {completed}/{total_to_process}\n")
            f.write(f"Errors encountered: {errors}\n")
            f.write(f"Total time: {total_time:.2f} seconds\n")
            f.write(f"Average speed: {profiles_per_second:.2f} profiles/second\n")
            f.write(f"To resume, use: python profile_scraper.py --start-index={start_index + completed}\n")
        
        print(f"\n{'='*50}")
        print(f"SCRAPING COMPLETED")
        print(f"Total profiles processed: {completed}/{total_to_process}")
        print(f"Errors encountered: {errors}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average speed: {profiles_per_second:.2f} profiles/second")
        print(f"{'='*50}\n")

def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print(f"  {sys.argv[0]} [OPTIONS]")
    print("Options:")
    print("  --url=URL          Scrape a single profile URL")
    print("  --file=FILE        Scrape profiles from a file (default: profile_urls.txt)")
    print("  --limit=N          Limit the number of profiles to scrape")
    print("  --start-index=N    Start scraping from index N in the URL list (default: 0)")
    print("  --workers=N        Number of parallel workers (default: 8, set to 1 for serial processing)")
    print("  --batch-size=N     Number of profiles to process in each batch (default: 100)")
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
    workers = 8           # Default to 8 parallel workers
    batch_size = 100      # Default batch size
    
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
        elif arg.startswith("--workers="):
            try:
                workers = int(arg.split("=", 1)[1])
                if workers < 1:
                    print("Workers must be at least 1. Setting to 1.")
                    workers = 1
                print(f"Using {workers} parallel worker{'s' if workers > 1 else ''}")
            except ValueError:
                print(f"Invalid workers: {arg}. Using default (8).")
                workers = 8
        elif arg.startswith("--batch-size="):
            try:
                batch_size = int(arg.split("=", 1)[1])
                if batch_size < 1:
                    print("Batch size must be at least 1. Setting to 10.")
                    batch_size = 10
                print(f"Using batch size of {batch_size}")
            except ValueError:
                print(f"Invalid batch size: {arg}. Using default (100).")
                batch_size = 100
    
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
        print(f"Using {workers} parallel worker{'s' if workers > 1 else ''}")
        print(f"Using batch size of {batch_size}")
        
        # Update scrape_from_url_file to accept batch_size
        # Using a wrapper function to maintain backward compatibility
        def scrape_with_batch_size(url_file, limit, start_index, workers):
            # Modify the batch_size in the function
            global batch_size
            scrape_from_url_file(url_file, limit, start_index, workers)
            
        scrape_with_batch_size(url_file, limit, start_index, workers)

if __name__ == "__main__":
    main()