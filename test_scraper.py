#!/usr/bin/env python3
"""
Test suite for the Tryst.link Scraper
"""

import os
import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, patch, MagicMock
from scraper import TrystScraper

# Test data
TEST_URL = "https://tryst.link/escort/test-profile"
MOCK_BROWSER_ENDPOINT = "wss://test-endpoint"

# Mock response data
MOCK_BROWSER_RESPONSE = {
    "results": [
        True,  # Mock result for age verification
        3,     # Mock result for clicking 3 Show buttons
        {      # Mock extracted data
            "name": "Test Profile",
            "email": "test@example.com",
            "mobile": "+1234567890",
            "onlyfans": "https://onlyfans.com/test-profile",
            "twitter": "https://twitter.com/test-profile"
        }
    ]
}

# Empty temporary files for testing
TEST_CSV = "test_profile_data.csv"
TEST_TRACKED = "test_scraped_urls.txt"

@pytest.fixture
def test_scraper():
    """Create a TrystScraper instance for testing"""
    # Ensure test files are clean
    for f in [TEST_CSV, TEST_TRACKED]:
        if os.path.exists(f):
            os.remove(f)
    
    # Create scraper with test configuration
    scraper = TrystScraper(
        browser_ws_endpoint=MOCK_BROWSER_ENDPOINT,
        save_path=TEST_CSV,
        tracked_urls_path=TEST_TRACKED,
        debug=True
    )
    
    yield scraper
    
    # Clean up after tests
    for f in [TEST_CSV, TEST_TRACKED]:
        if os.path.exists(f):
            os.remove(f)

@pytest.mark.asyncio
async def test_scrape_profile_success(test_scraper):
    """Test successful profile scraping"""
    # Mock the aiohttp ClientSession.post method
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_BROWSER_RESPONSE
    
    with patch('aiohttp.ClientSession.post', return_value=mock_response):
        # Call the method under test
        result = await test_scraper.scrape_profile(TEST_URL)
        
        # Verify results
        assert result["url"] == TEST_URL
        assert result["name"] == "Test Profile"
        assert result["email"] == "test@example.com"
        assert result["mobile"] == "+1234567890"
        assert result["onlyfans"] == "https://onlyfans.com/test-profile"
        assert result["twitter"] == "https://twitter.com/test-profile"
        assert "_process_time" in result
        assert "_error" not in result

@pytest.mark.asyncio
async def test_scrape_profile_error(test_scraper):
    """Test error handling during profile scraping"""
    # Mock an error response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"error": "Test error message"}
    
    with patch('aiohttp.ClientSession.post', return_value=mock_response):
        # Call the method under test
        result = await test_scraper.scrape_profile(TEST_URL)
        
        # Verify error handling
        assert result["url"] == TEST_URL
        assert "_error" in result
        assert "Test error message" in result["_error"]

@pytest.mark.asyncio
async def test_scrape_profile_network_error(test_scraper):
    """Test network error handling"""
    # Mock a network error
    with patch('aiohttp.ClientSession.post', side_effect=aiohttp.ClientError("Network error")):
        # Call the method under test
        result = await test_scraper.scrape_profile(TEST_URL)
        
        # Verify error handling
        assert result["url"] == TEST_URL
        assert "_error" in result
        assert "Network error" in result["_error"]

@pytest.mark.asyncio
async def test_scrape_profile_with_retries(test_scraper):
    """Test retry mechanism"""
    # Mock the scrape_profile method to fail twice then succeed
    original_scrape_profile = test_scraper.scrape_profile
    
    attempt_count = 0
    async def mock_scrape_profile(url):
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 3:
            return {"url": url, "_error": "Network error: Test failure"}
        else:
            # Success on third attempt
            return await original_scrape_profile(url)
    
    # Apply the mock
    test_scraper.scrape_profile = mock_scrape_profile
    
    # Mock successful third attempt
    mock_response = AsyncMock()
    mock_response.json.return_value = MOCK_BROWSER_RESPONSE
    
    with patch('aiohttp.ClientSession.post', return_value=mock_response):
        # Call the method under test
        result = await test_scraper.scrape_profile_with_retries(TEST_URL)
        
        # Verify results
        assert result["url"] == TEST_URL
        assert "_error" not in result
        assert attempt_count == 3  # Verify it took exactly 3 attempts

@pytest.mark.asyncio
async def test_scrape_batch(test_scraper):
    """Test batch processing"""
    # Create a list of test URLs
    test_urls = [f"{TEST_URL}-{i}" for i in range(3)]
    
    # Mock the scrape_profile_with_retries method
    async def mock_scrape_with_retries(url):
        # Return success for even indices, error for odd
        index = int(url.split("-")[-1])
        if index % 2 == 0:
            return {
                "url": url,
                "name": f"Test Profile {index}",
                "_process_time": "1.00s"
            }
        else:
            return {
                "url": url,
                "_error": "Test error",
                "_process_time": "1.00s"
            }
    
    # Apply the mock
    test_scraper.scrape_profile_with_retries = mock_scrape_with_retries
    
    # Call the method under test
    results = await test_scraper.scrape_batch(test_urls, max_workers=2)
    
    # Verify results
    assert len(results) == 3
    assert results[0]["name"] == "Test Profile 0"
    assert "_error" in results[1]
    assert results[2]["name"] == "Test Profile 2"
    
    # Verify tracked URLs were saved
    assert os.path.exists(TEST_TRACKED)
    with open(TEST_TRACKED, "r") as f:
        tracked_urls = f.read().splitlines()
    assert len(tracked_urls) == 3
    
    # Verify CSV was created
    assert os.path.exists(TEST_CSV)

def test_load_scraped_urls(test_scraper):
    """Test loading previously scraped URLs"""
    # Create test tracked URLs file
    test_urls = [f"{TEST_URL}-{i}" for i in range(5)]
    with open(TEST_TRACKED, "w") as f:
        f.write("\n".join(test_urls))
    
    # Reload URLs
    urls = test_scraper._load_scraped_urls()
    
    # Verify
    assert len(urls) == 5
    for url in test_urls:
        assert url in urls

def test_initialize_csv(test_scraper):
    """Test CSV initialization"""
    # Method is called in constructor, so file should exist
    assert os.path.exists(TEST_CSV)
    
    # Verify headers
    with open(TEST_CSV, "r") as f:
        header_line = f.readline().strip()
    
    assert "Profile URL" in header_line
    assert "Name" in header_line
    assert "Email" in header_line
    assert "Success" in header_line

def test_save_profile_data(test_scraper):
    """Test saving profile data to CSV"""
    # Test data
    data = {
        "url": TEST_URL,
        "name": "Test Profile",
        "email": "test@example.com",
        "onlyfans": "https://onlyfans.com/test-profile",
        "_process_time": "1.23s"
    }
    
    # Call method
    test_scraper._save_profile_data(data)
    
    # Verify data was saved
    with open(TEST_CSV, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2  # Header + data
        data_line = lines[1].strip()
        assert TEST_URL in data_line
        assert "Test Profile" in data_line
        assert "test@example.com" in data_line
        assert "onlyfans.com" in data_line
        assert "Yes" in data_line  # Success flag

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])