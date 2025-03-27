#!/usr/bin/env python3

"""
Test script to create a VISIBLE Chrome browser without ANY headless settings.
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import chromedriver_autoinstaller

print("This script will open a VISIBLE Chrome browser")

# Install chromedriver matching your Chrome version
chromedriver_path = chromedriver_autoinstaller.install()
print(f"Using chromedriver from: {chromedriver_path}")

# Set up options with NO HEADLESS settings
options = Options()
options.add_argument("--start-maximized")

# Create Chrome browser
driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

try:
    print("Opening browser to test page...")
    driver.get("https://www.google.com")
    
    print("Browser should be VISIBLE now")
    print("Waiting 20 seconds...")
    time.sleep(20)
    
    print("Taking screenshot...")
    driver.save_screenshot("visible_test.png")
    
finally:
    print("Closing browser")
    driver.quit()