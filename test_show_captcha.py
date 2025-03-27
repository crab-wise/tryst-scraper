#!/usr/bin/env python3

from profile_finder import initialize_driver, handle_captcha
import time
import random

# List of profile URLs to try
PROFILE_URLS = [
    'https://tryst.link/escort/11carmenlove',
    'https://tryst.link/escort/1122',
    'https://tryst.link/escort/1mistress-storm1',
    'https://tryst.link/escort/007jamesbondgirl',
    'https://tryst.link/escort/007sexybondgirl',
    'https://tryst.link/escort/00heaven',
    'https://tryst.link/escort/0hyped0',
    'https://tryst.link/escort/11111babydoll',
    'https://tryst.link/escort/1lucyluv',
    'https://tryst.link/escort/1stklasstess'
]

def try_profile(driver, url):
    """Try a single profile and check for Show buttons"""
    print(f"\nTrying profile: {url}")
    driver.get(url)
    time.sleep(3)
    
    # Handle age verification popup if present
    if "This website contains adult content" in driver.page_source:
        print("Handling age verification...")
        try:
            agree_btn = driver.find_element("xpath", '//button[contains(text(), "Agree and close")]')
            agree_btn.click()
            time.sleep(1)
        except Exception as e:
            print(f"Error clicking age verification: {e}")
    
    # Handle initial CAPTCHA if present
    if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
        print("Handling initial page CAPTCHA...")
        handle_captcha(driver)
        time.sleep(3)
        
        # Check if we're still on CAPTCHA page
        if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
            print("Failed to solve initial CAPTCHA")
            return False
    
    # Check for profile name to confirm we're on a profile page
    try:
        profile_name = driver.find_element("css selector", "h1.profile-header__name").text
        print(f"Successfully loaded profile: {profile_name}")
    except:
        print("Could not find profile name - page may not have loaded correctly")
    
    # Save screenshot of loaded profile
    driver.save_screenshot(f"profile_{url.split('/')[-1]}.png")
    
    # Look for Show buttons
    show_buttons = driver.find_elements("css selector", 'a[data-action*="unobfuscate-details#revealUnobfuscatedContent"]')
    if not show_buttons:
        print("No 'Show' buttons found on this profile")
        return False
        
    print(f"SUCCESS! Found {len(show_buttons)} 'Show' buttons on profile {url}")
    
    # Click a Show button and monitor what happens
    print("Clicking a 'Show' button...")
    try:
        # Save HTML before click
        with open(f"before_click_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # Click the button
        random_button = random.choice(show_buttons)
        random_button.click()
        time.sleep(2)
        
        # Save state after clicking
        driver.save_screenshot(f"after_show_click_{url.split('/')[-1]}.png")
        with open(f"after_click_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # Check if a CAPTCHA appeared
        if "You're Almost There" in driver.page_source or "security check" in driver.page_source.lower():
            print("CAPTCHA appeared after clicking 'Show'!")
            driver.save_screenshot("show_button_captcha.png")
            return True
        else:
            print("No CAPTCHA appeared after clicking 'Show'")
            
            # Check revealed content
            spans = driver.find_elements("css selector", "span[data-unobfuscate-details-target='output']")
            if spans:
                print(f"Found {len(spans)} revealed content spans:")
                for i, span in enumerate(spans[:3]):
                    print(f"  Span {i}: {span.text}")
            else:
                print("No revealed content spans found")
            
            return True
    except Exception as e:
        print(f"Error clicking Show button: {e}")
        return False

def main():
    driver = initialize_driver()
    try:
        for url in PROFILE_URLS:
            success = try_profile(driver, url)
            if success:
                print(f"Successfully found and tested Show buttons on {url}")
                break
        else:
            print("Could not find any profiles with Show buttons after trying all URLs")
    finally:
        driver.quit()
        print("Done")

if __name__ == "__main__":
    main()