#!/usr/bin/env python3
"""
Tryst.link Profile Scraper using Bright Data Scraping Browser

This script leverages Bright Data's Scraping Browser infrastructure to:
1. Extract contact information from escort profiles on Tryst.link
2. Handle rate limiting and CAPTCHAs automatically
3. Click "Show" buttons to reveal hidden contact info
4. Process profiles at scale with parallel workers
"""

import os
import sys
import time
import json
import csv
import base64
import random
import logging
import argparse
import requests  # Added for 2captcha API

# Add 2captcha API key for CAPTCHA solving
TWOCAPTCHA_API_KEY = "47c255be6d47c6761bd1db4141b5c8a4"
import asyncio
import aiohttp
from aiohttp import ClientSession, ClientTimeout, WSMsgType
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Any, Tuple, Optional
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Functions for 2captcha CAPTCHA solving
def solve_captcha_with_2captcha_imagetotext(image_path):
    """Solve image-to-text CAPTCHA using 2Captcha service."""
    logger.info("Attempting to solve image CAPTCHA with 2Captcha...")
    
    try:
        # Read the image file as base64
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Debug image size
            image_size_kb = len(image_data) / 1024
            logger.debug(f"Image size for 2Captcha: {image_size_kb:.2f} KB")
        
        # Create task with 2Captcha specific parameters
        task_payload = {
            "clientKey": TWOCAPTCHA_API_KEY,
            "task": {
                "type": "ImageToTextTask",
                "body": base64_image,
                "phrase": False,
                "case": True,
                "numeric": 0,
                "math": False,
                "minLength": 0,
                "maxLength": 0
            }
        }
        
        # Create 2Captcha task
        url = "https://api.2captcha.com/createTask"
        logger.debug("Sending createTask request to 2Captcha...")
        response = requests.post(url, json=task_payload)
        
        if response.status_code != 200:
            error_msg = f"Error creating 2Captcha task: {response.status_code}"
            logger.error(error_msg)
            return None
            
        data = response.json()
        if data.get("errorId") != 0:
            error_msg = f"Error from 2Captcha API: {data.get('errorDescription', 'Unknown error')}"
            logger.error(error_msg)
            return None
            
        task_id = data.get("taskId")
        if not task_id:
            logger.error("No taskId returned from 2Captcha")
            return None
            
        logger.debug(f"2Captcha task created with ID: {task_id}")
        
        # Get task result with retries
        max_attempts = 20
        attempts = 0
        result_data = None
        
        while attempts < max_attempts:
            attempts += 1
            logger.debug(f"Checking task result, attempt {attempts}/{max_attempts}...")
            
            # Wait before checking result
            time.sleep(3)  # 3 seconds between checks
            
            # Get task result
            get_result_payload = {
                "clientKey": TWOCAPTCHA_API_KEY,
                "taskId": task_id
            }
            result_url = "https://api.2captcha.com/getTaskResult" 
            result_response = requests.post(result_url, json=get_result_payload)
            
            if result_response.status_code != 200:
                logger.error(f"Error getting task result: {result_response.status_code}")
                continue
                
            result_data = result_response.json()
            
            # Check for error in response
            if result_data.get("errorId") != 0:
                error_msg = f"Error getting result: {result_data.get('errorDescription', 'Unknown error')}"
                logger.error(error_msg)
                return None
                
            # Check if task is ready
            status = result_data.get("status")
            if status == "ready":
                solution = result_data.get("solution", {}).get("text")
                if solution:
                    logger.info(f"2Captcha solved the CAPTCHA: {solution}")
                    return solution
                else:
                    logger.error("2Captcha returned empty solution")
                    return None
            
            # If not ready, continue waiting
            logger.debug(f"Task not ready yet, status: {status}")
        
        logger.error(f"Failed to get task result after {max_attempts} attempts")
        return None
        
    except Exception as e:
        logger.error(f"Error in 2Captcha solving process: {str(e)}")
        return None

# Bright Data Scraping Browser Configuration
# Hardcoded credentials from the image
BRIGHT_DATA_CUSTOMER_ID = "hl_4a56dcd0"  # Your customer ID
BRIGHT_DATA_ZONE = "scraping_browser1"   # Your zone name
BRIGHT_DATA_PASSWORD = "auv09na569vp"    # Your zone password

# Construct the proper WebSocket URL for Scraping Browser
BRIGHT_DATA_WS_ENDPOINT = f"wss://brd-customer-{BRIGHT_DATA_CUSTOMER_ID}-zone-{BRIGHT_DATA_ZONE}:{BRIGHT_DATA_PASSWORD}@brd.superproxy.io:9222"

# Log the WebSocket endpoint (but mask the password in logs)
masked_endpoint = BRIGHT_DATA_WS_ENDPOINT.replace(BRIGHT_DATA_PASSWORD, "****")
logger.info(f"Using Scraping Browser WebSocket endpoint: {masked_endpoint}")

# Performance settings
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_WORKERS = 20
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0  # Base for exponential backoff

