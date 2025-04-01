# Tryst.link Profile Scraper

A high-performance web scraper for extracting contact information from Tryst.link escort profiles, designed to handle rate limiting, CAPTCHAs, and "Show" buttons that hide contact information.

## Features

- **Efficient Data Extraction**: Automatically extracts name, email, phone, and social media links
- **Click "Show" Buttons**: Automatically reveals hidden contact information
- **Parallel Processing**: Scales to handle 30,000+ profiles with concurrent workers
- **CAPTCHA Handling**: Uses Bright Data Scraping Browser to automatically solve CAPTCHAs
- **Retry Mechanism**: Implements exponential backoff for failed requests
- **Resumable Jobs**: Tracks progress and can continue from previous runs
- **Detailed Logging**: Provides comprehensive logs and statistics

## Requirements

- Python 3.8+
- Bright Data account with Scraping Browser access
- Required Python packages listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/tryst-scraper.git
   cd tryst-scraper
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up Bright Data credentials as environment variables:
   ```
   export BRIGHT_DATA_CUSTOMER_ID="your-customer-id"
   export BRIGHT_DATA_ZONE="scraping_browser1"
   export BRIGHT_DATA_PASSWORD="your-zone-password"
   ```

## Usage

### Basic Usage

```
python scraper.py --urls profile_urls.txt --output profile_data.csv
```

### Command Line Options

- `--urls`, `-u`: File containing profile URLs to scrape (default: profile_urls.txt)
- `--output`, `-o`: Output CSV file for scraped data (default: profile_data.csv)
- `--tracked`, `-t`: File to track scraped URLs (default: scraped_urls.txt)
- `--batch-size`, `-b`: Number of URLs to process in each batch (default: 100)
- `--workers`, `-w`: Maximum number of concurrent workers (default: 20)
- `--debug`, `-d`: Enable debug logging
- `--test`: Run in test mode (only process 5 URLs)
- `--continue`: Continue from last run

### Example Usages

Test with a small batch:
```
python scraper.py --test --debug
```

Run with optimized settings for large jobs:
```
python scraper.py --batch-size 200 --workers 50
```

Continue a previously interrupted job:
```
python scraper.py --continue
```

## Output Format

The scraper creates a CSV file with the following columns:

- Profile URL
- Name
- Email
- Phone
- Mobile
- WhatsApp
- Linktree
- Website
- OnlyFans
- Fansly
- Twitter
- Instagram
- Snapchat
- Telegram
- Process Time
- Success (Yes/No)

## Testing

Run the test suite:
```
pytest test_scraper.py
```

## Architecture

The scraper uses a three-tier architecture:

1. **Data Extraction**: Uses Bright Data Scraping Browser to render pages, click buttons, and extract data
2. **Parallel Processing**: Implements asyncio for concurrent requests
3. **Data Storage**: Saves results to CSV with progress tracking

For detailed implementation information, see `Claude.md`.

## Performance Considerations

- **Concurrency**: The default 20 workers is a good starting point, but you may increase to 50+ for faster processing
- **Batch Size**: Larger batches (200-500) improve efficiency but use more memory
- **Rate Limiting**: The scraper handles rate limiting automatically via Bright Data's infrastructure

## License

MIT

## Acknowledgments

This project was designed with help from Claude, an AI assistant by Anthropic.