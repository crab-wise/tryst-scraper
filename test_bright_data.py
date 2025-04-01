#!/usr/bin/env python3
"""
Test script for Bright Data Web Unlocker API integration

This script tests the Web Unlocker API functionality by scraping
the first 10 profiles from profile_urls.txt and saving the results.
"""

import os
import sys
import time
import json
import csv
from pprint import pprint

# Import the necessary functions from profile_scraper.py
from profile_scraper import (
    fetch_with_bright_data,
    scrape_profile_with_bright_data,
    initialize_csv,
    save_to_csv,
    save_scraped_url
)

def test_bright_data_api():
    """Test the Bright Data Web Unlocker API by scraping 10 profiles."""
    print("\n" + "="*80)
    print("TESTING BRIGHT DATA WEB UNLOCKER API")
    print("="*80 + "\n")
    
    # Create test output directory
    os.makedirs("test_results", exist_ok=True)
    
    # Create test CSV file
    test_csv = "test_results/test_profiles.csv"
    
    # Initialize CSV file
    if not os.path.exists(test_csv):
        with open(test_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Profile URL", "Name", "Email", "Phone", "Mobile", "WhatsApp", 
                "Linktree", "Website", "OnlyFans", "Fansly", "Twitter", "Instagram",
                "Snapchat", "Telegram", "Success", "Error"
            ])
    
    # Read the first 10 URLs from profile_urls.txt
    with open("profile_urls.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f.readlines()[:10]]
    
    print(f"Found {len(urls)} URLs to test:")
    for i, url in enumerate(urls):
        print(f"{i+1}. {url}")
    print()
    
    # Test results tracking
    results = {
        "success": 0,
        "failed": 0,
        "errors": {},
        "show_buttons_found": 0,
        "contact_info_found": 0,
        "empty_responses": 0
    }
    
    # Test each URL
    for i, url in enumerate(urls):
        print(f"\nTesting URL {i+1}/{len(urls)}: {url}")
        print("-" * 50)
        
        try:
            # Start timing
            start_time = time.time()
            
            # Test direct fetch first to analyze the raw HTML
            print("Testing direct fetch first...")
            success, html_content = fetch_with_bright_data(url)
            
            if success:
                html_size = len(html_content)
                print(f"Direct fetch successful, got {html_size} bytes of HTML")
                
                # Check for empty content
                if html_size == 0:
                    print("⚠️ WARNING: Empty HTML content received")
                    results["empty_responses"] += 1
                    
                # Count Show buttons in the HTML
                show_button_count = html_content.count('data-action="click->unobfuscate-details#revealUnobfuscatedContent')
                if show_button_count > 0:
                    print(f"⚠️ Found {show_button_count} 'Show' buttons in the HTML that need to be clicked")
                    results["show_buttons_found"] += show_button_count
                    
                    # Save a sample of the HTML with Show buttons
                    with open(f"test_results/show_buttons_{i+1}.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    
            else:
                print(f"Direct fetch failed: {html_content}")
            
            # Then try the full scrape with parsing
            print("\nNow testing full scrape with parsing...")
            
            # Scrape the profile using Bright Data
            profile_data = scrape_profile_with_bright_data(url)
            
            # End timing
            elapsed_time = time.time() - start_time
            
            # Check if we got valid data
            if profile_data.get("_error"):
                print(f"❌ Failed: {profile_data.get('_error')}")
                results["failed"] += 1
                error_type = profile_data.get("_error")
                results["errors"][error_type] = results["errors"].get(error_type, 0) + 1
                
                # Save to CSV with error info
                with open(test_csv, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    row = [
                        profile_data.get("url", ""),
                        profile_data.get("name", ""),
                        profile_data.get("email", ""),
                        profile_data.get("phone", ""),
                        profile_data.get("mobile", ""),
                        profile_data.get("whatsapp", ""),
                        profile_data.get("linktree", ""),
                        profile_data.get("website", ""),
                        profile_data.get("onlyfans", ""),
                        profile_data.get("fansly", ""),
                        profile_data.get("twitter", ""),
                        profile_data.get("instagram", ""),
                        profile_data.get("snapchat", ""),
                        profile_data.get("telegram", ""),
                        "No",
                        profile_data.get("_error", "")
                    ]
                    writer.writerow(row)
            else:
                # Success case
                print(f"✅ Success in {elapsed_time:.2f} seconds")
                results["success"] += 1
                
                # Print the extracted data
                print(f"  Name: {profile_data.get('name')}")
                has_contact = False
                contact_fields = ["email", "phone", "mobile", "whatsapp", "onlyfans", "twitter", "instagram"]
                contact_count = 0
                
                for field in contact_fields:
                    if profile_data.get(field):
                        has_contact = True
                        contact_count += 1
                        print(f"  {field.capitalize()}: {profile_data.get(field)}")
                
                if has_contact:
                    print(f"  Found {contact_count} contact items")
                    results["contact_info_found"] += contact_count
                else:
                    print("  No contact information found")
                
                # Save to CSV
                with open(test_csv, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    row = [
                        profile_data.get("url", ""),
                        profile_data.get("name", ""),
                        profile_data.get("email", ""),
                        profile_data.get("phone", ""),
                        profile_data.get("mobile", ""),
                        profile_data.get("whatsapp", ""),
                        profile_data.get("linktree", ""),
                        profile_data.get("website", ""),
                        profile_data.get("onlyfans", ""),
                        profile_data.get("fansly", ""),
                        profile_data.get("twitter", ""),
                        profile_data.get("instagram", ""),
                        profile_data.get("snapchat", ""),
                        profile_data.get("telegram", ""),
                        "Yes",
                        ""
                    ]
                    writer.writerow(row)
            
            # Small delay between requests to be nice to the API
            if i < len(urls) - 1:  # No need to delay after the last URL
                delay = 1.0  # 1 second delay
                print(f"Waiting {delay:.1f} seconds before next request...")
                time.sleep(delay)
                
        except Exception as e:
            # Handle unexpected errors
            print(f"❌ Exception: {e}")
            results["failed"] += 1
            error_type = str(type(e).__name__)
            results["errors"][error_type] = results["errors"].get(error_type, 0) + 1
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total profiles tested: {len(urls)}")
    print(f"Successful: {results['success']} ({results['success']/len(urls)*100:.2f}%)")
    print(f"Failed: {results['failed']} ({results['failed']/len(urls)*100:.2f}%)")
    print(f"Empty responses: {results['empty_responses']}")
    print(f"Show buttons found: {results['show_buttons_found']}")
    print(f"Contact info items found: {results['contact_info_found']}")
    
    if results["errors"]:
        print("\nError types:")
        for error_type, count in results["errors"].items():
            print(f"  - {error_type}: {count}")
    
    # Save summary to file
    with open("test_results/summary.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": len(urls),
            "success": results["success"],
            "success_rate": results["success"]/len(urls),
            "failed": results["failed"],
            "errors": results["errors"],
            "show_buttons_found": results["show_buttons_found"],
            "contact_info_found": results["contact_info_found"],
            "empty_responses": results["empty_responses"]
        }, f, indent=2)
    
    print(f"\nDetailed results saved to {test_csv}")
    print(f"Summary saved to test_results/summary.json")

if __name__ == "__main__":
    # Run the test
    test_bright_data_api()