#!/usr/bin/env python3
"""
Test script to verify CAPTCHA detection and solving with the configured API keys.
This will directly access Tryst.link and attempt to solve any CAPTCHAs it encounters.
"""

import time
from selenium.webdriver.common.by import By
from scraper import (
    initialize_driver, 
    solve_captcha, 
    TWOCAPTCHA_API_KEY
)

def main():
    print("=" * 60)
    print("CAPTCHA Solving Test for Tryst.link")
    print("=" * 60)
    
    # Parse arguments
    import sys
    prevent_focus = "--visible" not in sys.argv
    
    # Display configured API key (masked for security)
    print("\nConfigured API Key:")
    print(f"2Captcha: {'*' * (len(TWOCAPTCHA_API_KEY) - 8) + TWOCAPTCHA_API_KEY[-8:]}")
    
    print("\nInitializing Chrome driver...")
    if prevent_focus:
        print("Using enhanced visibility headless mode (won't steal focus)")
        driver = initialize_driver(headless=False, prevent_focus=True)
    else:
        print("Using fully visible browser mode (may steal focus)")
        driver = initialize_driver(headless=False, prevent_focus=False)
    
    try:
        # First test: Direct access to search page (which often has CAPTCHA)
        print("\nTest 1: Accessing search page...")
        driver.get("https://tryst.link/search?loc=%3AAnywhere&within=50km&trans=false&q=")
        time.sleep(3)  # Give the page time to load
        
        # Take screenshot before attempting CAPTCHA solving
        driver.save_screenshot("before_captcha_solving.png")
        print("Screenshot saved to 'before_captcha_solving.png'")
        
        print("\nAttempting to detect and solve any CAPTCHA...")
        result = solve_captcha(driver)
        
        if result:
            print("CAPTCHA solving reported success!")
        else:
            print("CAPTCHA solving failed.")
        
        # Take screenshot after CAPTCHA solving attempt
        driver.save_screenshot("after_captcha_solving.png")
        print("Screenshot saved to 'after_captcha_solving.png'")
        
        # Check if search results are visible
        time.sleep(5)  # Wait for page to fully load after CAPTCHA
        try:
            escort_links = driver.find_elements(By.XPATH, '//a[contains(@href, "/escort/")]')
            if escort_links:
                print(f"\nSuccess! Found {len(escort_links)} escort links on the page.")
                print("CAPTCHA has been successfully bypassed.")
            else:
                print("\nNo escort links found on the page.")
                print("CAPTCHA may still be blocking access or page structure has changed.")
        except Exception as e:
            print(f"\nError checking for escort links: {e}")
    
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        print("\nTest completed. Check the screenshots to verify results.")
        input("Press Enter to close the browser and exit...")
        driver.quit()

if __name__ == "__main__":
    main() 