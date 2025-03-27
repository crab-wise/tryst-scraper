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
    captcha_result = handle_captcha(driver)
    
    # Check if we're still on the CAPTCHA page
    if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
        print("Still on CAPTCHA page after initial handling - trying again")
        captcha_result = handle_captcha(driver)
    
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
    
    # Verify we're on a profile page using multiple indicators - enhanced detection
    is_profile_page = False
    profile_name = None
    
    # Take a screenshot to help with debugging
    driver.save_screenshot(f"page_{url.split('/')[-1]}.png")
    
    # First check if we're NOT on a CAPTCHA page
    if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
        print("⚠️ Still on CAPTCHA page - not a profile page")
    else:
        # Try multiple methods to confirm we're on a profile page
        detection_scores = 0  # Count how many profile indicators we find
        
        # Method 1: Look for contact section
        try:
            contact_section = driver.find_element(By.CSS_SELECTOR, "ul.list-style-none.bg-light.p-3.rounded")
            if contact_section:
                print("✓ Found contact section - strong indicator of profile page")
                detection_scores += 2  # Strong indicator
                is_profile_page = True
        except:
            pass
            
        # Method 2: Look for Show buttons - multiple selectors
        try:
            # Try various selectors that might match Show buttons
            show_button_selectors = [
                "a[data-action*='unobfuscate-details#revealUnobfuscatedContent']",
                "a.text-secondary.fw-bold.text-decoration-none",
                "a.fw-bold[href='javascript:void(0)']"
            ]
            
            for selector in show_button_selectors:
                show_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if show_buttons and len(show_buttons) > 0:
                    print(f"✓ Found {len(show_buttons)} 'Show' buttons with selector '{selector}'")
                    detection_scores += 2  # Strong indicator
                    is_profile_page = True
                    break
        except:
            pass
            
        # Method 3: Try to find profile name in any heading
        try:
            headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3")
            for heading in headings:
                if heading.text and len(heading.text) > 3 and "You're almost there" not in heading.text.lower():
                    profile_name = heading.text.strip()
                    data["name"] = profile_name
                    print(f"✓ Found profile name: {profile_name}")
                    detection_scores += 1  # Moderate indicator
                    is_profile_page = True
                    break
        except:
            pass
            
        # Method 4: Look for profile images
        try:
            profile_images = driver.find_elements(By.CSS_SELECTOR, "div.profile-gallery img, img.profile-header__avatar")
            if profile_images and len(profile_images) > 0:
                print(f"✓ Found {len(profile_images)} profile images")
                detection_scores += 1  # Moderate indicator
                is_profile_page = True
        except:
            pass
            
        # Method 5: Check for profile URL structure in current URL
        profile_url_pattern = r'/escort/[-a-z0-9]+'
        import re
        if re.search(profile_url_pattern, driver.current_url):
            print(f"✓ Current URL '{driver.current_url}' matches profile pattern")
            detection_scores += 1  # Weak indicator but useful
            
        # Method 6: Look for contact info container
        try:
            contact_info = driver.find_elements(By.XPATH, "//*[contains(text(), 'Contact Info')]")
            if contact_info:
                print("✓ Found 'Contact Info' section heading")
                detection_scores += 1
                is_profile_page = True
        except:
            pass
    
        # Log overall detection confidence
        print(f"Profile page detection score: {detection_scores}/7 (3+ suggests a profile page)")
        is_profile_page = detection_scores >= 3  # Require multiple indicators
    
    if not is_profile_page:
        print(f"⚠️ Warning: Could not confirm this is a profile page (detection score too low)")
        # Save both a screenshot and the page source
        driver.save_screenshot(f"not_profile_page_{url.split('/')[-1]}.png")
        with open(f"not_profile_page_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # Analyze the page to see why we're not on profile
        if "captcha" in driver.page_source.lower() or "security check" in driver.page_source.lower():
            print("⚠️ Still on CAPTCHA/security page - attempting to solve again")
            handle_captcha(driver)
            time.sleep(2)
            
            # Check again after CAPTCHA handling
            if "captcha" not in driver.page_source.lower() and "security check" not in driver.page_source.lower():
                print("✓ CAPTCHA solved, proceeding with extraction")
                is_profile_page = True
        elif "not found" in driver.page_source.lower() or "404" in driver.page_source:
            print("⚠️ Profile not found (404 error)")
        elif "privacy" in driver.page_source.lower() or "cookie" in driver.page_source.lower():
            print("⚠️ On policy page instead of profile, attempting to click through")
            try:
                accept_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Agree') or contains(text(), 'Continue')]")
                if accept_buttons:
                    accept_buttons[0].click()
                    print("Clicked accept/agree button")
                    time.sleep(2)
                    # Refresh page and retry
                    driver.get(url)
                    time.sleep(3)
                    is_profile_page = True
            except:
                pass
                
    # For debugging - log current page title
    print(f"Current page title: '{driver.title}'") 
    
    # Continue anyway - we'll still try to extract data even if detection is uncertain
    
    try:
        
        # REMOVE JS OPTIMIZATION - Go back to explicitly clicking 'Show' buttons with Selenium
        # This is more reliable than the JS-only approach
        
        # Start timing data extraction
        extraction_start = timing_module.time()
        
        # Take screenshot before clicking buttons
        driver.save_screenshot(f"before_click_{url.split('/')[-1]}.png")
        
        # Find all 'Show' buttons - try multiple selectors for better coverage
        show_buttons = []
        show_button_selectors = [
            "a.text-secondary.fw-bold.text-decoration-none",  # Primary selector
            "a[data-action*='unobfuscate-details#revealUnobfuscatedContent']",  # Data action attribute
            "a.fw-bold[href='javascript:void(0)']"  # Generic fallback
            # Note: "a:contains('Show')" is not valid CSS, we'll use XPath for text-based search instead
        ]
        
        # Try each selector and combine unique results
        for selector in show_button_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if buttons:
                    print(f"Found {len(buttons)} Show buttons with selector: {selector}")
                    # Add only new buttons (avoid duplicates)
                    for btn in buttons:
                        if btn not in show_buttons:
                            show_buttons.append(btn)
            except Exception as e:
                print(f"Error finding buttons with selector '{selector}': {e}")
        
        # Also try XPath as fallback
        try:
            xpath_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Show')]")
            if xpath_buttons:
                print(f"Found {len(xpath_buttons)} Show buttons with XPath text search")
                # Add only new buttons (avoid duplicates)
                for btn in xpath_buttons:
                    if btn not in show_buttons:
                        show_buttons.append(btn)
        except Exception as e:
            print(f"Error finding buttons with XPath: {e}")
        
        print(f"Found total of {len(show_buttons)} unique Show buttons to click...")
        
        # Take screenshot with buttons highlighted if possible
        if show_buttons:
            try:
                # Highlight buttons for debugging
                driver.execute_script("""
                    arguments[0].forEach(function(btn) {
                        btn.style.border = '3px solid red';
                        btn.style.backgroundColor = 'yellow';
                    });
                """, show_buttons)
                driver.save_screenshot(f"show_buttons_highlighted_{url.split('/')[-1]}.png")
            except:
                pass
        else:
            print("⚠️ No Show buttons found - saving page for analysis")
            driver.save_screenshot(f"no_show_buttons.png")
            with open(f"no_show_buttons_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        
        # Click each button individually
        for i, btn in enumerate(show_buttons):
            try:
                # First scroll to ensure button is visible
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.2)  # Short pause after scrolling
                
                # Click the button
                text_before = btn.text
                btn.click()
                print(f"Clicked {text_before} button ({i+1}/{len(show_buttons)})")
                time.sleep(0.5)  # Wait for content to appear or CAPTCHA to load
                
                # Check if a CAPTCHA iframe or modal appeared - more comprehensive detection
                try:
                    # Look for all iframes first - broader approach
                    all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    challenge_iframe = None
                    
                    if all_iframes:
                        print(f"Found {len(all_iframes)} iframes after clicking button {i+1}")
                        
                        # Check each iframe to find the CAPTCHA one
                        for idx, iframe in enumerate(all_iframes):
                            try:
                                iframe_src = iframe.get_attribute("src") or ""
                                iframe_class = iframe.get_attribute("class") or ""
                                
                                print(f"  iframe {idx}: src='{iframe_src}', class='{iframe_class}'")
                                
                                # Match any iframe that looks like a CAPTCHA challenge
                                if ('challenge' in iframe_src.lower() or 
                                    'captcha' in iframe_src.lower() or 
                                    'fancybox' in iframe_class.lower()):
                                    challenge_iframe = iframe
                                    print(f"⚠️ CAPTCHA iframe detected (iframe {idx})")
                                    break
                            except:
                                print(f"Error checking iframe {idx}")
                    
                    # Also check for CAPTCHA text in main page as backup detection method
                    captcha_text_present = ("captcha" in driver.page_source.lower() or 
                                           "security check" in driver.page_source.lower() or
                                           "you're almost there" in driver.page_source.lower())
                    
                    if captcha_text_present and not challenge_iframe:
                        print("CAPTCHA text detected in page but no iframe found")
                        driver.save_screenshot(f"captcha_text_detected_{i}.png")
                    
                    # Process CAPTCHA iframe if found
                    if challenge_iframe:
                        print(f"⚠️ CAPTCHA modal detected after clicking Show button {i+1}")
                        driver.save_screenshot(f"captcha_modal_{i}.png")
                        
                        # Try to switch to the iframe and solve the CAPTCHA
                        try:
                            # Switch to the iframe
                            driver.switch_to.frame(challenge_iframe)
                            print("Successfully switched to CAPTCHA iframe")
                            
                            # Take screenshot inside the iframe
                            driver.save_screenshot(f"captcha_inside_iframe_{i}.png")
                            
                            # Save page source inside iframe for debugging
                            with open(f"captcha_iframe_source_{i}.html", "w", encoding="utf-8") as f:
                                f.write(driver.page_source)
                            
                            # Try multiple strategies to find CAPTCHA image
                            captcha_img = None
                            
                            # Strategy 1: Direct img tag
                            try:
                                captcha_img = driver.find_element(By.TAG_NAME, "img")
                                print(f"Found CAPTCHA image with direct img tag: {captcha_img.get_attribute('src')}")
                            except:
                                print("No img tag found, trying alternative selectors")
                            
                            # Strategy 2: Any image with certain attributes or contexts
                            if not captcha_img:
                                img_selectors = [
                                    "img[src*='captcha']",
                                    "img[alt*='captcha']",
                                    "img[alt*='security']",
                                    "img.captcha"
                                ]
                                
                                for selector in img_selectors:
                                    try:
                                        captcha_img = driver.find_element(By.CSS_SELECTOR, selector)
                                        print(f"Found CAPTCHA image with selector '{selector}': {captcha_img.get_attribute('src')}")
                                        break
                                    except:
                                        pass
                            
                            # Strategy 3: Look for image within divs containing CAPTCHA-related text
                            if not captcha_img:
                                try:
                                    # Find divs with CAPTCHA-related text
                                    captcha_divs = driver.find_elements(By.XPATH, 
                                                                      "//*[contains(text(), 'CAPTCHA') or contains(text(), 'captcha') or contains(text(), 'security')]")
                                    
                                    for div in captcha_divs:
                                        try:
                                            potential_img = div.find_element(By.TAG_NAME, "img")
                                            captcha_img = potential_img
                                            print(f"Found CAPTCHA image within text context: {captcha_img.get_attribute('src')}")
                                            break
                                        except:
                                            pass
                                except:
                                    pass
                            
                            # Final image debug
                            if captcha_img:
                                driver.save_screenshot(f"captcha_image_found_{i}.png")
                            else:
                                print("No CAPTCHA image found with any method")
                            
                            # Try multiple methods to find input field
                            input_field = None
                            
                            # Strategy 1: Direct input tag
                            try:
                                input_field = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                                print("Found CAPTCHA input field with direct selector")
                            except:
                                print("No text input found, trying alternatives")
                            
                            # Strategy 2: Various input selectors
                            if not input_field:
                                input_selectors = [
                                    "input.form-control",
                                    "input[name='response']",
                                    "input[id*='captcha']",
                                    "input[placeholder*='enter']",
                                    "input:not([type='hidden'])"  # Any non-hidden input as last resort
                                ]
                                
                                for selector in input_selectors:
                                    try:
                                        input_field = driver.find_element(By.CSS_SELECTOR, selector)
                                        print(f"Found input field with selector '{selector}'")
                                        break
                                    except:
                                        pass
                            
                            # Only if we have both image and input, try to solve
                            if captcha_img and input_field:
                                try:
                                    # Save CAPTCHA image locally with direct screenshot method
                                    captcha_filename = f"captcha_{i}.png"
                                    with open(captcha_filename, "wb") as f:
                                        f.write(captcha_img.screenshot_as_png)
                                    print(f"Saved CAPTCHA to {captcha_filename}")
                                    
                                    # Use 2Captcha to solve it directly
                                    from profile_finder import solve_captcha_with_2captcha_imagetotext
                                    captcha_text = solve_captcha_with_2captcha_imagetotext(captcha_filename)
                                    
                                    if captcha_text:
                                        print(f"CAPTCHA solution: '{captcha_text}'")
                                        
                                        # Enter the solution
                                        input_field.clear()
                                        input_field.send_keys(captcha_text)
                                        time.sleep(0.5)
                                        
                                        # Find and click submit button - try multiple methods
                                        submit_btn = None
                                        submit_selectors = [
                                            "button[type='submit']",
                                            "button.btn-primary",
                                            "button.btn-submit",
                                            "button:contains('Submit')",
                                            "button:contains('Verify')",
                                            "button:contains('Unlock')",
                                            "input[type='submit']"
                                        ]
                                        
                                        for selector in submit_selectors:
                                            try:
                                                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                                                print(f"Found submit button with selector '{selector}'")
                                                break
                                            except:
                                                pass
                                        
                                        # If no button found by CSS, try XPath with text
                                        if not submit_btn:
                                            submit_xpaths = [
                                                "//button[contains(text(), 'Submit')]",
                                                "//button[contains(text(), 'Verify')]",
                                                "//button[contains(text(), 'Unlock')]",
                                                "//input[@type='submit']"
                                            ]
                                            
                                            for xpath in submit_xpaths:
                                                try:
                                                    submit_btn = driver.find_element(By.XPATH, xpath)
                                                    print(f"Found submit button with XPath '{xpath}'")
                                                    break
                                                except:
                                                    pass
                                        
                                        # Click the submit button if found
                                        if submit_btn:
                                            driver.save_screenshot(f"before_submit_captcha_{i}.png")
                                            submit_btn.click()
                                            print("Clicked submit button for CAPTCHA solution")
                                            time.sleep(2)  # Wait for submission
                                            driver.save_screenshot(f"after_submit_captcha_{i}.png")
                                        else:
                                            # As last resort, try pressing Enter on the input field
                                            print("No submit button found, trying Enter key")
                                            input_field.send_keys("\n")
                                            time.sleep(2)
                                    else:
                                        print("Failed to get CAPTCHA solution from 2Captcha")
                                except Exception as solve_e:
                                    print(f"Error solving CAPTCHA: {solve_e}")
                            else:
                                print("Missing required CAPTCHA elements (image or input field)")
                                
                            # Switch back to main content
                            driver.switch_to.default_content()
                            print("Switched back to main content")
                            
                            # Wait a bit to see if CAPTCHA was solved
                            time.sleep(2)
                        except Exception as iframe_e:
                            print(f"Error handling iframe CAPTCHA: {iframe_e}")
                            # Switch back to main frame just in case
                            driver.switch_to.default_content()
                    else:
                        # Check for any visible CAPTCHA elements in main frame
                        captcha_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'CAPTCHA') or contains(text(), 'captcha') or contains(text(), 'security check')]")
                        if captcha_elements:
                            print(f"CAPTCHA text found in main page after clicking button {i+1}")
                            driver.save_screenshot(f"captcha_in_main_{i}.png")
                except Exception as detect_e:
                    print(f"Error detecting CAPTCHA: {detect_e}")
                    # No CAPTCHA iframe found, continue normally
            except Exception as e:
                print(f"Error clicking Show button: {e}")
                # Try JavaScript click as fallback
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    print("Clicked with JavaScript instead")
                    time.sleep(0.5)
                    
                    # Also check for CAPTCHA after JavaScript click - use improved detection
                    try:
                        # Look for all iframes - more comprehensive approach
                        all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        challenge_iframe = None
                        
                        if all_iframes:
                            print(f"Found {len(all_iframes)} iframes after JS clicking button {i+1}")
                            
                            # Check each iframe to find the CAPTCHA one
                            for idx, iframe in enumerate(all_iframes):
                                try:
                                    iframe_src = iframe.get_attribute("src") or ""
                                    iframe_class = iframe.get_attribute("class") or ""
                                    
                                    print(f"  iframe {idx} after JS click: src='{iframe_src}', class='{iframe_class}'")
                                    
                                    # Match any iframe that looks like a CAPTCHA challenge
                                    if ('challenge' in iframe_src.lower() or 
                                        'captcha' in iframe_src.lower() or 
                                        'fancybox' in iframe_class.lower()):
                                        challenge_iframe = iframe
                                        print(f"⚠️ CAPTCHA iframe detected after JS click (iframe {idx})")
                                        break
                                except:
                                    pass
                        
                        # Also check for CAPTCHA text in main page as backup
                        captcha_text_present = ("captcha" in driver.page_source.lower() or 
                                               "security check" in driver.page_source.lower() or
                                               "you're almost there" in driver.page_source.lower())
                        
                        if captcha_text_present and not challenge_iframe:
                            print("CAPTCHA text detected after JS click but no iframe found")
                            driver.save_screenshot(f"captcha_text_js_click_{i}.png")
                            
                        # Process CAPTCHA iframe if found
                        if challenge_iframe:
                            print(f"⚠️ CAPTCHA modal detected after JS clicking button {i+1}")
                            driver.save_screenshot(f"captcha_modal_js_{i}.png")
                            
                            # Try to switch to the iframe and solve the CAPTCHA
                            try:
                                # Switch to the iframe
                                driver.switch_to.frame(challenge_iframe)
                                print("Successfully switched to CAPTCHA iframe after JS click")
                                
                                # Take screenshot inside the iframe
                                driver.save_screenshot(f"captcha_inside_iframe_js_{i}.png")
                                
                                # Save page source inside iframe for debugging
                                with open(f"captcha_iframe_source_js_{i}.html", "w", encoding="utf-8") as f:
                                    f.write(driver.page_source)
                                
                                # Try multiple strategies to find CAPTCHA image
                                captcha_img = None
                                
                                # Strategy 1: Direct img tag
                                try:
                                    captcha_img = driver.find_element(By.TAG_NAME, "img")
                                    print(f"Found CAPTCHA image with direct img tag after JS click: {captcha_img.get_attribute('src')}")
                                except:
                                    print("No img tag found after JS click, trying alternative selectors")
                                
                                # Strategy 2: Any image with certain attributes or contexts
                                if not captcha_img:
                                    img_selectors = [
                                        "img[src*='captcha']",
                                        "img[alt*='captcha']",
                                        "img[alt*='security']",
                                        "img.captcha"
                                    ]
                                    
                                    for selector in img_selectors:
                                        try:
                                            captcha_img = driver.find_element(By.CSS_SELECTOR, selector)
                                            print(f"Found CAPTCHA image with selector '{selector}' after JS click")
                                            break
                                        except:
                                            pass
                                
                                # Strategy 3: Look for image within divs containing CAPTCHA-related text
                                if not captcha_img:
                                    try:
                                        # Find divs with CAPTCHA-related text
                                        captcha_divs = driver.find_elements(By.XPATH, 
                                                                          "//*[contains(text(), 'CAPTCHA') or contains(text(), 'captcha') or contains(text(), 'security')]")
                                        
                                        for div in captcha_divs:
                                            try:
                                                potential_img = div.find_element(By.TAG_NAME, "img")
                                                captcha_img = potential_img
                                                print(f"Found CAPTCHA image within text context after JS click")
                                                break
                                            except:
                                                pass
                                    except:
                                        pass
                                
                                # Final image debug
                                if captcha_img:
                                    driver.save_screenshot(f"captcha_image_found_js_{i}.png")
                                else:
                                    print("No CAPTCHA image found with any method after JS click")
                                
                                # Try multiple methods to find input field
                                input_field = None
                                
                                # Strategy 1: Direct input tag
                                try:
                                    input_field = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                                    print("Found CAPTCHA input field with direct selector after JS click")
                                except:
                                    print("No text input found after JS click, trying alternatives")
                                
                                # Strategy 2: Various input selectors
                                if not input_field:
                                    input_selectors = [
                                        "input.form-control",
                                        "input[name='response']",
                                        "input[id*='captcha']",
                                        "input[placeholder*='enter']",
                                        "input:not([type='hidden'])"  # Any non-hidden input as last resort
                                    ]
                                    
                                    for selector in input_selectors:
                                        try:
                                            input_field = driver.find_element(By.CSS_SELECTOR, selector)
                                            print(f"Found input field with selector '{selector}' after JS click")
                                            break
                                        except:
                                            pass
                                
                                # Only if we have both image and input, try to solve
                                if captcha_img and input_field:
                                    try:
                                        # Save CAPTCHA image locally with direct screenshot method
                                        captcha_filename = f"captcha_js_{i}.png"
                                        with open(captcha_filename, "wb") as f:
                                            f.write(captcha_img.screenshot_as_png)
                                        print(f"Saved CAPTCHA to {captcha_filename}")
                                        
                                        # Use 2Captcha to solve it directly
                                        from profile_finder import solve_captcha_with_2captcha_imagetotext
                                        captcha_text = solve_captcha_with_2captcha_imagetotext(captcha_filename)
                                        
                                        if captcha_text:
                                            print(f"CAPTCHA solution after JS click: '{captcha_text}'")
                                            
                                            # Enter the solution
                                            input_field.clear()
                                            input_field.send_keys(captcha_text)
                                            time.sleep(0.5)
                                            
                                            # Find and click submit button - try multiple methods
                                            submit_btn = None
                                            submit_selectors = [
                                                "button[type='submit']",
                                                "button.btn-primary",
                                                "button.btn-submit",
                                                "input[type='submit']"
                                            ]
                                            
                                            for selector in submit_selectors:
                                                try:
                                                    submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                                                    print(f"Found submit button with selector '{selector}' after JS click")
                                                    break
                                                except:
                                                    pass
                                            
                                            # If no button found by CSS, try XPath with text
                                            if not submit_btn:
                                                submit_xpaths = [
                                                    "//button[contains(text(), 'Submit')]",
                                                    "//button[contains(text(), 'Verify')]",
                                                    "//button[contains(text(), 'Unlock')]",
                                                    "//input[@type='submit']"
                                                ]
                                                
                                                for xpath in submit_xpaths:
                                                    try:
                                                        submit_btn = driver.find_element(By.XPATH, xpath)
                                                        print(f"Found submit button with XPath '{xpath}' after JS click")
                                                        break
                                                    except:
                                                        pass
                                            
                                            # Click the submit button if found
                                            if submit_btn:
                                                driver.save_screenshot(f"before_submit_captcha_js_{i}.png")
                                                submit_btn.click()
                                                print("Clicked submit button for CAPTCHA solution after JS click")
                                                time.sleep(2)  # Wait for submission
                                                driver.save_screenshot(f"after_submit_captcha_js_{i}.png")
                                            else:
                                                # As last resort, try pressing Enter on the input field
                                                print("No submit button found after JS click, trying Enter key")
                                                input_field.send_keys("\n")
                                                time.sleep(2)
                                        else:
                                            print("Failed to get CAPTCHA solution from 2Captcha after JS click")
                                    except Exception as solve_e:
                                        print(f"Error solving CAPTCHA after JS click: {solve_e}")
                                else:
                                    print("Missing required CAPTCHA elements (image or input field) after JS click")
                                    
                                # Switch back to main content
                                driver.switch_to.default_content()
                                print("Switched back to main content after JS click CAPTCHA handling")
                                
                                # Wait to see if CAPTCHA was solved
                                time.sleep(2)
                            except Exception as iframe_js_e:
                                print(f"Error handling iframe CAPTCHA after JS click: {iframe_js_e}")
                                # Switch back to main frame just in case
                                driver.switch_to.default_content()
                    except Exception as captcha_js_e:
                        print(f"Error checking for CAPTCHA after JS click: {captcha_js_e}")
                except:
                    pass
                    
        # Take screenshot after clicking buttons
        driver.save_screenshot(f"after_click_{url.split('/')[-1]}.png")
        
        # Wait a moment for any final elements to load
        time.sleep(0.5)
        
        # Now extract the revealed data using JavaScript
        # This collects all contact information from the revealed elements
        contact_data = driver.execute_script("""
            // Extract all already-revealed contact data
            // Important: We've already clicked all the Show buttons with Selenium
            
            const result = {};
            
            // Function to extract all contact data
            function extractAllContactData() {
                // Don't click any buttons again - they should already be clicked
                // Just focus on extraction
                
                // Extract all data
                const data = {};
                
                // Helper to extract all visible contacts
                document.querySelectorAll("ul.list-style-none.bg-light.p-3.rounded div.row.justify-content-between").forEach(row => {
                    try {
                        const labelEl = row.querySelector("div.col-auto.fw-bold");
                        const valueEl = row.querySelector("div.col-auto.text-end");
                        
                        if (!labelEl || !valueEl) return;
                        
                        // Get label
                        let label = labelEl.textContent.trim().toLowerCase();
                        if (label.includes("(formerly twitter)")) label = "twitter";
                        
                        // Get value
                        let value = null;
                        
                        // Is this a field that needs the "Show" button clicked?
                        const hasShowButton = valueEl.querySelector("a[data-action*='unobfuscate-details#revealUnobfuscatedContent']");
                        
                        if (hasShowButton) {
                            // For fields with Show buttons, only accept values from the revealed span
                            const span = valueEl.querySelector("span[data-unobfuscate-details-target='output']");
                            if (span && !span.textContent.includes('●')) {
                                value = span.textContent.trim();
                            }
                            // Don't use link.href or any other fallback for these fields
                        } else {
                            // For normal fields (without Show buttons), use normal extraction
                            const span = valueEl.querySelector("span[data-unobfuscate-details-target='output']");
                            if (span && !span.textContent.includes('●')) {
                                value = span.textContent.trim();
                            } else {
                                // Only use link.href for social media links, not for email/phone
                                const link = valueEl.querySelector("a");
                                if (link && !label.includes("email") && !label.includes("mobile") && 
                                    !label.includes("phone") && !label.includes("whatsapp")) {
                                    value = link.href;
                                } else {
                                    // Plain text
                                    const text = valueEl.textContent.trim();
                                    if (!text.includes('●') && text.length > 2) {
                                        value = text;
                                    }
                                }
                            }
                        }
                        
                        if (value) data[label] = value;
                    } catch(e) {}
                });
                
                // Also extract direct social links
                const socialPlatforms = ['onlyfans.com', 'instagram.com', 'twitter.com', 'x.com', 'fansly.com'];
                document.querySelectorAll('a[href]').forEach(link => {
                    try {
                        const href = link.href;
                        for (const platform of socialPlatforms) {
                            if (href.includes(platform)) {
                                // Determine platform type
                                let type = platform.split('.')[0];
                                if (platform === 'x.com') type = 'twitter';
                                
                                // Add to data
                                if (!data[type]) data[type] = href;
                                break;
                            }
                        }
                    } catch(e) {}
                });
                
                return data;
            }
            
            // Run the extraction
            return extractAllContactData();
        """)
        
        # For debugging
        print(f"Extracted contact data via JavaScript: {contact_data}")
        
        # Check for special flags from JavaScript extraction
        if contact_data and contact_data.get("_CAPTCHA_DETECTED"):
            print("⚠️ CAPTCHA detected during Show button clicks!")
            driver.save_screenshot("captcha_during_extraction.png")
            
            # Try to handle the CAPTCHA
            print("Attempting to solve CAPTCHA that appeared during extraction...")
            handle_captcha(driver)
            
            # Try extraction again
            print("Retrying data extraction after CAPTCHA...")
            contact_data = driver.execute_script("""
                // Extract only data - don't try to click buttons again
                const data = {};
                
                // Extract visible contact info
                document.querySelectorAll("ul.list-style-none.bg-light.p-3.rounded div.row.justify-content-between").forEach(row => {
                    try {
                        const labelEl = row.querySelector("div.col-auto.fw-bold");
                        const valueEl = row.querySelector("div.col-auto.text-end");
                        
                        if (!labelEl || !valueEl) return;
                        
                        // Get label and value
                        let label = labelEl.textContent.trim().toLowerCase();
                        if (label.includes("(formerly twitter)")) label = "twitter";
                        
                        // Try to get revealed value
                        const span = valueEl.querySelector("span[data-unobfuscate-details-target='output']");
                        if (span && !span.textContent.includes('●')) {
                            data[label] = span.textContent.trim();
                        }
                    } catch(e) {}
                });
                
                // Extract social links
                const socialPlatforms = ['onlyfans.com', 'instagram.com', 'twitter.com', 'x.com', 'fansly.com'];
                document.querySelectorAll('a[href]').forEach(link => {
                    try {
                        const href = link.href;
                        for (const platform of socialPlatforms) {
                            if (href.includes(platform)) {
                                let type = platform.split('.')[0];
                                if (platform === 'x.com') type = 'twitter';
                                if (!data[type]) data[type] = href;
                                break;
                            }
                        }
                    } catch(e) {}
                });
                
                return data;
            """)
            print(f"After CAPTCHA handling, extracted: {contact_data}")
        
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
        if contact_data and not contact_data.get("_ERROR"):
            for js_field, value in contact_data.items():
                # Skip special keys that start with _
                if js_field.startswith("_"):
                    continue
                    
                for key, data_field in field_mapping.items():
                    if key in js_field:
                        data[data_field] = value
                        print(f"✓ Saved {data_field}: {value}")
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

