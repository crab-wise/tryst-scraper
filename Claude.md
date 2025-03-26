# Tryst-Scraper Project

## Current Focus
**Currently working with: Profile Scraper (`profile_scraper.py`)**

The Profile Scraper is responsible for extracting detailed information from individual profiles, such as email addresses, websites, and social media links. This is the second step in the two-step process:

1. First, `profile_finder.py` was run to collect profile URLs, which are saved to `profile_urls.txt`
2. Now, `profile_scraper.py` reads these URLs from `profile_urls.txt`, visits each profile page, extracts the relevant information, and saves it to a CSV file (`profile_data.csv`)

## Overview
The Tryst-Scraper is a Python-based web scraping tool designed to extract profile information from Tryst.link, an adult services directory. The scraper is engineered to handle CAPTCHA challenges, age verification prompts, and extract contact information from profiles, including hidden emails that require user interaction to reveal.

## Project Structure
The project follows a two-phase approach to scraping:

1. **Profile Finder** (`profile_finder.py`): Collects all profile URLs from search pages
2. **Profile Scraper** (`profile_scraper.py`): Extracts detailed information from individual profiles

## Main Components

### 1. Profile Finder
This component navigates through search result pages to collect profile URLs.

Key functions:
- `load_all_profiles`: Handles pagination through search results
- `handle_captcha`: Detects and solves CAPTCHAs using third-party services
- `handle_age_verification`: Bypasses age verification prompts
- `extract_profile_links`: Collects profile URLs from pages
- `save_urls`: Stores collected URLs to a text file

### 2. Profile Scraper
This component visits individual profile pages and extracts contact information.

Key functions:
- `scrape_profile`: Extracts data from a profile page
- `reveal_email`: Clicks "Show Email" and waits for unobfuscation
- `save_to_csv`: Stores extracted data in CSV format
- `scrape_from_url_file`: Processes multiple profiles from a file

### 3. CAPTCHA Handling System
The scraper includes a robust CAPTCHA solving system that:
- Uses 2Captcha API for automated solving
- Takes screenshots of CAPTCHA challenges
- Falls back to manual solving when the automated method fails

### 4. Utilities
- `initialize_driver`: Sets up Chrome WebDriver with anti-detection measures
- `load_scraped_urls`: Tracks already processed URLs to avoid duplicates

## Dependencies
- Selenium (WebDriver for browser automation)
- Requests (HTTP library)
- ChromeDriver (for Chrome browser automation)
- Pillow (for image processing related to CAPTCHAs)

## Data Collection
The scraper collects the following information:
- Profile URL
- Name
- Email address (revealed by interacting with the page)
- Website links
- OnlyFans links
- Twitter/X accounts
- Instagram accounts

Data is saved to CSV format for further processing.

## Security and Anti-Detection
The scraper includes several measures to avoid detection:
- Randomized delays between requests
- User-agent spoofing
- Disabling WebDriver flags that could be detected
- Tracking scraped URLs to avoid duplicates

## Usage
The tool is designed to be used sequentially:
1. Run `profile_finder.py` to collect URLs
2. Run `profile_scraper.py` to extract data from those URLs

Additional options for the profile scraper allow for scraping individual URLs, limiting batch size, or using custom URL files.