class TrystScraper:
    """
    Main scraper class for extracting data from Tryst.link using Bright Data Scraping Browser
    """
    
    def __init__(
        self, 
        browser_ws_endpoint: str = BRIGHT_DATA_WS_ENDPOINT,
        save_path: str = "profile_data.csv",
        tracked_urls_path: str = "scraped_urls.txt",
        max_retries: int = MAX_RETRIES,
        debug: bool = False
    ):
        """
        Initialize the scraper with configuration settings
        
        Args:
            browser_ws_endpoint: WebSocket URL for Bright Data Scraping Browser
            save_path: Path to save profile data CSV
            tracked_urls_path: Path to save list of processed URLs
            max_retries: Maximum number of retry attempts per profile
            debug: Whether to enable debug mode (additional logging)
        """
        self.browser_ws_endpoint = browser_ws_endpoint
        self.save_path = save_path
        self.tracked_urls_path = tracked_urls_path
        self.max_retries = max_retries
        self.debug = debug
        self.scraped_urls = self._load_scraped_urls()
        
        # Initialize CSV if it doesn't exist
        if not os.path.exists(save_path):
            self._initialize_csv()
        
        # Mask password in logs
        masked_endpoint = self.browser_ws_endpoint
        if BRIGHT_DATA_PASSWORD in masked_endpoint:
            masked_endpoint = masked_endpoint.replace(BRIGHT_DATA_PASSWORD, "****")
        
        logger.info(f"TrystScraper initialized with Bright Data WebSocket endpoint: {masked_endpoint}")
        
        if self.debug:
            logger.setLevel(logging.DEBUG)
    
    def _load_scraped_urls(self) -> Set[str]:
        """Load set of already processed profile URLs to avoid duplicates"""
        if os.path.exists(self.tracked_urls_path):
            with open(self.tracked_urls_path, "r", encoding="utf-8") as f:
                return {line.strip() for line in f if line.strip()}
        return set()
    
    def _initialize_csv(self) -> None:
        """Initialize CSV file with headers if it doesn't exist"""
        with open(self.save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Profile URL", "Name", "Email", "Phone", "Mobile", "WhatsApp", 
                "Linktree", "Website", "OnlyFans", "Fansly", "Twitter", "Instagram",
                "Snapchat", "Telegram", "Process Time", "Success"
            ])
    
    def _save_profile_data(self, data: Dict[str, Any]) -> None:
        """
        Save profile data to CSV file
        
        Args:
            data: Dictionary containing profile data
        """
        with open(self.save_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                data.get("url", ""),
                data.get("name", ""),
                data.get("email", ""),
                data.get("phone", ""),
                data.get("mobile", ""),
                data.get("whatsapp", ""),
                data.get("linktree", ""),
                data.get("website", ""),
                data.get("onlyfans", ""),
                data.get("fansly", ""),
                data.get("twitter", ""),
                data.get("instagram", ""),
                data.get("snapchat", ""),
                data.get("telegram", ""),
                data.get("_process_time", ""),
                "Yes" if not data.get("_error") else "No"
            ])
    
    def _track_scraped_url(self, url: str) -> None:
        """
        Mark URL as processed
        
        Args:
            url: Profile URL that has been processed
        """
        with open(self.tracked_urls_path, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
        self.scraped_urls.add(url)
    
    async def scrape_profile(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single profile using Bright Data Scraping Browser
        
        Args:
            url: Profile URL to scrape
            
        Returns:
            Dictionary containing profile data or error information
        """
        start_time = time.time()
        logger.info(f"Scraping profile: {url}")
        
        # Initialize profile data structure
        data = {
            "url": url,
            "name": None,
            "email": None,
            "phone": None,
            "mobile": None,
            "whatsapp": None,
            "linktree": None,
            "website": None,
            "onlyfans": None,
            "fansly": None,
            "twitter": None,
            "instagram": None,
            "snapchat": None,
            "telegram": None
        }
        
        # Prepare browser automation steps
        browser_actions = [
            # Navigate to URL and wait for page to load
            {"action": "goto", "url": url, "waitUntil": "networkidle0"},
            
            # Handle age verification if needed
            {"action": "evaluate", "script": """
                try {
                    const agreeButton = document.querySelector('button.btn-red[data-action="click->terms-toast#agree"]');
                    if (agreeButton) {
                        console.log('Clicking age verification button');
                        agreeButton.click();
                        return true;
                    }
                    return false;
                } catch (e) {
                    console.error('Age verification error:', e);
                    return false;
                }
            """},
            
            # Click all "Show" buttons to reveal contact info
            {"action": "evaluate", "script": """
                try {
                    // Find all Show buttons
                    const showButtons = document.querySelectorAll('a[data-action*="unobfuscate-details#revealUnobfuscatedContent"]');
                    console.log('Found ' + showButtons.length + ' Show buttons');
                    
                    // Click each button and wait briefly
                    for (const btn of showButtons) {
                        console.log('Clicking button: ' + btn.innerText);
                        btn.click();
                        // Wait for content to load
                        await new Promise(r => setTimeout(r, 500));
                    }
                    return showButtons.length;
                } catch (e) {
                    console.error('Show button error:', e);
                    return -1;
                }
            """},
            
            # Wait for any hidden content to finish loading
            {"action": "wait", "timeout": 2000},
            
            # Extract profile data
            {"action": "evaluate", "script": """
                try {
                    const extractedData = {};
                    
                    // Extract profile name
                    const nameSelectors = ['h1', 'h2', 'h3'];
                    for (const selector of nameSelectors) {
                        const element = document.querySelector(selector);
                        if (element && element.textContent.trim()) {
                            extractedData.name = element.textContent.trim();
                            break;
                        }
                    }
                    
                    // Extract contact information
                    const contactRows = document.querySelectorAll("ul.list-style-none.bg-light.p-3.rounded div.row.justify-content-between");
                    console.log('Found ' + contactRows.length + ' contact rows');
                    
                    contactRows.forEach(row => {
                        try {
                            const labelElement = row.querySelector("div.col-auto.fw-bold");
                            const valueElement = row.querySelector("div.col-auto.text-end");
                            
                            if (!labelElement || !valueElement) return;
                            
                            // Get label and standardize it
                            let label = labelElement.textContent.trim().toLowerCase();
                            if (label.includes("formerly twitter")) label = "twitter";
                            
                            // Try to extract value (revealed content)
                            let value = null;
                            
                            // First check for spans with revealed content
                            const span = valueElement.querySelector("span[data-unobfuscate-details-target='output']");
                            if (span && !span.textContent.includes('●')) {
                                value = span.textContent.trim();
                            }
                            
                            // If no value and it's a social media field, check for links
                            if (!value && !['email', 'phone', 'mobile', 'whatsapp'].includes(label)) {
                                const link = valueElement.querySelector("a");
                                if (link && link.href && !link.href.startsWith('javascript:')) {
                                    value = link.href;
                                }
                            }
                            
                            if (value) {
                                extractedData[label] = value;
                            }
                        } catch (e) {
                            console.error('Error processing row:', e);
                        }
                    });
                    
                    // Look for social media links throughout the page
                    const socialPlatforms = [
                        {domain: 'onlyfans.com', key: 'onlyfans'},
                        {domain: 'twitter.com', key: 'twitter'},
                        {domain: 'x.com', key: 'twitter'},
                        {domain: 'instagram.com', key: 'instagram'},
                        {domain: 'fansly.com', key: 'fansly'},
                        {domain: 'linktree', key: 'linktree'},
                        {domain: 'linktr.ee', key: 'linktree'},
                        {domain: 'snapchat.com', key: 'snapchat'},
                        {domain: 't.me', key: 'telegram'}
                    ];
                    
                    document.querySelectorAll('a[href]').forEach(link => {
                        const href = link.href;
                        for (const platform of socialPlatforms) {
                            if (href.includes(platform.domain) && !extractedData[platform.key]) {
                                // Fix doubled URLs
                                if (href.split(platform.domain).length > 2) {
                                    const parts = href.split(platform.domain);
                                    extractedData[platform.key] = `https://${platform.domain}${parts[parts.length-1]}`;
                                } else {
                                    extractedData[platform.key] = href;
                                }
                                break;
                            }
                        }
                    });
                    
                    return extractedData;
                } catch (e) {
                    console.error('Data extraction error:', e);
                    return {_error: e.toString()};
                }
            """}
        ]
        
        try:
            # Bright Data documentation specifies using WebSocket protocol, not HTTP POST
            # Connect using proper WebSocket client
            logger.info(f"Connecting to Bright Data Scraping Browser via WebSocket for {url}")
            
            async with aiohttp.ClientSession() as session:
                try:
                    # Connect to the browser debugging interface via WebSocket
                    async with session.ws_connect(
                        self.browser_ws_endpoint,
                        timeout=60  # Increased timeout for browser automation
                    ) as ws:
                        # First list available targets
                        await ws.send_json({
                            "id": 1,
                            "method": "Target.getTargets"
                        })
                        
                        # Wait for response
                        targets = []
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 1:
                                    if "result" in response and "targetInfos" in response["result"]:
                                        targets = response["result"]["targetInfos"]
                                        logger.debug(f"Found {len(targets)} targets")
                                    break
                            
                        # Create a new page target
                        await ws.send_json({
                            "id": 2,
                            "method": "Target.createTarget",
                            "params": {"url": "about:blank"}
                        })
                        
                        # Get the target ID from the response
                        target_id = None
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 2:
                                    if "result" in response and "targetId" in response["result"]:
                                        target_id = response["result"]["targetId"]
                                        logger.debug(f"Created new target with ID: {target_id}")
                                    else:
                                        error = response.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"Error creating target: {error}")
                                        data["_error"] = f"Error creating target: {error}"
                                    break
                        
                        if not target_id:
                            logger.error("Failed to create target")
                            data["_error"] = "Failed to create target"
                            return data
                            
                        # Attach to the target to get a session ID
                        await ws.send_json({
                            "id": 3,
                            "method": "Target.attachToTarget",
                            "params": {"targetId": target_id, "flatten": True}
                        })
                        
                        # Get the session ID from the response
                        session_id = None
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 3:
                                    if "result" in response and "sessionId" in response["result"]:
                                        session_id = response["result"]["sessionId"]
                                        logger.debug(f"Attached to target with session ID: {session_id}")
                                    else:
                                        error = response.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"Error attaching to target: {error}")
                                        data["_error"] = f"Error attaching to target: {error}"
                                    break
                        
                        if not session_id:
                            logger.error("Failed to get session ID")
                            data["_error"] = "Failed to get session ID"
                            return data
                        
                        # Enable necessary domains
                        domains_to_enable = ["Page", "Runtime", "DOM"]
                        for i, domain in enumerate(domains_to_enable):
                            await ws.send_json({
                                "id": 10 + i,
                                "method": f"{domain}.enable",
                                "sessionId": session_id
                            })
                            
                            # Wait for response
                            async for msg in ws:
                                if msg.type == WSMsgType.TEXT:
                                    response = json.loads(msg.data)
                                    if "id" in response and response["id"] == 10 + i:
                                        break
                        
                        # Navigate to the URL
                        await ws.send_json({
                            "id": 20,
                            "method": "Page.navigate",
                            "params": {"url": url},
                            "sessionId": session_id
                        })
                        
                        # Wait for navigation response
                        frame_id = None
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 20:
                                    if "result" in response and "frameId" in response["result"]:
                                        frame_id = response["result"]["frameId"]
                                        logger.debug(f"Navigation started with frame ID: {frame_id}")
                                    else:
                                        error = response.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"Error navigating: {error}")
                                        data["_error"] = f"Error navigating: {error}"
                                    break
                        
                        if not frame_id:
                            logger.error("Failed to navigate")
                            data["_error"] = "Failed to navigate"
                            return data
                        
                        # Wait for page load event
                        load_event_received = False
                        for _ in range(60):  # Wait up to 60 seconds
                            try:
                                msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                                if msg.type == WSMsgType.TEXT:
                                    event = json.loads(msg.data)
                                    if "method" in event and event["method"] == "Page.loadEventFired":
                                        load_event_received = True
                                        logger.debug("Page load event fired")
                                        break
                            except asyncio.TimeoutError:
                                pass  # Continue waiting
                        
                        if not load_event_received:
                            logger.warning("Page load event not received, continuing anyway")
                        
                        # Wait a bit more to ensure page is fully loaded
                        await asyncio.sleep(2)
                        
                        # First check if the page has the "You're almost there" text
                        await ws.send_json({
                            "id": 24,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": "document.documentElement.outerHTML",
                                "returnByValue": True
                            },
                            "sessionId": session_id
                        })
                        
                        # Get the HTML for analysis
                        page_html = ""
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 24:
                                    if "result" in response and "result" in response["result"]:
                                        page_html = response["result"]["result"].get("value", "")
                                    break
                        
                        is_verification_page = "You're almost there" in page_html
                        
                        # Use the built-in CAPTCHA solver first
                        logger.info("Attempting to solve any CAPTCHAs on the page with built-in solver...")
                        await ws.send_json({
                            "id": 25,
                            "method": "Captcha.solve",
                            "params": {
                                "detectTimeout": 30000  # 30 seconds timeout
                            },
                            "sessionId": session_id
                        })
                        
                        # Wait for CAPTCHA solve result
                        captcha_status = None
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 25:
                                    if "result" in response and "status" in response["result"]:
                                        captcha_status = response["result"]["status"]
                                        logger.info(f"CAPTCHA solve status: {captcha_status}")
                                    else:
                                        error = response.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"Error solving CAPTCHA: {error}")
                                    break
                        
                        # If we're on verification page but built-in solver didn't work, try 2captcha
                        if is_verification_page and captcha_status != "solve_finished":
                            logger.info("Verification page detected but built-in solver didn't work. Trying 2captcha...")
                            
                            # Take a screenshot of the page
                            await ws.send_json({
                                "id": 26,
                                "method": "Page.captureScreenshot",
                                "sessionId": session_id
                            })
                            
                            # Get the screenshot data
                            screenshot_data = None
                            async for msg in ws:
                                if msg.type == WSMsgType.TEXT:
                                    response = json.loads(msg.data)
                                    if "id" in response and response["id"] == 26:
                                        if "result" in response and "data" in response["result"]:
                                            screenshot_data = response["result"]["data"]
                                        break
                            
                            if screenshot_data:
                                # Save the screenshot
                                captcha_image_path = f"captcha_{url.split('/')[-1]}.png"
                                with open(captcha_image_path, "wb") as f:
                                    f.write(base64.b64decode(screenshot_data))
                                logger.info(f"Saved CAPTCHA screenshot to {captcha_image_path}")
                                
                                # Try to solve with 2captcha
                                captcha_solution = solve_captcha_with_2captcha_imagetotext(captcha_image_path)
                                
                                if captcha_solution:
                                    logger.info(f"2captcha provided solution: {captcha_solution}")
                                    
                                    # Find the input field and submit
                                    await ws.send_json({
                                        "id": 27,
                                        "method": "Runtime.evaluate",
                                        "params": {
                                            "expression": f"""
                                                (async function() {{
                                                    // Find the input field
                                                    let inputField = document.querySelector('input[name="response"]');
                                                    if (!inputField) {{
                                                        // Try more generic selectors
                                                        inputField = document.querySelector('input[type="text"]');
                                                    }}
                                                    
                                                    if (!inputField) {{
                                                        // Try to find any input field
                                                        const inputs = document.querySelectorAll('input');
                                                        for (const inp of inputs) {{
                                                            if (inp.type !== 'hidden' && inp.offsetParent !== null) {{
                                                                inputField = inp;
                                                                break;
                                                            }}
                                                        }}
                                                    }}
                                                    
                                                    if (!inputField) {{
                                                        return {{success: false, error: "Could not find input field"}};
                                                    }}
                                                    
                                                    // Enter the CAPTCHA solution
                                                    inputField.value = "{captcha_solution}";
                                                    
                                                    // Find the submit button
                                                    let submitButton = document.querySelector('button[type="submit"]');
                                                    if (!submitButton) {{
                                                        // Try more generic approaches
                                                        const buttons = document.querySelectorAll('button');
                                                        for (const btn of buttons) {{
                                                            const text = btn.textContent.toLowerCase();
                                                            if (text.includes('unlock') || text.includes('submit') || 
                                                                text.includes('verify') || btn.type === 'submit') {{
                                                                submitButton = btn;
                                                                break;
                                                            }}
                                                        }}
                                                    }}
                                                    
                                                    if (submitButton) {{
                                                        // Click the button
                                                        submitButton.click();
                                                        await new Promise(r => setTimeout(r, 1000));
                                                        return {{success: true, method: "button"}};
                                                    }} else {{
                                                        // Try submitting the form
                                                        const form = inputField.closest('form');
                                                        if (form) {{
                                                            form.submit();
                                                            await new Promise(r => setTimeout(r, 1000));
                                                            return {{success: true, method: "form"}};
                                                        }} else {{
                                                            // Last resort: try Enter key
                                                            const event = new KeyboardEvent('keypress', {{
                                                                key: 'Enter',
                                                                code: 'Enter',
                                                                keyCode: 13,
                                                                which: 13,
                                                                bubbles: true
                                                            }});
                                                            inputField.dispatchEvent(event);
                                                            await new Promise(r => setTimeout(r, 1000));
                                                            return {{success: true, method: "enter key"}};
                                                        }}
                                                    }}
                                                }})();
                                            """,
                                            "returnByValue": True,
                                            "awaitPromise": True
                                        },
                                        "sessionId": session_id
                                    })
                                    
                                    # Get the result of the CAPTCHA submission
                                    captcha_submit_result = None
                                    async for msg in ws:
                                        if msg.type == WSMsgType.TEXT:
                                            response = json.loads(msg.data)
                                            if "id" in response and response["id"] == 27:
                                                if "result" in response and "result" in response["result"]:
                                                    captcha_submit_result = response["result"]["result"].get("value", {})
                                                break
                                    
                                    if captcha_submit_result:
                                        logger.info(f"CAPTCHA submission result: {captcha_submit_result}")
                                        
                                        # Wait a bit for the page to load after CAPTCHA submission
                                        await asyncio.sleep(3)
                                        
                                        # Now check if we're still on the verification page
                                        await ws.send_json({
                                            "id": 28,
                                            "method": "Runtime.evaluate",
                                            "params": {
                                                "expression": "document.title",
                                                "returnByValue": True
                                            },
                                            "sessionId": session_id
                                        })
                                        
                                        # Get the page title
                                        page_title = ""
                                        async for msg in ws:
                                            if msg.type == WSMsgType.TEXT:
                                                response = json.loads(msg.data)
                                                if "id" in response and response["id"] == 28:
                                                    if "result" in response and "result" in response["result"]:
                                                        page_title = response["result"]["result"].get("value", "")
                                                    break
                                        
                                        if "You're almost there" not in page_title:
                                            logger.info("CAPTCHA solved successfully! Verification page passed.")
                                            captcha_status = "solve_finished"  # Mark as solved
                                        else:
                                            logger.warning("Still on verification page after 2captcha attempt")
                                else:
                                    logger.warning("2captcha failed to provide a solution")
                            else:
                                logger.warning("Failed to get screenshot for 2captcha")
                        
                        # If CAPTCHA wasn't detected or wasn't solved, continue anyway
                        if captcha_status not in ["solve_finished", "not_detected"]:
                            logger.warning(f"CAPTCHA not successfully solved. Status: {captcha_status}")
                        
                        # Wait a bit after CAPTCHA solving
                        await asyncio.sleep(2)
                        
                        # Click all "Show" buttons to reveal contact info - improved version
                        await ws.send_json({
                            "id": 29,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
                                    (async function() {
                                        try {
                                            // Track button count and success
                                            let clickedCount = 0;
                                            
                                            // Multiple selectors for Show buttons
                                            const selectors = [
                                                'a[data-action*="unobfuscate-details#revealUnobfuscatedContent"]',
                                                'a.text-secondary.fw-bold.text-decoration-none',
                                                'a.fw-bold[href="javascript:void(0)"]'
                                            ];
                                            
                                            // Function to find and click buttons
                                            async function clickButtonsWithSelector(selector) {
                                                try {
                                                    const buttons = document.querySelectorAll(selector);
                                                    
                                                    console.log(`Found ${buttons.length} buttons with selector: ${selector}`);
                                                    
                                                    for (const btn of buttons) {
                                                        try {
                                                            // Check if this button is for showing hidden content
                                                            const isShowBtn = btn.textContent.includes('Show') || 
                                                                             btn.dataset.action?.includes('unobfuscate') ||
                                                                             btn.className.includes('fw-bold');
                                                            
                                                            if (isShowBtn) {
                                                                console.log(`Clicking button: ${btn.textContent}`);
                                                                // Try direct click first
                                                                btn.click();
                                                                clickedCount++;
                                                                
                                                                // Check for CAPTCHA after each click
                                                                if (document.title.includes("You're almost there") || 
                                                                    document.querySelector('iframe[src*="captcha"]')) {
                                                                    console.log("⚠️ CAPTCHA detected after button click");
                                                                    return {clickedCount, captchaDetected: true};
                                                                }
                                                                
                                                                // Wait for content to load
                                                                await new Promise(r => setTimeout(r, 700));
                                                            }
                                                        } catch (btnError) {
                                                            console.error(`Error clicking specific button: ${btnError}`);
                                                            // Try with JavaScript as fallback
                                                            try {
                                                                console.log("Using JS click fallback");
                                                                const clickEvent = document.createEvent('MouseEvents');
                                                                clickEvent.initEvent('click', true, true);
                                                                btn.dispatchEvent(clickEvent);
                                                                clickedCount++;
                                                                await new Promise(r => setTimeout(r, 700));
                                                            } catch (jsClickError) {
                                                                console.error(`JS click also failed: ${jsClickError}`);
                                                            }
                                                        }
                                                    }
                                                    return {clickedCount, captchaDetected: false};
                                                } catch (selectorError) {
                                                    console.error(`Error with selector ${selector}: ${selectorError}`);
                                                    return {clickedCount: 0, captchaDetected: false};
                                                }
                                            }
                                            
                                            // Try each selector
                                            for (const selector of selectors) {
                                                const result = await clickButtonsWithSelector(selector);
                                                clickedCount += result.clickedCount;
                                                
                                                // If CAPTCHA detected, stop and report
                                                if (result.captchaDetected) {
                                                    return {clickedCount, captchaDetected: true};
                                                }
                                            }
                                            
                                            // Second pass: Look for any remaining obfuscated content and try to find their buttons
                                            const obfuscatedSpans = document.querySelectorAll('span.user-select-none.font-monospace');
                                            console.log(`Found ${obfuscatedSpans.length} obfuscated spans that might need clicking`);
                                            
                                            if (obfuscatedSpans.length > 0) {
                                                // Look for nearby show buttons
                                                for (const span of obfuscatedSpans) {
                                                    try {
                                                        // Look for a nearby button
                                                        const parent = span.closest('div.row');
                                                        if (parent) {
                                                            const nearbyButtons = parent.querySelectorAll('a');
                                                            for (const btn of nearbyButtons) {
                                                                try {
                                                                    console.log(`Clicking nearby button: ${btn.textContent}`);
                                                                    btn.click();
                                                                    clickedCount++;
                                                                    await new Promise(r => setTimeout(r, 700));
                                                                } catch (e) {
                                                                    console.error(`Error clicking nearby button: ${e}`);
                                                                }
                                                            }
                                                        }
                                                    } catch (e) {
                                                        console.error(`Error finding related button: ${e}`);
                                                    }
                                                }
                                            }
                                            
                                            // Return results
                                            return {clickedCount, captchaDetected: false};
                                        } catch (e) {
                                            console.error('Show button error:', e);
                                            return {clickedCount: -1, error: e.toString()};
                                        }
                                    })();
                                """,
                                "returnByValue": True,
                                "awaitPromise": True
                            },
                            "sessionId": session_id
                        })
                        
                        # Wait for response
                        show_button_result = None
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 29:
                                    if "result" in response and "result" in response["result"]:
                                        show_button_result = response["result"]["result"].get("value", {})
                                        logger.info(f"Show button click result: {show_button_result}")
                                        
                                        # If CAPTCHA was detected after clicking, try to solve it
                                        if show_button_result.get("captchaDetected"):
                                            logger.info("CAPTCHA detected after clicking Show buttons! Trying to solve...")
                                            # Re-run CAPTCHA solving since it was detected during Show button clicks
                                            await ws.send_json({
                                                "id": 29.5,
                                                "method": "Captcha.solve",
                                                "params": {
                                                    "detectTimeout": 30000  # 30 seconds timeout
                                                },
                                                "sessionId": session_id
                                            })
                                            
                                            # Wait for CAPTCHA solve result
                                            async for captcha_msg in ws:
                                                if captcha_msg.type == WSMsgType.TEXT:
                                                    captcha_response = json.loads(captcha_msg.data)
                                                    if "id" in captcha_response and captcha_response["id"] == 29.5:
                                                        if "result" in captcha_response and "status" in captcha_response["result"]:
                                                            captcha_status = captcha_response["result"]["status"]
                                                            logger.info(f"CAPTCHA solve status during Show clicks: {captcha_status}")
                                                        break
                                            
                                            # Wait a bit then continue
                                            await asyncio.sleep(2)
                                    break
                        
                        # Wait a bit for content to appear after clicking
                        await asyncio.sleep(2)
                        
                        # Click the age verification button if present
                        await ws.send_json({
                            "id": 30,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
                                    (function() {
                                        try {
                                            const agreeButton = document.querySelector('button.btn-red[data-action="click->terms-toast#agree"]');
                                            if (agreeButton) {
                                                console.log('Clicking age verification button');
                                                agreeButton.click();
                                                return true;
                                            }
                                            return false;
                                        } catch (e) {
                                            console.error('Age verification error:', e);
                                            return false;
                                        }
                                    })();
                                """,
                                "returnByValue": True
                            },
                            "sessionId": session_id
                        })
                        
                        # Wait for response but don't require success
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 30:
                                    if "result" in response and "result" in response["result"]:
                                        clicked = response["result"]["result"].get("value", False)
                                        if clicked:
                                            logger.debug("Clicked age verification button")
                                    break
                        
                        # Wait a bit for any redirects or further page loads
                        await asyncio.sleep(1)
                        
                        # Note: Show buttons are already clicked in the improved implementation above, 
                        # so we don't need to click them again here.
                        
                        # Wait a bit more for any content to load
                        await asyncio.sleep(2)
                        
                        # Extract profile data
                        await ws.send_json({
                            "id": 32,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
                                    (function() {
                                        try {
                                            const extractedData = {};
                                            
                                            // Extract profile name
                                            const nameSelectors = ['h1', 'h2', 'h3'];
                                            for (const selector of nameSelectors) {
                                                const element = document.querySelector(selector);
                                                if (element && element.textContent.trim()) {
                                                    extractedData.name = element.textContent.trim();
                                                    break;
                                                }
                                            }
                                            
                                            // Extract contact information
                                            const contactRows = document.querySelectorAll("ul.list-style-none.bg-light.p-3.rounded div.row.justify-content-between");
                                            console.log('Found ' + contactRows.length + ' contact rows');
                                            
                                            contactRows.forEach(row => {
                                                try {
                                                    const labelElement = row.querySelector("div.col-auto.fw-bold");
                                                    const valueElement = row.querySelector("div.col-auto.text-end");
                                                    
                                                    if (!labelElement || !valueElement) return;
                                                    
                                                    // Get label and standardize it
                                                    let label = labelElement.textContent.trim().toLowerCase();
                                                    if (label.includes("formerly twitter")) label = "twitter";
                                                    
                                                    // Try to extract value (revealed content)
                                                    let value = null;
                                                    
                                                    // First check for spans with revealed content
                                                    const span = valueElement.querySelector("span[data-unobfuscate-details-target='output']");
                                                    if (span && !span.textContent.includes('●')) {
                                                        value = span.textContent.trim();
                                                    }
                                                    
                                                    // If no value and it's a social media field, check for links
                                                    if (!value && !['email', 'phone', 'mobile', 'whatsapp'].includes(label)) {
                                                        const link = valueElement.querySelector("a");
                                                        if (link && link.href && !link.href.startsWith('javascript:')) {
                                                            value = link.href;
                                                        }
                                                    }
                                                    
                                                    if (value) {
                                                        extractedData[label] = value;
                                                    }
                                                } catch (e) {
                                                    console.error('Error processing row:', e);
                                                }
                                            });
                                            
                                            // Look for social media links throughout the page
                                            const socialPlatforms = [
                                                {domain: 'onlyfans.com', key: 'onlyfans'},
                                                {domain: 'twitter.com', key: 'twitter'},
                                                {domain: 'x.com', key: 'twitter'},
                                                {domain: 'instagram.com', key: 'instagram'},
                                                {domain: 'fansly.com', key: 'fansly'},
                                                {domain: 'linktree', key: 'linktree'},
                                                {domain: 'linktr.ee', key: 'linktree'},
                                                {domain: 'snapchat.com', key: 'snapchat'},
                                                {domain: 't.me', key: 'telegram'}
                                            ];
                                            
                                            document.querySelectorAll('a[href]').forEach(link => {
                                                const href = link.href;
                                                for (const platform of socialPlatforms) {
                                                    if (href.includes(platform.domain) && !extractedData[platform.key]) {
                                                        // Fix doubled URLs
                                                        if (href.split(platform.domain).length > 2) {
                                                            const parts = href.split(platform.domain);
                                                            extractedData[platform.key] = `https://${platform.domain}${parts[parts.length-1]}`;
                                                        } else {
                                                            extractedData[platform.key] = href;
                                                        }
                                                        break;
                                                    }
                                                }
                                            });
                                            
                                            return extractedData;
                                        } catch (e) {
                                            console.error('Data extraction error:', e);
                                            return {_error: e.toString()};
                                        }
                                    })();
                                """,
                                "returnByValue": True
                            },
                            "sessionId": session_id
                        })
                        
                        # Wait for extraction results
                        extracted_data = {}
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 32:
                                    if "result" in response and "result" in response["result"]:
                                        extracted_data = response["result"]["result"].get("value", {})
                                        logger.debug(f"Extracted data: {extracted_data}")
                                    else:
                                        error = response.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"Error extracting data: {error}")
                                        data["_error"] = f"Error extracting data: {error}"
                                    break
                        
                        # Close the target
                        await ws.send_json({
                            "id": 40,
                            "method": "Target.closeTarget",
                            "params": {"targetId": target_id}
                        })
                        
                        # Wait for close response
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                response = json.loads(msg.data)
                                if "id" in response and response["id"] == 40:
                                    break
                        
                        # Update our data dictionary with the extracted values
                        result = {"results": [extracted_data]}
                        
                except Exception as e:
                    logger.error(f"WebSocket connection error: {str(e)}")
                    data["_error"] = f"WebSocket connection error: {str(e)}"
                    return data
                
                # Check for errors in the response
                if "error" in result:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Scraping Browser error: {error_msg}")
                    data["_error"] = f"Scraping Browser error: {error_msg}"
                    return data
                
                # Extract data from the results
                if "results" in result and len(result["results"]) > 0:
                    # The last result should be from our data extraction script
                    extracted_data = result["results"][-1]
                    
                    if isinstance(extracted_data, dict):
                        # Check for extraction errors
                        if "_error" in extracted_data:
                            logger.error(f"Data extraction error: {extracted_data['_error']}")
                            data["_error"] = f"Data extraction error: {extracted_data['_error']}"
                            return data
                        
                        # Update our data dictionary with the extracted values
                        found_data = []
                        for key, value in extracted_data.items():
                            if key in data and value:
                                data[key] = value
                                found_data.append(key)
                        
                        if found_data:
                            logger.info(f"Successfully extracted data: {', '.join(found_data)}")
                        else:
                            logger.warning("Extraction completed but no data found")
                    else:
                        logger.info(f"Extracted data is not a dict, got: {type(extracted_data)}")
                        if isinstance(extracted_data, (int, str, bool)):
                            logger.info(f"Extracted data value: {extracted_data}")
                else:
                    logger.error("No results returned from Scraping Browser")
                    data["_error"] = "No results returned"
                    return data
            
            return data
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error while scraping {url}: {e}")
            
            # Provide more helpful error message for common cases
            if "401" in error_message or "403" in error_message or "Authentication" in error_message:
                logger.error("Authentication error with Bright Data Scraping Browser. Please check your credentials.")
                logger.error("You might need to:")
                logger.error("1. Verify your Bright Data account has Scraping Browser access")
                logger.error("2. Check that your customer ID, zone name, and password are correct")
                logger.error("3. Ensure your Bright Data account has sufficient credits")
                data["_error"] = f"Authentication error with Bright Data: {str(e)}"
            elif "websockets" in error_message.lower() or "ws" in error_message.lower():
                logger.error("WebSocket connection error. Please check:")
                logger.error("1. That your Bright Data account has Scraping Browser access")
                logger.error("2. That you're using the correct WebSocket URL format")
                logger.error("3. That your network allows WebSocket connections")
                data["_error"] = f"WebSocket connection error: {str(e)}"
            else:
                data["_error"] = f"Error: {str(e)}"
                
            return data
        except asyncio.TimeoutError:
            logger.error(f"Timeout while scraping {url}")
            data["_error"] = "Request timeout"
            return data
        except Exception as e:
            logger.error(f"Unexpected error while scraping {url}: {e}")
            data["_error"] = f"Unexpected error: {str(e)}"
            return data
        
        # Calculate processing time
        process_time = time.time() - start_time
        data["_process_time"] = f"{process_time:.2f}s"
        
        # Log extracted data
        found_data = [k for k, v in data.items() if v and not k.startswith("_")]
        logger.info(f"Successfully scraped {url} in {process_time:.2f}s. Found {len(found_data)} data points: {', '.join(found_data)}")
        
        return data
    
    async def scrape_profile_with_retries(self, url: str) -> Dict[str, Any]:
        """
        Scrape a profile with retries on failure
        
        Args:
            url: Profile URL to scrape
            
        Returns:
            Dictionary containing profile data
        """
        # Skip if already processed
        if url in self.scraped_urls:
            logger.info(f"Skipping already processed URL: {url}")
            return {"url": url, "_error": "Already processed"}
        
        # Try scraping with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt > 1:
                    # Exponential backoff for retries
                    delay = RETRY_DELAY_BASE ** attempt
                    logger.info(f"Retry {attempt}/{self.max_retries} for {url} after {delay:.2f}s delay")
                    await asyncio.sleep(delay)
                
                result = await self.scrape_profile(url)
                
                # If successful or not a retryable error, return result
                if not result.get("_error") or "Network error" not in result.get("_error", ""):
                    # Save result and mark URL as processed
                    self._save_profile_data(result)
                    self._track_scraped_url(url)
                    return result
            
            except Exception as e:
                logger.error(f"Error during retry {attempt} for {url}: {e}")
        
        # If we've exhausted retries, return the last error
        error_data = {
            "url": url,
            "_error": f"Failed after {self.max_retries} attempts",
            "_process_time": "N/A"
        }
        self._save_profile_data(error_data)
        self._track_scraped_url(url)
        return error_data
    
    async def scrape_batch(self, urls: List[str], max_workers: int = DEFAULT_MAX_WORKERS) -> List[Dict[str, Any]]:
        """
        Scrape a batch of profile URLs in parallel
        
        Args:
            urls: List of URLs to scrape
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of profile data dictionaries
        """
        # Filter out already processed URLs
        urls_to_scrape = [url for url in urls if url not in self.scraped_urls]
        logger.info(f"Scraping batch of {len(urls_to_scrape)} profiles with {max_workers} workers")
        
        if not urls_to_scrape:
            logger.info("No new URLs to process in this batch")
            return []
        
        # Create tasks for each URL, limiting concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self.scrape_profile_with_retries(url)
        
        # Create and gather tasks
        tasks = [scrape_with_semaphore(url) for url in urls_to_scrape]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, handling exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing {urls_to_scrape[i]}: {result}")
                error_data = {
                    "url": urls_to_scrape[i],
                    "_error": f"Unhandled exception: {str(result)}",
                    "_process_time": "N/A"
                }
                self._save_profile_data(error_data)
                self._track_scraped_url(urls_to_scrape[i])
                processed_results.append(error_data)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def scrape_all(self, urls: List[str], batch_size: int = DEFAULT_BATCH_SIZE, max_workers: int = DEFAULT_MAX_WORKERS) -> Dict[str, Any]:
        """
        Scrape all profile URLs in batches
        
        Args:
            urls: List of all URLs to scrape
            batch_size: Number of URLs to process in each batch
            max_workers: Maximum number of concurrent workers
            
        Returns:
            Statistics about the scraping process
        """
        # Remove duplicates and filter already processed URLs
        unique_urls = list(set(urls))
        urls_to_scrape = [url for url in unique_urls if url not in self.scraped_urls]
        total_urls = len(urls_to_scrape)
        
        if total_urls == 0:
            logger.info("No new URLs to process")
            return {"total": 0, "success": 0, "failed": 0, "time": 0, "profiles_per_second": 0, "errors": {}}
        
        logger.info(f"Starting scrape of {total_urls} profiles in batches of {batch_size} with {max_workers} workers")
        
        # Initialize statistics
        stats = {
            "total": total_urls,
            "success": 0,
            "failed": 0,
            "time": 0,
            "errors": {}
        }
        
        start_time = time.time()
        
        # Process in batches
        for i in range(0, total_urls, batch_size):
            batch_start = i
            batch_end = min(i + batch_size, total_urls)
            batch = urls_to_scrape[batch_start:batch_end]
            
            logger.info(f"Processing batch {batch_start//batch_size + 1}: URLs {batch_start+1}-{batch_end} of {total_urls}")
            
            # Process batch
            batch_results = await self.scrape_batch(batch, max_workers)
            
            # Update statistics
            for result in batch_results:
                if result.get("_error"):
                    stats["failed"] += 1
                    error_type = result.get("_error", "Unknown error")
                    stats["errors"][error_type] = stats["errors"].get(error_type, 0) + 1
                else:
                    stats["success"] += 1
            
            # Calculate progress
            processed = batch_end
            success_rate = (stats["success"] / processed) * 100 if processed > 0 else 0
            elapsed_time = time.time() - start_time
            profiles_per_second = processed / elapsed_time if elapsed_time > 0 else 0
            
            logger.info(f"Progress: {processed}/{total_urls} ({processed/total_urls*100:.1f}%) - " + 
                       f"Success rate: {success_rate:.1f}% - Speed: {profiles_per_second:.2f} profiles/sec")
            
            # Save intermediate statistics
            stats["time"] = elapsed_time
            stats["profiles_per_second"] = profiles_per_second
            with open("scraper_stats.json", "w") as f:
                json.dump(stats, f, indent=2)
        
        # Final statistics
        total_time = time.time() - start_time
        stats["time"] = total_time
        stats["profiles_per_second"] = total_urls / total_time if total_time > 0 else 0
        
        logger.info(f"Completed scraping {total_urls} profiles in {total_time:.2f}s")
        logger.info(f"Success: {stats['success']}/{total_urls} ({stats['success']/total_urls*100:.1f}%)")
        logger.info(f"Failed: {stats['failed']}/{total_urls} ({stats['failed']/total_urls*100:.1f}%)")
        
        return stats

