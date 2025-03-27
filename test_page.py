#!/usr/bin/env python3

from profile_finder import initialize_driver
import time

def main():
    driver = initialize_driver()
    try:
        # Go to a profile page
        print("Loading profile page...")
        driver.get('https://tryst.link/escort/11carmenlove')
        time.sleep(5)
        
        # Take screenshot
        driver.save_screenshot('page_structure.png')
        print("Saved screenshot as page_structure.png")
        
        # Save HTML source
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("Saved HTML source as page_source.html")
        
        # Try to find contact elements
        print("\nLooking for contact elements...")
        
        # Test selector for profile name
        try:
            profile_name = driver.find_element("css selector", "h1.profile-header__name")
            print(f"Profile name found: {profile_name.text}")
        except Exception as e:
            print(f"Profile name NOT found: {e}")
            
        # Test selector for contact rows
        try:
            contact_rows = driver.find_elements("css selector", "ul.list-style-none.bg-light.p-3.rounded div.row.justify-content-between")
            print(f"Found {len(contact_rows)} contact rows")
            
            # Print the first few
            for i, row in enumerate(contact_rows[:3]):
                label_el = row.find_element("css selector", "div.col-auto.fw-bold")
                value_el = row.find_element("css selector", "div.col-auto.text-end")
                label = label_el.text.strip()
                value = value_el.text.strip()
                print(f"  Row {i}: {label} = {value}")
        except Exception as e:
            print(f"Contact rows NOT found: {e}")
            
        # Test selector for unobfuscate buttons
        try:
            show_buttons = driver.find_elements("css selector", 'a[data-action*="unobfuscate-details#revealUnobfuscatedContent"]')
            print(f"Found {len(show_buttons)} 'Show' buttons")
        except Exception as e:
            print(f"Show buttons NOT found: {e}")
        
    finally:
        driver.quit()
        print("Done")

if __name__ == "__main__":
    main()