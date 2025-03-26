# Tryst.link Scraper

A clean, minimal, and reliable scraper for Tryst.link profiles that can handle CAPTCHAs, reveal hidden information, and save data to CSV. The scraper is split into two parts for better flexibility and reliability.

## Features

- Two-part scraping process for improved flexibility:
  1. Profile Finder: Collects all profile URLs from search pages
  2. Profile Scraper: Extracts detailed information from individual profiles
- Handles text-based image CAPTCHAs using:
  - 2Captcha as the automated service
  - Manual solving as fallback
- Handles age verification prompts automatically
- Reveals and extracts hidden emails
- Collects contact information:
  - Emails (hidden behind "Show Email" button)
  - Website links
  - OnlyFans links
  - Twitter/X accounts
  - Instagram accounts
- Saves data to CSV
- Tracks scraped URLs to avoid duplicates
- Handles interruptions gracefully
- Error handling to prevent crashes

## Requirements

- Python 3.6+
- Chrome browser
- 2Captcha API key

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/tryst-scraper.git
   cd tryst-scraper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the scraper:
   - Open `profile_finder.py` and add your API key:
     ```python
     TWOCAPTCHA_API_KEY = "YOUR_2CAPTCHA_API_KEY_HERE"
     ```
   - If you don't have an API key, the scraper will fall back to manual CAPTCHA solving

## Usage

### Step 1: Find Profile URLs

First, run the profile finder to collect all profile URLs:

```bash
python profile_finder.py
```

This will:
- Load the search page
- Solve any CAPTCHAs that appear
- Scroll through all results to load all profiles
- Save profile URLs to `profile_urls.txt`

### Step 2: Scrape Individual Profiles

Once you have collected profile URLs, use the profile scraper to extract detailed information:

```bash
python profile_scraper.py
```

This will:
- Read URLs from `profile_urls.txt`
- Visit each profile page
- Extract hidden email addresses and other contact information
- Save data to `profile_data.csv`
- Track scraped URLs in `scraped_urls.txt` to avoid duplicates

### Additional Options for Profile Scraper

You can customize the profile scraper with command-line options:

```bash
# Scrape a single specific profile URL
python profile_scraper.py --url=https://tryst.link/escort/example

# Use a different file for profile URLs
python profile_scraper.py --file=my_urls.txt

# Limit the number of profiles to scrape (useful for testing)
python profile_scraper.py --limit=5

# Show help
python profile_scraper.py --help
```

## Customization

### Running in Headless Mode

To run in headless mode (no visible browser), modify the `initialize_driver` call in either script:

```python
driver = initialize_driver(headless=True)
```

### Adjusting CAPTCHA Solving

The scraper is set up to handle the text-based image CAPTCHAs on Tryst.link. It will:
1. First attempt to solve using Capsolver's ImageToText API
2. If automated solving fails, fall back to manual intervention

## CAPTCHA Handling

The scraper uses a specialized approach for handling Tryst.link's text-based CAPTCHA:
1. Detects the "You're Almost There" page
2. Takes a screenshot of the CAPTCHA
3. Uses 2Captcha's ImageToText API for automated solving
4. Falls back to manual intervention if automated service fails

## Notes

- The scripts are set to run with a visible browser by default to allow for manual CAPTCHA solving if needed
- Random delays between profile scrapes help avoid being blocked
- If the site's structure changes, you may need to update the selectors in the `scrape_profile()` function
- The scraper respects the site's structure and doesn't attempt to bypass legitimately hidden information

## License

MIT

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with Tryst.link's terms of service.