def load_urls(filename: str) -> List[str]:
    """
    Load profile URLs from a file, one URL per line
    
    Args:
        filename: Path to the file containing URLs
        
    Returns:
        List of profile URLs
    """
    if not os.path.exists(filename):
        logger.error(f"URL file not found: {filename}")
        return []
    
    with open(filename, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Loaded {len(urls)} URLs from {filename}")
    return urls

async def main():
    """Main entry point for the scraper"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape Tryst.link profiles using Bright Data Scraping Browser")
    parser.add_argument("--urls", "-u", default="profile_urls.txt", help="File containing profile URLs to scrape")
    parser.add_argument("--output", "-o", default="profile_data.csv", help="Output CSV file for scraped data")
    parser.add_argument("--tracked", "-t", default="scraped_urls.txt", help="File to track scraped URLs")
    parser.add_argument("--batch-size", "-b", type=int, default=DEFAULT_BATCH_SIZE, help="Batch size for processing")
    parser.add_argument("--workers", "-w", type=int, default=DEFAULT_MAX_WORKERS, help="Max concurrent workers")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--test", action="store_true", help="Run in test mode (only process 5 URLs)")
    parser.add_argument("--continue", dest="continue_from_last", action="store_true", help="Continue from last run")
    args = parser.parse_args()
    
    # Credentials are now hardcoded, but we'll verify they're present
    if not BRIGHT_DATA_CUSTOMER_ID or not BRIGHT_DATA_PASSWORD:
        logger.warning("Using default credentials. For production use, update the credentials in the source code.")
    else:
        logger.info(f"Using credentials for customer ID: {BRIGHT_DATA_CUSTOMER_ID}")
    
    # Initialize the scraper
    scraper = TrystScraper(
        browser_ws_endpoint=BRIGHT_DATA_WS_ENDPOINT,
        save_path=args.output,
        tracked_urls_path=args.tracked,
        debug=args.debug
    )
    
    # Load URLs from file
    urls = load_urls(args.urls)
    if not urls:
        logger.error("No URLs found to process. Exiting.")
        sys.exit(1)
    
    if args.test:
        # Test mode - only process 5 URLs
        logger.info("Running in TEST MODE - processing only 5 URLs")
        urls = urls[:5]
    
    # Run the scraper
    stats = await scraper.scrape_all(
        urls=urls,
        batch_size=args.batch_size,
        max_workers=args.workers
    )
    
    # Print final stats
    logger.info(f"Scraping complete. Final statistics:")
    logger.info(f"Total URLs processed: {stats['total']}")
    
    # Calculate success rate safely
    success_rate = (stats['success']/stats['total']*100) if stats['total'] > 0 else 0
    failure_rate = (stats['failed']/stats['total']*100) if stats['total'] > 0 else 0
    
    logger.info(f"Successful: {stats['success']} ({success_rate:.1f}%)")
    logger.info(f"Failed: {stats['failed']} ({failure_rate:.1f}%)")
    logger.info(f"Total time: {stats['time']:.2f}s")
    logger.info(f"Average speed: {stats['profiles_per_second']:.2f} profiles/second")
    
    # Save final stats
    with open("final_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

if __name__ == "__main__":
    # Run the asyncio event loop
    asyncio.run(main())