def scrape_single_profile(url, use_visible_browser=False):
    """Scrape a single profile URL."""
    # Check if already scraped
    scraped_urls = load_scraped_urls()
    if url in scraped_urls:
        print(f"Profile {url} has already been scraped. Skipping.")
        return
    
    # Initialize driver and CSV
    driver = initialize_driver(headless=False, prevent_focus=(not use_visible_browser))
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
    """Apply extreme optimizations to the driver for maximum performance."""
    # Set aggressive timeouts for faster responses
    driver.set_page_load_timeout(15)   # Reduced timeout for faster operation
    driver.set_script_timeout(5)       # Faster script execution timeout
    
    # Disable unnecessary features via JavaScript for extreme speed
    driver.execute_script("""
        // Disable animations completely
        const style = document.createElement('style');
        style.innerHTML = `
            * {
                animation: none !important;
                transition: none !important;
                animation-duration: 0s !important;
                transition-duration: 0s !important;
            }
        `;
        document.head.appendChild(style);
        
        // Disable image loading for speed
        document.querySelectorAll('img').forEach(img => {
           img.style.display = 'none';
           img.setAttribute('loading', 'lazy');
        });
        
        // Disable all event listeners that might cause delays
        document.addEventListener = function() {};
        window.addEventListener = function() {};
        
        // Prevent expensive reflows
        document.body.style.contain = 'strict';
    """)
    
    return driver

