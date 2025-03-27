#!/usr/bin/env python3
"""
Minimal test script to load a profile and click Show buttons.
"""

import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import chromedriver_autoinstaller

def main():
    # Set up Chrome with simplest possible config - fully visible
    options = Options()
    chromedriver_path = chromedriver_autoinstaller.install()
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)
    
    try:
        # Load a profile page
        profile_url = "https://tryst.link/escort/-1kenziekraves1-"
        print(f"Loading profile: {profile_url}")
        driver.get(profile_url)
        time.sleep(3)
        
        # Log page state
        print(f"Page title: {driver.title}")
        
        # Handle age verification if present
        try:
            age_button = driver.find_element(By.XPATH, '//button[contains(text(), "Agree and close")]')
            if age_button.is_displayed():
                print("Clicking age verification button")
                age_button.click()
                time.sleep(1)
        except Exception as e:
            print(f"No age verification or error: {e}")
            
        # Take a screenshot
        driver.save_screenshot("page_before_action.png")
        
        # Manual handling of CAPTCHA if needed 
        print("If there's a CAPTCHA, please solve it manually within 30 seconds")
        time.sleep(30)  # Wait for manual intervention
        
        # Look for Show buttons in various ways
        print("\nLooking for Show buttons:")
        
        # Method 1: Direct CSS selector
        show_buttons1 = driver.find_elements(By.CSS_SELECTOR, "a.text-secondary.fw-bold.text-decoration-none")
        print(f"1. Found {len(show_buttons1)} buttons with class text-secondary.fw-bold.text-decoration-none")
        
        # Method 2: Data action attribute
        show_buttons2 = driver.find_elements(By.CSS_SELECTOR, 'a[data-action*="unobfuscate-details#revealUnobfuscatedContent"]')
        print(f"2. Found {len(show_buttons2)} buttons with data-action=unobfuscate-details#revealUnobfuscatedContent")
        
        # Method 3: Text content
        show_buttons3 = driver.find_elements(By.XPATH, '//a[contains(text(), "Show")]')
        print(f"3. Found {len(show_buttons3)} buttons containing 'Show' text")
        
        # Take screenshot again
        driver.save_screenshot("page_with_buttons.png")
        
        # Try to click buttons if found
        show_buttons = show_buttons1 if show_buttons1 else (show_buttons2 if show_buttons2 else show_buttons3)
        
        if show_buttons:
            print(f"\nAttempting to click {len(show_buttons)} Show buttons:")
            for i, btn in enumerate(show_buttons):
                # Print button details
                text = btn.text
                html = btn.get_attribute("outerHTML")
                print(f"\nButton {i+1}: Text='{text}', HTML={html}")
                
                try:
                    # First scroll to button to make sure it's visible
                    print(f"Scrolling to button {i+1}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(1)
                    
                    # Take screenshot
                    driver.save_screenshot(f"before_click_button{i+1}.png")
                    
                    # Then click the button
                    print(f"Clicking button {i+1} with Selenium")
                    btn.click()
                    time.sleep(2)
                    
                    # Check for any CAPTCHA or modal
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    if iframes:
                        print(f"⚠️ Found {len(iframes)} iframes after clicking button {i+1}")
                        for j, iframe in enumerate(iframes):
                            iframe_src = iframe.get_attribute("src")
                            print(f"  iframe {j+1} src: {iframe_src}")
                            
                            if "challenge" in iframe_src.lower():
                                print("  This appears to be a CAPTCHA iframe")
                                driver.save_screenshot(f"captcha_after_button{i+1}.png")
                                
                                print("  Waiting 30 seconds for manual CAPTCHA solving...")
                                time.sleep(30)
                except Exception as e:
                    print(f"Error clicking button {i+1} with Selenium: {e}")
                    
                    # Try JavaScript click as fallback
                    try:
                        print(f"Trying JavaScript click for button {i+1}")
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(2)
                        
                        # Check for modal again
                        if driver.find_elements(By.TAG_NAME, "iframe"):
                            print(f"⚠️ Found iframes after JavaScript click on button {i+1}")
                            driver.save_screenshot(f"modal_after_js_click_button{i+1}.png")
                            
                            print("  Waiting 30 seconds for manual handling...")
                            time.sleep(30)
                    except Exception as js_e:
                        print(f"JavaScript click also failed: {js_e}")
                        
                # Take another screenshot after clicking
                driver.save_screenshot(f"after_click_button{i+1}.png")
            
            # Final screenshot after all button clicks
            driver.save_screenshot("final_state.png")
            
            # Check if we successfully extracted any hidden content
            revealed_spans = driver.find_elements(By.CSS_SELECTOR, "span[data-unobfuscate-details-target='output']")
            print(f"\nFound {len(revealed_spans)} revealed content spans:")
            for i, span in enumerate(revealed_spans):
                span_text = span.text.strip()
                print(f"Span {i+1}: '{span_text}'")
        else:
            print("No Show buttons found on the page")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nTest complete. Check the screenshots to see what happened.")
        input("Press Enter to close the browser...")
        driver.quit()

if __name__ == "__main__":
    main()