def scrape_profile_worker(url, use_visible_browser=False):
    """Worker function for parallel processing to scrape a single profile."""
    # Create a new driver instance for this thread
    driver = initialize_driver(headless=False, prevent_focus=(not use_visible_browser))
    
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

def scrape_from_url_file(url_file="profile_urls.txt", limit=None, start_index=0, max_workers=4, use_visible_browser=False):
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
                # More efficient future handling with as_completed - pass visibility setting
                future_to_url = {executor.submit(scrape_profile_worker, url, use_visible_browser): (i, url) for i, url in batch_urls}
                
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
    print("  --workers=N        Number of parallel workers (default: 16, set to 1 for serial processing)")
    print("  --batch-size=N     Number of profiles to process in each batch (default: 200)")
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
    prevent_focus = True   # Default to invisible mode
    fully_visible = False  # Default to not fully visible
    workers = 16           # Extreme parallelization: 16 workers by default
    batch_size = 200       # Increased batch size for efficiency
    
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
        elif arg == "--fully-visible":
            fully_visible = True
            prevent_focus = False
            print("Using FULLY VISIBLE browser mode for debugging")
        elif arg == "--visible":
            prevent_focus = False
            print("Using FULLY VISIBLE browser mode - this WILL show the browser window")
        elif arg == "--invisible":
            prevent_focus = True
            fully_visible = False
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
    
    # Override initialize_driver to support visible/invisible mode toggle
    from profile_finder import initialize_driver as original_init_driver
    
    # Create a simplified initializer that respects the visibility flag
    def initialize_driver(headless=False, prevent_focus=True):
        """Initialize Chrome driver with visibility based on prevent_focus setting"""
        
        # Install chromedriver using autoinstaller
        chromedriver_path = chromedriver_autoinstaller.install()
        print(f"Using chromedriver from: {chromedriver_path}")
        
        # Set up Chrome options
        options = Options()
        
        # Apply visibility settings based on --visible flag
        if not prevent_focus:
            # VISIBLE MODE - NO HEADLESS OPTIONS AT ALL
            print("\n🖥️ Creating VISIBLE browser - window will appear on screen\n")
            # Only basic window settings
            options.add_argument("--start-maximized")
        else:
            # Invisible mode with headless=new (better rendering)
            print("Creating invisible headless browser")
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        
        # Common options for all modes
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # Create driver with explicit service
        try:
            driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
            if not prevent_focus:
                print("✓ VISIBLE Chrome browser created successfully")
            return driver
        except Exception as e:
            print(f"Error creating Chrome driver: {e}")
            raise
    
    # Replace the function
    globals()['initialize_driver'] = initialize_driver
    
    # Run the scraper
    if url:
        print(f"Scraping single profile: {url}")
        scrape_single_profile(url, use_visible_browser=(not prevent_focus))
    else:
        print(f"Scraping profiles from file: {url_file}")
        print(f"Starting from index: {start_index}")
        print(f"Using {workers} parallel worker{'s' if workers > 1 else ''}")
        print(f"Using batch size of {batch_size}")
        
        # Update scrape_from_url_file to accept batch_size and pass visibility setting
        # Using a wrapper function to maintain backward compatibility
        def scrape_with_batch_size(url_file, limit, start_index, workers):
            # Modify the batch_size in the function and pass visibility
            global batch_size
            use_visible_mode = not prevent_focus
            scrape_from_url_file(url_file, limit, start_index, workers, use_visible_browser=use_visible_mode)
            
        scrape_with_batch_size(url_file, limit, start_index, workers)

if __name__ == "__main__":
    main()