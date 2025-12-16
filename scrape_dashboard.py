#!/usr/bin/env python3
"""
Cursor Dashboard Scraper
Fetches yearly usage stats from Cursor's API after browser login for auth
"""

import time
import json
import sys
import os
import tempfile
import requests
from datetime import datetime, timedelta
from collections import defaultdict

import subprocess
import urllib.parse

# Try to import PIL for terminal screenshot generation
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ASCII Art digits for big number display (compact 3x5)
ASCII_DIGITS = {
    '0': ['███', '█ █', '█ █', '█ █', '███'],
    '1': [' █ ', '██ ', ' █ ', ' █ ', '███'],
    '2': ['███', '  █', '███', '█  ', '███'],
    '3': ['███', '  █', '███', '  █', '███'],
    '4': ['█ █', '█ █', '███', '  █', '  █'],
    '5': ['███', '█  ', '███', '  █', '███'],
    '6': ['███', '█  ', '███', '█ █', '███'],
    '7': ['███', '  █', ' █ ', ' █ ', ' █ '],
    '8': ['███', '█ █', '███', '█ █', '███'],
    '9': ['███', '█ █', '███', '  █', '███'],
    ',': ['   ', '   ', '   ', ' █ ', '█  '],
    '.': ['   ', '   ', '   ', '   ', ' █ '],
    '+': ['   ', ' █ ', '███', ' █ ', '   '],
    '%': ['█ █', '  █', ' █ ', '█  ', '█ █'],
    ' ': ['   ', '   ', '   ', '   ', '   '],
    # K - 5-wide for better recognition
    'k': ['█  █', '█ █ ', '██  ', '█ █ ', '█  █'],
    'K': ['█  █', '█ █ ', '██  ', '█ █ ', '█  █'],
    # M - 5-wide for clear M shape
    'M': ['█   █', '██ ██', '█ █ █', '█   █', '█   █'],
    'm': ['█   █', '██ ██', '█ █ █', '█   █', '█   █'],
    # B - 5-wide with clear bumps
    'B': ['████ ', '█   █', '████ ', '█   █', '████ '],
    'b': ['████ ', '█   █', '████ ', '█   █', '████ '],
}

def number_to_ascii(num_str, color="\033[97m"):
    """Convert a number string to ASCII art."""
    reset = "\033[0m"
    lines = ['', '', '', '', '']
    for char in str(num_str):
        if char in ASCII_DIGITS:
            digit = ASCII_DIGITS[char]
            char_width = len(digit[0])  # Get actual width of this character
            for i in range(5):
                lines[i] += color + digit[i] + reset + ' '
        else:
            for i in range(5):
                lines[i] += '    '
    return lines

def get_ascii_width(num_str):
    """Get the visual width of ASCII number (without color codes)."""
    width = 0
    for char in str(num_str):
        if char in ASCII_DIGITS:
            char_width = len(ASCII_DIGITS[char][0])  # Get actual width
            width += char_width + 1  # char width + 1 space
        else:
            width += 4
    return width

def format_large_number(n, suffix=""):
    """Format large numbers in human-readable form (e.g., 1.2M, 234K)."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B{suffix}"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M{suffix}"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K{suffix}"
    else:
        return f"{n}{suffix}"

def stream_print(text, delay=0.005):
    """Print text with streaming effect."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def fade_in_block(lines, delay=0.025):
    """Animate a block of text fading in line by line."""
    for line in lines:
        print(line)
        time.sleep(delay)

def typing_effect(text, delay=0.015):
    """Fast typing effect."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)

def reveal_number(label, value, color="\033[96m", suffix=""):
    """Reveal a big ASCII number with animation."""
    reset = "\033[0m"
    dim = "\033[2m"
    
    # Print label with typing effect
    typing_effect(f"  {dim}{label}{reset}", delay=0.015)
    print()
    print()  # Extra space between label and number
    time.sleep(0.2)
    
    # Format number
    if isinstance(value, int) and value >= 1000:
        formatted = f"{value:,}"
    else:
        formatted = str(value)
    
    # Build ASCII art
    ascii_lines = number_to_ascii(formatted + suffix, color)
    
    # Reveal effect - line by line with delay
    for line in ascii_lines:
        print(f"    {line}")
        time.sleep(0.04)
    
    time.sleep(0.15)
    print()

def reveal_numbers_side_by_side(label1, value1, label2, value2, color1="\033[96m", color2="\033[95m"):
    """Reveal two big ASCII numbers side by side."""
    reset = "\033[0m"
    dim = "\033[2m"
    
    # Fixed column width for alignment
    COL_WIDTH = 32
    
    # Print both labels aligned
    print(f"  {dim}{label1:<{COL_WIDTH}}{label2}{reset}")
    print()
    time.sleep(0.3)
    
    # Format numbers
    fmt1 = f"{value1:,}" if isinstance(value1, int) and value1 >= 1000 else str(value1)
    fmt2 = f"{value2:,}" if isinstance(value2, int) and value2 >= 1000 else str(value2)
    
    # Build ASCII art for both
    lines1 = number_to_ascii(fmt1, color1)
    lines2 = number_to_ascii(fmt2, color2)
    
    # Get visual width of first number (without ANSI codes)
    width1 = get_ascii_width(fmt1)
    
    # Print side by side with proper padding
    for i in range(5):
        left = lines1[i] if i < len(lines1) else ""
        right = lines2[i] if i < len(lines2) else ""
        # Calculate padding needed (COL_WIDTH minus the visual width)
        padding = COL_WIDTH - width1
        print(f"    {left}{' ' * padding}{right}")
        time.sleep(0.08)
    
    time.sleep(0.25)
    print()

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
except ImportError:
    print("Selenium not installed. Installing...")
    import subprocess
    subprocess.run(["pip3", "install", "selenium", "requests"], check=True)
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options


def get_auth_cookie():
    """Open browser for login and capture the auth cookie."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         CURSOR DASHBOARD - SIGN IN                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  A browser window will open to the Cursor dashboard.                         ║
║  Please sign in when prompted.                                               ║
║  Once you see the dashboard, the window will close automatically.            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # Setup Chrome options - normal window for better login compatibility
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1200,800")
    chrome_options.add_argument("--window-position=100,100")
    # Remove automation flags that might cause login issues
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # Add user data dir to persist login state
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    
    print("Opening browser...")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"Chrome driver error: {e}")
        print("\nTry installing chromedriver:")
        print("   brew install chromedriver")
        return None
    
    try:
        # Go directly to dashboard - it will redirect to login if needed
        driver.get("https://cursor.com/dashboard")
        
        print("\n" + "="*60)
        print("PLEASE SIGN IN TO YOUR CURSOR ACCOUNT IN THE BROWSER")
        print("="*60)
        print("\n1. Sign in with Google, GitHub, or email")
        print("2. Wait for the dashboard to load")
        print("3. The window will close automatically once logged in")
        print("\nWaiting for login...")
        
        # Poll for the auth cookie - check every 2 seconds
        auth_cookie = None
        start_time = time.time()
        last_url = ""
        
        while not auth_cookie and (time.time() - start_time) < 300:  # 5 min timeout
            try:
                current_url = driver.current_url
                
                # Log URL changes for debugging
                if current_url != last_url:
                    if 'dashboard' in current_url.lower():
                        print("   Dashboard detected, checking for auth...")
                    last_url = current_url
                
                # Check all cookies
                cookies = driver.get_cookies()
                for cookie in cookies:
                    if cookie['name'] == 'WorkosCursorSessionToken':
                        auth_cookie = cookie['value']
                        print("   Auth token found!")
                        break
                
                # If we're on dashboard and have the cookie, we're done
                if auth_cookie and 'dashboard' in current_url.lower():
                    break
                
                # If we're on dashboard but no cookie yet, wait a bit more
                if 'dashboard' in current_url.lower() and not auth_cookie:
                    time.sleep(2)
                    # Refresh cookies
                    cookies = driver.get_cookies()
                    for cookie in cookies:
                        if cookie['name'] == 'WorkosCursorSessionToken':
                            auth_cookie = cookie['value']
                            break
                
                time.sleep(2)
            except Exception as e:
                time.sleep(2)
        
        if auth_cookie:
            print("\nLogin successful! Got auth token.")
            return auth_cookie
        else:
            print("\nCould not detect login. Please try again.")
            print("   Make sure you complete the login and see the dashboard.")
            return None
            
    finally:
        print("Closing browser...")
        driver.quit()


def fetch_yearly_analytics(auth_cookie):
    """Fetch full year analytics from Cursor API."""
    
    print("\nFetching yearly analytics...")
    
    # Hardcoded date range (Jan 2025 - Aug 2025)
    end_ts = "1765785600000"
    start_ts = "1735718400000"
    
    # API endpoint
    url = "https://cursor.com/api/dashboard/get-user-analytics"
    
    # Request payload
    payload = {
        "teamId": 0,
        "userId": 0,
        "startDate": start_ts,
        "endDate": end_ts
    }
    
    # Headers
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://cursor.com",
        "referer": "https://cursor.com/dashboard",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    # Cookies
    cookies = {
        "WorkosCursorSessionToken": auth_cookie
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)
        response.raise_for_status()
        data = response.json()
        
        print(f"Got {len(data.get('dailyMetrics', []))} days of data")
        return data
        
    except requests.exceptions.HTTPError as e:
        print(f"API Error: {e}")
        print(f"   Response: {response.text[:500]}")
        return None
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        return None


def fetch_token_usage(auth_cookie):
    """Fetch detailed token usage from Cursor API."""
    
    print("Fetching token usage data...")
    
    # Same date range
    end_ts = "1765871999999"
    start_ts = "1735718400000"
    
    url = "https://cursor.com/api/dashboard/get-filtered-usage-events"
    
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://cursor.com",
        "referer": "https://cursor.com/dashboard?tab=usage",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }
    
    cookies = {
        "WorkosCursorSessionToken": auth_cookie
    }
    
    all_events = []
    page = 1
    
    # Fetch multiple pages
    while page <= 10:
        payload = {
            "teamId": 0,
            "startDate": start_ts,
            "endDate": end_ts,
            "page": page,
            "pageSize": 100
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, cookies=cookies)
            response.raise_for_status()
            data = response.json()
            
            events = data.get('usageEventsDisplay', [])
            if not events:
                break
            
            all_events.extend(events)
            
            if len(events) < 100:
                break
            
            page += 1
            
        except Exception as e:
            print(f"   Error on page {page}: {e}")
            break
    
    print(f"   Got {len(all_events)} usage events")
    return all_events


def analyze_token_usage(events):
    """Analyze token usage from events."""
    
    if not events:
        return None
    
    stats = {
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'total_cache_write': 0,
        'total_cache_read': 0,
        'total_cost_cents': 0,
        'model_costs': defaultdict(float),
        'model_tokens': defaultdict(lambda: {'input': 0, 'output': 0}),
        'event_count': len(events)
    }
    
    for event in events:
        token_usage = event.get('tokenUsage', {})
        model = event.get('model', 'unknown')
        
        # API returns values in thousands, multiply by 1000 to get actual count
        input_tokens = token_usage.get('inputTokens', 0) * 1000
        output_tokens = token_usage.get('outputTokens', 0) * 1000
        cache_write = token_usage.get('cacheWriteTokens', 0) * 1000
        cache_read = token_usage.get('cacheReadTokens', 0) * 1000
        cost_cents = token_usage.get('totalCents', 0)
        
        stats['total_input_tokens'] += input_tokens
        stats['total_output_tokens'] += output_tokens
        stats['total_cache_write'] += cache_write
        stats['total_cache_read'] += cache_read
        stats['total_cost_cents'] += cost_cents
        
        stats['model_costs'][model] += cost_cents
        stats['model_tokens'][model]['input'] += input_tokens
        stats['model_tokens'][model]['output'] += output_tokens
    
    return stats


def analyze_yearly_data(data):
    """Analyze the yearly data and compute aggregate stats."""
    
    if not data or 'dailyMetrics' not in data:
        return None
    
    metrics = data['dailyMetrics']
    
    # Aggregate stats
    stats = {
        'total_lines_added': 0,
        'total_lines_deleted': 0,
        'accepted_lines_added': 0,
        'accepted_lines_deleted': 0,
        'total_applies': 0,
        'total_accepts': 0,
        'total_rejects': 0,
        'total_tabs_shown': 0,
        'total_tabs_accepted': 0,
        'total_agent_requests': 0,
        'subscription_included_reqs': 0,
        'active_days': 0,
        'model_usage': defaultdict(int),
        'extension_usage': defaultdict(int),
        'tab_extension_usage': defaultdict(int),
        'client_versions': defaultdict(int),
        'monthly_stats': defaultdict(lambda: {
            'lines_added': 0, 
            'accepted_lines': 0,
            'agent_requests': 0, 
            'active_days': 0,
            'tabs_shown': 0,
            'tabs_accepted': 0
        }),
        'daily_data': [],
        'busiest_day': None,
        'best_coding_day': None,
        'most_productive_day': None,
        'streak_current': 0,
        'streak_longest': 0,
        'day_of_week_stats': defaultdict(lambda: {'lines': 0, 'requests': 0, 'count': 0})
    }
    
    # Track streaks
    current_streak = 0
    longest_streak = 0
    last_active_date = None
    
    # June 1, 2025 cutoff
    june_cutoff = datetime(2025, 6, 1)
    
    for day in metrics:
        # Parse date
        date_ts = int(day.get('date', 0)) / 1000
        date_obj = datetime.fromtimestamp(date_ts)
        
        # Skip data before June 2025
        if date_obj < june_cutoff:
            continue
        
        month_key = date_obj.strftime('%Y-%m')
        day_of_week = date_obj.strftime('%A')
        
        # Check if this was an active day
        lines_added = day.get('linesAdded', 0)
        agent_requests = day.get('agentRequests', 0)
        tabs_shown = day.get('totalTabsShown', 0)
        accepted_lines = day.get('acceptedLinesAdded', 0)
        
        has_activity = lines_added > 0 or agent_requests > 0 or tabs_shown > 0
        
        if has_activity:
            stats['active_days'] += 1
            
            # Track streaks
            if last_active_date:
                days_diff = (date_obj.date() - last_active_date).days
                if days_diff == 1:
                    current_streak += 1
                else:
                    current_streak = 1
            else:
                current_streak = 1
            
            longest_streak = max(longest_streak, current_streak)
            last_active_date = date_obj.date()
            
            # Update monthly stats
            stats['monthly_stats'][month_key]['lines_added'] += lines_added
            stats['monthly_stats'][month_key]['accepted_lines'] += accepted_lines
            stats['monthly_stats'][month_key]['agent_requests'] += agent_requests
            stats['monthly_stats'][month_key]['active_days'] += 1
            stats['monthly_stats'][month_key]['tabs_shown'] += tabs_shown
            stats['monthly_stats'][month_key]['tabs_accepted'] += day.get('totalTabsAccepted', 0)
            
            # Day of week stats
            stats['day_of_week_stats'][day_of_week]['lines'] += lines_added
            stats['day_of_week_stats'][day_of_week]['requests'] += agent_requests
            stats['day_of_week_stats'][day_of_week]['count'] += 1
            
            # Track busiest day (most agent requests)
            if not stats['busiest_day'] or agent_requests > stats['busiest_day']['requests']:
                stats['busiest_day'] = {
                    'date': date_obj.strftime('%B %d, %Y'),
                    'requests': agent_requests,
                    'lines': lines_added
                }
            
            # Track best coding day (most lines added)
            if not stats['best_coding_day'] or lines_added > stats['best_coding_day']['lines']:
                stats['best_coding_day'] = {
                    'date': date_obj.strftime('%B %d, %Y'),
                    'lines': lines_added,
                    'accepted': accepted_lines
                }
            
            # Track most productive day (same as best_coding_day but with date object)
            if not stats['most_productive_day'] or lines_added > stats['most_productive_day']['lines']:
                stats['most_productive_day'] = {
                    'date': date_obj,
                    'lines': lines_added,
                    'accepted': accepted_lines
                }
        
        # Sum up metrics
        stats['total_lines_added'] += lines_added
        stats['total_lines_deleted'] += day.get('linesDeleted', 0)
        stats['accepted_lines_added'] += accepted_lines
        stats['accepted_lines_deleted'] += day.get('acceptedLinesDeleted', 0)
        stats['total_applies'] += day.get('totalApplies', 0)
        stats['total_accepts'] += day.get('totalAccepts', 0)
        stats['total_rejects'] += day.get('totalRejects', 0)
        stats['total_tabs_shown'] += tabs_shown
        stats['total_tabs_accepted'] += day.get('totalTabsAccepted', 0)
        stats['total_agent_requests'] += agent_requests
        stats['subscription_included_reqs'] += day.get('subscriptionIncludedReqs', 0)
        
        # Model usage
        for model in day.get('modelUsage', []):
            name = model.get('name', 'unknown')
            count = model.get('count', 0)
            stats['model_usage'][name] += count
        
        # Extension usage
        for ext in day.get('extensionUsage', []):
            name = ext.get('name')
            if name:  # Only count if has a name
                count = ext.get('count', 0)
                stats['extension_usage'][name] += count
        
        # Tab extension usage
        for ext in day.get('tabExtensionUsage', []):
            name = ext.get('name')
            if name:
                count = ext.get('count', 0)
                stats['tab_extension_usage'][name] += count
        
        # Client version usage
        for ver in day.get('clientVersionUsage', []):
            name = ver.get('name', 'unknown')
            count = ver.get('count', 0)
            stats['client_versions'][name] += count
        
        # Store daily data
        if has_activity:
            stats['daily_data'].append({
                'date': day.get('date'),
                'date_str': date_obj.strftime('%Y-%m-%d'),
                'lines_added': lines_added,
                'accepted_lines': accepted_lines,
                'agent_requests': agent_requests
            })
    
    stats['streak_longest'] = longest_streak
    stats['streak_current'] = current_streak
    
    return stats


def print_wrapped_stats(stats, raw_data, token_stats=None):
    """Print stats in Claude Code-inspired animated format."""
    
    if not stats:
        print("No stats to display")
        return
    
    # ANSI colors
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Calculate derived metrics
    acceptance_rate = 0
    if stats['total_applies'] > 0:
        acceptance_rate = stats['total_accepts'] / stats['total_applies'] * 100
    
    tab_acceptance_rate = 0
    if stats['total_tabs_shown'] > 0:
        tab_acceptance_rate = stats['total_tabs_accepted'] / stats['total_tabs_shown'] * 100
    
    net_lines = stats['accepted_lines_added'] - stats['accepted_lines_deleted']
    
    # Calculate days (Aug 1 - Dec 16 2025 = ~138 days)
    total_days_in_period = 199  # June 1 - Dec 16
    
    # Pre-calculate
    day_full = {'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday',
                'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday'}
    day_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    best_day = None
    best_lines = 0
    for day in day_order:
        full = day_full[day]
        if full in stats['day_of_week_stats']:
            if stats['day_of_week_stats'][full]['lines'] > best_lines:
                best_lines = stats['day_of_week_stats'][full]['lines']
                best_day = day
    
    total_model_requests = sum(stats['model_usage'].values())
    sorted_models = sorted(stats['model_usage'].items(), key=lambda x: -x[1])
    sorted_months = sorted(
        [(k, v) for k, v in stats['monthly_stats'].items() if v['lines_added'] > 0],
        key=lambda x: x[1]['lines_added'],
        reverse=True
    ) if stats['monthly_stats'] else []
    
    # Clear screen
    print("\033[2J\033[H", end="")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INTRO ANIMATION - Big ASCII "CURSOR WRAPPED"
    # ═══════════════════════════════════════════════════════════════════════════
    
    # ASCII art for CURSOR WRAPPED
    cursor_art = [
        "  ██████╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ ",
        " ██╔════╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗",
        " ██║     ██║   ██║██████╔╝███████╗██║   ██║██████╔╝",
        " ██║     ██║   ██║██╔══██╗╚════██║██║   ██║██╔══██╗",
        " ╚██████╗╚██████╔╝██║  ██║███████║╚██████╔╝██║  ██║",
        "  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝",
    ]
    
    wrapped_art = [
        " ██╗    ██╗██████╗  █████╗ ██████╗ ██████╗ ███████╗██████╗ ",
        " ██║    ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗",
        " ██║ █╗ ██║██████╔╝███████║██████╔╝██████╔╝█████╗  ██║  ██║",
        " ██║███╗██║██╔══██╗██╔══██║██╔═══╝ ██╔═══╝ ██╔══╝  ██║  ██║",
        " ╚███╔███╔╝██║  ██║██║  ██║██║     ██║     ███████╗██████╔╝",
        "  ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚══════╝╚═════╝ ",
    ]
    
    # Loading bar first
    print("\n\n\n")
    print(f"  {DIM}Loading your year in review...{RESET}")
    print()
    
    bar_width = 40
    for i in range(bar_width + 1):
        progress = int((i / bar_width) * 100)
        filled = "█" * i
        empty = "░" * (bar_width - i)
        sys.stdout.write(f"\r  {CYAN}{filled}{DIM}{empty}{RESET} {WHITE}{progress}%{RESET}")
        sys.stdout.flush()
        time.sleep(0.02)
    
    time.sleep(0.25)
    print("\033[2J\033[H", end="")
    
    # Reveal CURSOR line by line
    print("\n\n")
    for line in cursor_art:
        print(f"  {CYAN}{line}{RESET}")
        time.sleep(0.04)
    
    time.sleep(0.15)
    
    # Reveal WRAPPED line by line
    for line in wrapped_art:
        print(f"  {MAGENTA}{line}{RESET}")
        time.sleep(0.04)
    
    print()
    
    # Subtitle with typing effect
    subtitle = "Your 2025 Year in AI-Assisted Coding"
    print(f"  {DIM}", end="")
    for char in subtitle:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.015)
    print(f"{RESET}")
    
    print(f"\n  {DIM}─────────────────────────────────────────────────────────{RESET}")
    print(f"  {DIM}June - December 2025{RESET}")
    
    time.sleep(0.6)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BIG NUMBER REVEALS
    # ═══════════════════════════════════════════════════════════════════════════
    
    print(f"\n\n  {CYAN}{BOLD}YOUR STATS{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}\n")
    
    # Helper function to wait for user to press Tab
    def wait_for_tab():
        print()
        # Fixed width box - 34 chars inner width
        box_w = 34
        text = "⇥  Press Tab to continue"
        padding = box_w - len(text) - 2  # -2 for leading spaces
        print(f"  {CYAN}┌{'─' * box_w}┐{RESET}")
        print(f"  {CYAN}│{RESET}  {WHITE}{BOLD}{text}{RESET}{' ' * padding}{CYAN}│{RESET}")
        print(f"  {CYAN}└{'─' * box_w}┘{RESET}")
        sys.stdout.flush()
        
        # Try to use termios for single key detection (Unix/macOS)
        try:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while True:
                    ch = sys.stdin.read(1)
                    if ch == '\t':  # Tab key
                        break
                    elif ch == '\r' or ch == '\n':  # Also accept Enter as fallback
                        break
                    elif ch == '\x03':  # Ctrl+C
                        raise KeyboardInterrupt
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except (ImportError, termios.error):
            # Fallback to regular input on Windows or if termios fails
            input()
        except (KeyboardInterrupt, EOFError):
            pass
        
        # Clear the prompt box (4 lines)
        sys.stdout.write("\033[4A\033[J")
        sys.stdout.flush()
    
    # Helper function for styled joke/insight comments
    def show_insight_comment(text, color=YELLOW):
        time.sleep(0.15)
        print()
        # Fixed width box - 60 chars inner width
        box_inner = 60
        print(f"    {color}╭{'─' * box_inner}╮{RESET}")
        print(f"    {color}│{' ' * box_inner}│{RESET}")
        # Print text with proper right border
        sys.stdout.write(f"    {color}│{RESET}  ")
        displayed_chars = 0
        for char in text:
            sys.stdout.write(f"{WHITE}{char}{RESET}")
            sys.stdout.flush()
            displayed_chars += 1
            time.sleep(0.015)
        # Pad remaining space and close with right border
        # Account for emojis taking 2 visual chars
        emoji_chars = sum(1 for c in text if ord(c) > 127)
        visual_len = len(text) + emoji_chars
        remaining = box_inner - visual_len - 2
        sys.stdout.write(f"{' ' * max(0, remaining)}{color}│{RESET}\n")
        print(f"    {color}│{' ' * box_inner}│{RESET}")
        print(f"    {color}╰{'─' * box_inner}╯{RESET}")
        time.sleep(0.25)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MOST PRODUCTIVE DAY - Special streaming reveal
    # ═══════════════════════════════════════════════════════════════════════════
    if stats.get('most_productive_day'):
        d = stats['most_productive_day']['date']
        day_lines = stats['most_productive_day']['lines']
        date_str = d.strftime('%B %d, %Y')
        
        # Stream "What happened on..."
        time.sleep(0.25)
        question = f"What happened on {date_str}..."
        print()  # Start on a fresh line
        sys.stdout.write(f"  {YELLOW}")
        sys.stdout.flush()
        for char in question:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.025)
        print(RESET)
        time.sleep(0.75)
        
        # Clear the question lines
        sys.stdout.write("\033[2A")  # Move up 2 lines
        sys.stdout.write("\033[J")   # Clear from cursor to end of screen
        sys.stdout.flush()
        
        # Big reveal with ASCII number
        typing_effect(f"  {YELLOW}{BOLD}🏆 YOUR TOP DAY{RESET}", delay=0.02)
        print()
        time.sleep(0.15)
        
        lines_ascii = number_to_ascii(f"{day_lines:,}", YELLOW)
        for line in lines_ascii:
            print(f"    {line}")
            time.sleep(0.04)
        
        print(f"    {DIM}lines of code on {RESET}{WHITE}{date_str}{RESET}")
        time.sleep(0.15)
        
        # Celebratory message
        print()
        celeb_msg = "You absolutely shipped that day! 🚀"
        sys.stdout.write(f"    {GREEN}")
        for char in celeb_msg:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.015)
        print(RESET)
        time.sleep(0.5)
        
        print(f"\n  {DIM}{'─' * 60}{RESET}\n")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # POWER DAY (most productive day of week)
    # ═══════════════════════════════════════════════════════════════════════════
    if best_day:
        time.sleep(0.25)
        typing_effect(f"  {MAGENTA}{BOLD}📅 YOUR FAVORITE CODING DAY{RESET}", delay=0.02)
        print()
        time.sleep(0.2)
        
        # ASCII art for day names
        day_ascii = {
            'Monday': [
                "███╗   ███╗ ██████╗ ███╗   ██╗██████╗  █████╗ ██╗   ██╗",
                "████╗ ████║██╔═══██╗████╗  ██║██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "██╔████╔██║██║   ██║██╔██╗ ██║██║  ██║███████║ ╚████╔╝ ",
                "██║╚██╔╝██║██║   ██║██║╚██╗██║██║  ██║██╔══██║  ╚██╔╝  ",
                "██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██████╔╝██║  ██║   ██║   ",
                "╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Tuesday': [
                "████████╗██╗   ██╗███████╗███████╗██████╗  █████╗ ██╗   ██╗",
                "╚══██╔══╝██║   ██║██╔════╝██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "   ██║   ██║   ██║█████╗  ███████╗██║  ██║███████║ ╚████╔╝ ",
                "   ██║   ██║   ██║██╔══╝  ╚════██║██║  ██║██╔══██║  ╚██╔╝  ",
                "   ██║   ╚██████╔╝███████╗███████║██████╔╝██║  ██║   ██║   ",
                "   ╚═╝    ╚═════╝ ╚══════╝╚══════╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Wednesday': [
                "██╗    ██╗███████╗██████╗ ███╗   ██╗███████╗███████╗██████╗  █████╗ ██╗   ██╗",
                "██║    ██║██╔════╝██╔══██╗████╗  ██║██╔════╝██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "██║ █╗ ██║█████╗  ██║  ██║██╔██╗ ██║█████╗  ███████╗██║  ██║███████║ ╚████╔╝ ",
                "██║███╗██║██╔══╝  ██║  ██║██║╚██╗██║██╔══╝  ╚════██║██║  ██║██╔══██║  ╚██╔╝  ",
                "╚███╔███╔╝███████╗██████╔╝██║ ╚████║███████╗███████║██████╔╝██║  ██║   ██║   ",
                " ╚══╝╚══╝ ╚══════╝╚═════╝ ╚═╝  ╚═══╝╚══════╝╚══════╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Thursday': [
                "████████╗██╗  ██╗██╗   ██╗██████╗ ███████╗██████╗  █████╗ ██╗   ██╗",
                "╚══██╔══╝██║  ██║██║   ██║██╔══██╗██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "   ██║   ███████║██║   ██║██████╔╝███████╗██║  ██║███████║ ╚████╔╝ ",
                "   ██║   ██╔══██║██║   ██║██╔══██╗╚════██║██║  ██║██╔══██║  ╚██╔╝  ",
                "   ██║   ██║  ██║╚██████╔╝██║  ██║███████║██████╔╝██║  ██║   ██║   ",
                "   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Friday': [
                "███████╗██████╗ ██╗██████╗  █████╗ ██╗   ██╗",
                "██╔════╝██╔══██╗██║██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "█████╗  ██████╔╝██║██║  ██║███████║ ╚████╔╝ ",
                "██╔══╝  ██╔══██╗██║██║  ██║██╔══██║  ╚██╔╝  ",
                "██║     ██║  ██║██║██████╔╝██║  ██║   ██║   ",
                "╚═╝     ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Saturday': [
                "███████╗ █████╗ ████████╗██╗   ██╗██████╗ ██████╗  █████╗ ██╗   ██╗",
                "██╔════╝██╔══██╗╚══██╔══╝██║   ██║██╔══██╗██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "███████╗███████║   ██║   ██║   ██║██████╔╝██║  ██║███████║ ╚████╔╝ ",
                "╚════██║██╔══██║   ██║   ██║   ██║██╔══██╗██║  ██║██╔══██║  ╚██╔╝  ",
                "███████║██║  ██║   ██║   ╚██████╔╝██║  ██║██████╔╝██║  ██║   ██║   ",
                "╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
            'Sunday': [
                "███████╗██╗   ██╗███╗   ██╗██████╗  █████╗ ██╗   ██╗",
                "██╔════╝██║   ██║████╗  ██║██╔══██╗██╔══██╗╚██╗ ██╔╝",
                "███████╗██║   ██║██╔██╗ ██║██║  ██║███████║ ╚████╔╝ ",
                "╚════██║██║   ██║██║╚██╗██║██║  ██║██╔══██║  ╚██╔╝  ",
                "███████║╚██████╔╝██║ ╚████║██████╔╝██║  ██║   ██║   ",
                "╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
            ],
        }
        
        day_name = day_full[best_day]
        if day_name in day_ascii:
            for line in day_ascii[day_name]:
                print(f"    {MAGENTA}{line}{RESET}")
                time.sleep(0.04)
        else:
            # Fallback for any missing day
            print(f"    {MAGENTA}{BOLD}{day_name.upper()}{RESET}")
        
        print()
        print(f"    {DIM}your most productive day{RESET}")
        time.sleep(0.4)
        
        print(f"\n  {DIM}{'─' * 60}{RESET}\n")
    
    # Lines of Code + Agent Requests - SIDE BY SIDE
    time.sleep(0.5)
    reveal_numbers_side_by_side(
        "Lines of AI Code Accepted", stats['accepted_lines_added'],
        "Agent Requests Made", stats['total_agent_requests'],
        CYAN, MAGENTA
    )
    time.sleep(0.6)
    
    # Active Days + Longest Streak - SIDE BY SIDE
    COL_WIDTH = 32
    
    # Print both labels aligned
    print(f"  {DIM}{'Active Coding Days':<{COL_WIDTH}}Longest Streak{RESET}")
    print()
    time.sleep(0.3)
    
    # Build ASCII for both
    active_str = f"{stats['active_days']}"
    streak_str = f"{stats['streak_longest']}"
    active_lines = number_to_ascii(active_str, GREEN)
    streak_lines = number_to_ascii(streak_str, YELLOW)
    
    # Get visual width of first number
    width1 = get_ascii_width(active_str)
    
    # Print side by side with proper padding
    for i in range(5):
        left = active_lines[i] if i < len(active_lines) else ""
        right = streak_lines[i] if i < len(streak_lines) else ""
        padding = COL_WIDTH - width1
        print(f"    {left}{' ' * padding}{right}")
        time.sleep(0.08)
    
    # Subtitles aligned
    sub1 = f"out of {total_days_in_period} days"
    print(f"    {DIM}{sub1:<{COL_WIDTH}}days in a row{RESET}")
    time.sleep(0.3)
    print()
    
    # Calculate activity percentage and add joke
    activity_pct = (stats['active_days'] / total_days_in_period) * 100 if total_days_in_period > 0 else 0
    if activity_pct >= 90:
        top_pct = 100 - activity_pct
        show_insight_comment(f"You're top {top_pct:.0f}% of users! You've been feeling the AGI 🔥", GREEN)
    elif activity_pct >= 70:
        show_insight_comment("Solid consistency — you show up every day.", CYAN)
    else:
        show_insight_comment("Taking it easy? The code won't write itself... oh wait 🤖", YELLOW)
    
    time.sleep(0.4)
    
    # AI Trust Level - acceptance rate with interpretation and jokes
    trust_pct = int(acceptance_rate)
    if trust_pct >= 70:
        trust_label = "VIBES ONLY"
        trust_color = GREEN
        trust_joke = "Maybe slow down on the vibecoding? 🎵"
    elif trust_pct >= 50:
        trust_label = "BALANCED"
        trust_color = CYAN
        trust_joke = "The sweet spot — trust but verify. 🎯"
    else:
        trust_label = "SKEPTIC"
        trust_color = YELLOW
        trust_joke = "Why don't you trust the AGI? It just wants to help... 🤖"
    
    time.sleep(0.25)
    typing_effect(f"  {DIM}AI Trust Level{RESET}", delay=0.015)
    print()
    time.sleep(0.15)
    
    # Show percentage as ASCII
    pct_str = f"{trust_pct}"
    ascii_pct = number_to_ascii(pct_str, trust_color)
    for line in ascii_pct:
        print(f"    {line} {trust_color}%{RESET}")
        time.sleep(0.03)
    
    time.sleep(0.2)
    print(f"    {trust_color}{BOLD}{trust_label}{RESET} {DIM}— You accepted {trust_pct}% of AI suggestions{RESET}")
    
    show_insight_comment(trust_joke, trust_color)
    
    time.sleep(0.25)
    
    print(f"\n  {DIM}{'─' * 60}{RESET}")
    
    wait_for_tab()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DETAILED STATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    print("\033[2J\033[H", end="")
    print(f"\n  {CYAN}{BOLD}DETAILED BREAKDOWN{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}\n")
    
    time.sleep(0.25)
    print()
    stream_print(f"  {CYAN}{BOLD}▸ ACTIVITY BY DAY OF WEEK{RESET}", delay=0.015)
    print()
    time.sleep(0.25)
    
    max_day_lines = max((stats['day_of_week_stats'].get(day_full[d], {}).get('lines', 0) 
                        for d in day_order), default=1)
    
    for day in day_order:
        full = day_full[day]
        if full in stats['day_of_week_stats']:
            lines = stats['day_of_week_stats'][full]['lines']
            bar_len = int((lines / max_day_lines) * 25) if max_day_lines > 0 else 0
            bar = f"{CYAN}{'█' * bar_len}{DIM}{'░' * (25 - bar_len)}{RESET}"
            star = f"  {YELLOW}★ BEST{RESET}" if day == best_day else ""
            print(f"    {WHITE}{day}{RESET}  {bar}  {WHITE}{lines:>7,}{RESET} lines{star}")
            time.sleep(0.08)
    
    time.sleep(0.4)
    
    # Models - Big animated section
    time.sleep(0.3)
    print()
    
    # Animated header reveal
    model_header = "▸ TOP MODELS"
    print(f"  {MAGENTA}", end="")
    for char in model_header:
        sys.stdout.write(f"{BOLD}{char}{RESET}{MAGENTA}")
        sys.stdout.flush()
        time.sleep(0.025)
    print(RESET)
    print()
    time.sleep(0.25)
    
    # Favorite model gets big treatment
    if sorted_models:
        fav_model, fav_count = sorted_models[0]
        fav_pct = fav_count / total_model_requests * 100 if total_model_requests > 0 else 0
        
        # Pulsing reveal for #1 model
        pulses = ["◐", "◓", "◑", "◒"]
        for i in range(4):
            sys.stdout.write(f"\r    {MAGENTA}{pulses[i % 4]}{RESET} Calculating your favorite...")
            sys.stdout.flush()
            time.sleep(0.05)
        
        print(f"\r    {MAGENTA}{BOLD}★ #1 FAVORITE MODEL{RESET}                          ")
        print()
        time.sleep(0.1)
        
        # Big model name reveal - show full name
        print(f"    {WHITE}{BOLD}", end="")
        for char in fav_model:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.015)
        print(RESET)
        
        # Stats bar
        bar_width = 40
        bar_filled = int((fav_pct / 100) * bar_width)
        print(f"    {MAGENTA}{'█' * bar_filled}{DIM}{'░' * (bar_width - bar_filled)}{RESET}")
        print(f"    {WHITE}{fav_count:,}{RESET} uses  •  {WHITE}{fav_pct:.1f}%{RESET} of all requests")
        print()
        time.sleep(0.3)
        
        # Special reveal: "You and X model wrote X lines of code together"
        lines_written = stats['accepted_lines_added']
        
        print(f"    ", end="")
        msg_parts = [
            ("You and ", WHITE),
            (fav_model, YELLOW),
            (" wrote ", WHITE),
            (f"{lines_written:,}", GREEN),
            (" lines of code together.", WHITE)
        ]
        for text, color in msg_parts:
            for char in text:
                sys.stdout.write(f"{color}{char}{RESET}")
                sys.stdout.flush()
                time.sleep(0.018)
        print()
        time.sleep(0.4)
        
        # Apollo 11 comparison if > 145,000 lines
        APOLLO_11_LINES = 145000

        times_more = lines_written / APOLLO_11_LINES
        apollo_msg = f"That's {times_more:.1f}x the amount of code written in Apollo 11's moon mission! 🚀"
        print(f"    ", end="")
        for char in apollo_msg:
            color = YELLOW if char.isdigit() or char == '.' or char == 'x' else DIM
            sys.stdout.write(f"{color}{char}{RESET}")
            sys.stdout.flush()
            time.sleep(0.012)
        print()
        time.sleep(0.3)
        
        print()
        
        # Other models in compact form with sliding animation
        if len(sorted_models) > 1:
            print(f"    {DIM}Other models:{RESET}")
            print()
            for i, (model, count) in enumerate(sorted_models[1:5], start=2):
                pct = count / total_model_requests * 100 if total_model_requests > 0 else 0
                bar_len = min(int(pct / 5), 16)
                bar_empty = 16 - bar_len
                model_display = model[:20] if len(model) <= 20 else model[:17] + "..."
                
                # Simple reveal without color bleed
                print(f"    {DIM}#{i}{RESET}  {WHITE}{model_display:22}{RESET} {MAGENTA}{'▓' * bar_len}{RESET}{DIM}{'░' * bar_empty}{RESET}  {WHITE}{count:>5,}{RESET} uses {DIM}({pct:.1f}%){RESET}")
                time.sleep(0.05)
    
    # Monthly breakdown as bar graph
    if sorted_months:
        wait_for_tab()
        
        print("\033[2J\033[H", end="")
        print(f"\n  {GREEN}{BOLD}MONTHLY BREAKDOWN{RESET}")
        print(f"  {DIM}Accepted lines of AI-generated code by month{RESET}")
        print(f"  {DIM}{'─' * 60}{RESET}\n")
        time.sleep(0.3)
        
        month_short = {
            '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
            '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
            '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
        }
        
        # Find max for scaling
        max_lines = max(data['lines_added'] for _, data in sorted_months) if sorted_months else 1
        bar_max_width = 35
        
        # Sort by month chronologically for the graph
        chrono_months = sorted(stats['monthly_stats'].items(), key=lambda x: x[0])
        
        # Show bar graph for each month
        for month, data in chrono_months:
            year, month_num = month.split('-')
            m_name = month_short.get(month_num, month_num)
            lines = data['lines_added']
            
            # Calculate bar width
            bar_width = int((lines / max_lines) * bar_max_width) if max_lines > 0 else 0
            bar_empty = bar_max_width - bar_width
            
            # Color based on ranking
            rank = next((i for i, (m, _) in enumerate(sorted_months) if m == month), -1)
            if rank == 0:
                bar_color = YELLOW
                star = f" {YELLOW}★{RESET}"
            elif rank == 1:
                bar_color = WHITE
                star = ""
            elif rank == 2:
                bar_color = MAGENTA
                star = ""
            else:
                bar_color = GREEN
                star = ""
            
            # Print the bar
            bar = f"{bar_color}{'█' * bar_width}{RESET}{DIM}{'░' * bar_empty}{RESET}"
            print(f"    {WHITE}{m_name}{RESET}  {bar}  {WHITE}{lines:>6,}{RESET}{star}")
            time.sleep(0.1)
        
        print()
        print(f"    {DIM}★ = top month{RESET}")
        time.sleep(0.3)
    
    # Tab completions - bigger section
    time.sleep(0.4)
    print()
    stream_print(f"  {BLUE}{BOLD}▸ TAB COMPLETIONS{RESET}", delay=0.015)
    print()
    time.sleep(0.25)
    
    # Big number for tabs accepted
    typing_effect(f"    {DIM}Tabs Accepted{RESET}", delay=0.015)
    print()
    tab_ascii = number_to_ascii(f"{stats['total_tabs_accepted']:,}", BLUE)
    for line in tab_ascii:
        print(f"      {line}")
        time.sleep(0.015)
    print(f"      {DIM}out of {stats['total_tabs_shown']:,} suggestions ({tab_acceptance_rate:.1f}% acceptance rate){RESET}")
    print()
    
    # Token usage section (if available)
    if token_stats and token_stats.get('event_count', 0) > 0:
        wait_for_tab()
        
        print("\033[2J\033[H", end="")
        print(f"\n  {GREEN}{BOLD}TOKEN USAGE{RESET}")
        print(f"  {DIM}{'─' * 60}{RESET}\n")
        time.sleep(0.25)
        
        total_tokens = token_stats['total_input_tokens'] + token_stats['total_output_tokens']
        cache_total = token_stats['total_cache_read'] + token_stats['total_cache_write']
        cache_hit_rate = (token_stats['total_cache_read'] / cache_total * 100) if cache_total > 0 else 0
        cost_dollars = token_stats['total_cost_cents'] / 100
        
        # Total tokens as ASCII (formatted for readability)
        typing_effect(f"  {DIM}Total Tokens Used{RESET}", delay=0.01)
        print()
        print()  # Extra space
        token_display = format_large_number(total_tokens)
        token_ascii = number_to_ascii(token_display, GREEN)
        for line in token_ascii:
            print(f"    {line}")
            time.sleep(0.015)
        print(f"    {DIM}({total_tokens:,} tokens){RESET}")
        print()
        
        # Breakdown with readable format (always show unit)
        print(f"    {DIM}Input tokens:{RESET}      {WHITE}{format_large_number(token_stats['total_input_tokens'], ' tokens'):>18}{RESET}")
        print(f"    {DIM}Output tokens:{RESET}     {WHITE}{format_large_number(token_stats['total_output_tokens'], ' tokens'):>18}{RESET}")
        print(f"    {DIM}Cache read:{RESET}        {WHITE}{format_large_number(token_stats['total_cache_read'], ' tokens'):>18}{RESET}")
        print(f"    {DIM}Cache write:{RESET}       {WHITE}{format_large_number(token_stats['total_cache_write'], ' tokens'):>18}{RESET}")
        print(f"    {DIM}Cache hit rate:{RESET}    {WHITE}{cache_hit_rate:>11.1f}%{RESET}")
        print()
        print(f"    {DIM}Estimated cost:{RESET}    {GREEN}{BOLD}${cost_dollars:>10,.2f}{RESET}")
        
        # Cost by model
        if token_stats.get('model_costs'):
            print()
            print(f"    {DIM}Cost by model:{RESET}")
            sorted_costs = sorted(token_stats['model_costs'].items(), key=lambda x: -x[1])[:4]
            for model, cost in sorted_costs:
                model_short = model[:25] if len(model) <= 25 else model[:22] + "..."
                cost_usd = cost / 100
                print(f"      {WHITE}{model_short:27}{RESET} ${cost_usd:>8,.2f}")
        print()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY CARD (Screenshot-friendly) - Animated reveal
    # ═══════════════════════════════════════════════════════════════════════════
    
    wait_for_tab()
    
    print("\033[2J\033[H", end="")
    
    # Build the summary card data
    top_model = sorted_models[0][0] if sorted_models else "N/A"
    if 'claude' in top_model.lower():
        top_model = top_model.replace('claude-', '').replace('-', ' ').title()
    top_model = top_model[:20] if len(top_model) > 20 else top_model
    
    power_day = day_full[best_day] if best_day else "N/A"
    
    peak_day_str = "N/A"
    if stats.get('most_productive_day'):
        d = stats['most_productive_day']['date']
        peak_day_str = f"{d.strftime('%b %d')} ({stats['most_productive_day']['lines']:,})"
    
    # Token stats
    total_tokens_val = "N/A"
    if token_stats:
        total_tok = token_stats.get('total_input_tokens', 0) + token_stats.get('total_output_tokens', 0)
        total_tokens_val = format_large_number(total_tok, " tokens")
    
    # Pre-format all values
    lines_val = f"{stats['accepted_lines_added']:,}"
    requests_val = f"{stats['total_agent_requests']:,}"
    active_val = f"{stats['active_days']} / {total_days_in_period}"
    streak_val = f"{stats['streak_longest']} days"
    accept_val = f"{int(acceptance_rate)}%"
    
    # Tab acceptance stats
    tab_shown = stats.get('total_tabs_shown', 0)
    tab_accepted = stats.get('total_tabs_accepted', 0)
    tab_rate = (tab_accepted / tab_shown * 100) if tab_shown > 0 else 0
    tab_val = f"{tab_accepted:,} ({tab_rate:.0f}%)"
    
    # Sleek summary card with animation
    W = 52  # inner width (must be even for centering)
    
    def animate_line(line, delay=0.02):
        """Print line with animation."""
        print(line)
        time.sleep(delay)
    
    def make_stat_row(label, value):
        """Create a stat row with fixed width alignment."""
        label_w = 20  # Increased to fit "Favorite Coding Day"
        value_w = W - label_w - 4  # 4 for spacing
        padded_label = f"{label:<{label_w}}"
        padded_value = f"{value:>{value_w}}"
        return f"  {CYAN}│{RESET}  {WHITE}{padded_label}{RESET}{YELLOW}{padded_value}{RESET}  {CYAN}│{RESET}"
    
    def make_highlight_row(label, value):
        """Create a highlighted row with fixed width."""
        label_w = 20  # Increased to fit "Favorite Coding Day"
        value_w = W - label_w - 4
        padded_label = f"{label:<{label_w}}"
        padded_value = f"{value:>{value_w}}"
        return f"  {CYAN}│{RESET}  {MAGENTA}{BOLD}{padded_label}{RESET}{WHITE}{BOLD}{padded_value}{RESET}  {CYAN}│{RESET}"
    
    # Animated reveal
    print()
    time.sleep(0.3)
    
    # Top border
    animate_line(f"  {CYAN}┌{'─' * W}┐{RESET}", 0.05)
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.03)
    
    # Title - centered
    title = "✦ CURSOR WRAPPED 2025 ✦"
    title_pad = (W - len(title)) // 2
    animate_line(f"  {CYAN}│{RESET}{' ' * title_pad}{WHITE}{BOLD}{title}{RESET}{' ' * (W - title_pad - len(title))}{CYAN}│{RESET}", 0.05)
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.03)
    animate_line(f"  {CYAN}├{'─' * W}┤{RESET}", 0.03)
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.02)
    
    # Stats section
    animate_line(make_highlight_row("Lines Accepted", lines_val), 0.06)
    animate_line(make_stat_row("Agent Requests", requests_val), 0.05)
    animate_line(make_stat_row("Total Tokens", total_tokens_val), 0.05)
    animate_line(make_stat_row("Tabs Accepted", tab_val), 0.05)
    animate_line(make_stat_row("Active Days", active_val), 0.05)
    animate_line(make_stat_row("Longest Streak", streak_val), 0.05)
    
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.02)
    animate_line(f"  {CYAN}├{'─' * W}┤{RESET}", 0.03)
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.02)
    
    # Highlights section - simple format
    animate_line(make_stat_row("Top Model", top_model), 0.05)
    animate_line(make_stat_row("Favorite Coding Day", power_day), 0.05)
    animate_line(make_stat_row("Peak Day", peak_day_str), 0.05)
    
    animate_line(f"  {CYAN}│{' ' * W}│{RESET}", 0.02)
    animate_line(f"  {CYAN}├{'─' * W}┤{RESET}", 0.03)
    
    # Footer - centered
    github_url = "github.com/riyapatel25/cursorWrapped"
    url_pad = (W - len(github_url)) // 2
    animate_line(f"  {CYAN}│{RESET}{' ' * url_pad}{DIM}{github_url}{RESET}{' ' * (W - url_pad - len(github_url))}{CYAN}│{RESET}", 0.03)
    animate_line(f"  {CYAN}└{'─' * W}┘{RESET}", 0.05)
    
    print()
    time.sleep(0.3)
    print(f"  {DIM}Screenshot this to share! 📸{RESET}")
    print()
    
    # Final message
    print(f"  {DIM}{'─' * 60}{RESET}")
    print()
    final_msg = "Keep shipping in 2026"
    for i in range(len(final_msg) + 1):
        sys.stdout.write(f"\r  {CYAN}{BOLD}{final_msg[:i]}{RESET}")
        sys.stdout.flush()
        time.sleep(0.015)
    print(" 🚀")
    print()
    print(f"  {DIM}{'─' * 60}{RESET}")
    print()
    
    # Return stats for potential replay/share
    return {
        'stats': stats,
        'raw_data': raw_data,
        'token_stats': token_stats,
        'acceptance_rate': acceptance_rate,
        'best_day': best_day,
        'day_full': day_full,
        'sorted_models': sorted_models,
        'sorted_months': sorted_months,
        'total_days': total_days_in_period
    }
    


def generate_terminal_image(wrapped_data):
    """Generate a professional, modern card image for sharing."""
    if not HAS_PIL:
        return None
    
    # Extract data for the card
    stats = wrapped_data['stats']
    acceptance_rate = wrapped_data['acceptance_rate']
    sorted_models = wrapped_data['sorted_models']
    best_day = wrapped_data['best_day']
    day_full = wrapped_data['day_full']
    total_days = wrapped_data.get('total_days', 199)
    token_stats = wrapped_data.get('token_stats')
    
    # Prepare display values
    top_model = sorted_models[0][0] if sorted_models else "N/A"
    if 'claude' in top_model.lower():
        top_model = top_model.replace('claude-', '').replace('-', ' ').title()
    top_model = top_model[:20] if len(top_model) > 20 else top_model
    
    power_day = day_full[best_day] if best_day else "N/A"
    
    total_tokens = "N/A"
    if token_stats:
        total_tok = token_stats.get('total_input_tokens', 0) + token_stats.get('total_output_tokens', 0)
        total_tokens = format_large_number(total_tok, " tokens")
    
    tab_shown = stats.get('total_tabs_shown', 0)
    tab_accepted = stats.get('total_tabs_accepted', 0)
    tab_rate = (tab_accepted / tab_shown * 100) if tab_shown > 0 else 0
    tabs_val = f"{tab_accepted:,} ({tab_rate:.0f}%)"
    
    # === CLAUDE CODE INSPIRED COLOR PALETTE ===
    bg_gradient_top = (13, 13, 18)      # #0D0D12
    bg_gradient_bottom = (19, 19, 24)   # #131318
    card_bg = (26, 26, 34)              # #1A1A22
    title_bar_bg = (32, 32, 40)         # Window chrome
    divider_color = (42, 42, 53)        # #2A2A35
    
    primary_accent = (96, 223, 255)     # #60DFFF cyan
    secondary_accent = (126, 231, 135)  # #7EE787 green
    gold_accent = (255, 200, 87)        # Gold for title
    text_primary = (255, 255, 255)      # White
    text_secondary = (152, 152, 166)    # #9898A6
    text_dim = (100, 100, 115)          # Dimmed text
    
    # Load fonts
    def load_font(size, bold=False):
        # Try SF Pro first (macOS), then fall back to system fonts
        paths = [
            "/System/Library/Fonts/SFNSMono.ttf" if not bold else "/System/Library/Fonts/SFNSMono.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()
    
    # Fonts for different hierarchy levels
    title_font = load_font(26, bold=True)
    label_font = load_font(18)
    value_font = load_font(18, bold=True)
    small_font = load_font(14)
    window_font = load_font(13)
    
    # === LAYOUT DIMENSIONS ===
    card_width = 520
    card_padding = 36
    content_width = card_width - (card_padding * 2)
    row_height = 36
    section_spacing = 20
    
    # Calculate card height based on content
    title_section_height = 80
    stats_section_height = row_height * 6 + section_spacing
    highlights_section_height = row_height * 2 + section_spacing
    footer_section_height = 50
    
    card_height = (title_section_height + stats_section_height + 
                   highlights_section_height + footer_section_height + section_spacing * 2)
    
    # Window dimensions (with title bar)
    window_title_bar_height = 48
    window_padding = 40
    img_width = card_width + window_padding * 2
    img_height = card_height + window_title_bar_height + window_padding * 2
    
    # Create image
    img = Image.new('RGB', (img_width, img_height), bg_gradient_top)
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background
    for y in range(img_height):
        ratio = y / img_height
        r = int(bg_gradient_top[0] + (bg_gradient_bottom[0] - bg_gradient_top[0]) * ratio)
        g = int(bg_gradient_top[1] + (bg_gradient_bottom[1] - bg_gradient_top[1]) * ratio)
        b = int(bg_gradient_top[2] + (bg_gradient_bottom[2] - bg_gradient_top[2]) * ratio)
        draw.line([(0, y), (img_width, y)], fill=(r, g, b))
    
    # === DRAW WINDOW CHROME (macOS style) ===
    # Title bar
    draw.rectangle([(0, 0), (img_width, window_title_bar_height)], fill=title_bar_bg)
    draw.line([(0, window_title_bar_height), (img_width, window_title_bar_height)], fill=divider_color, width=1)
    
    # Traffic light buttons
    button_y = (window_title_bar_height - 14) // 2
    draw.ellipse([(20, button_y), (34, button_y + 14)], fill=(255, 95, 87))
    draw.ellipse([(44, button_y), (58, button_y + 14)], fill=(255, 189, 46))
    draw.ellipse([(68, button_y), (82, button_y + 14)], fill=(39, 201, 63))
    
    # Window title
    window_title = "cursor-wrapped"
    title_bbox = draw.textbbox((0, 0), window_title, font=window_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((img_width - title_w) // 2, (window_title_bar_height - 14) // 2), 
              window_title, fill=text_secondary, font=window_font)
    
    # === DRAW MAIN CARD ===
    card_x = window_padding
    card_y = window_title_bar_height + window_padding
    card_radius = 12
    
    # Draw card shadow (multiple layers for soft shadow)
    for i in range(8, 0, -1):
        shadow_alpha = int(20 * (1 - i / 8))
        shadow_color = (0, 0, 0)
        offset = i * 2
        # Draw shadow rectangles (approximate rounded rect shadow)
        draw.rectangle(
            [(card_x + offset, card_y + offset), 
             (card_x + card_width + offset, card_y + card_height + offset)],
            fill=(shadow_color[0], shadow_color[1], shadow_color[2])
        )
    
    # Draw card background with rounded corners
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_width, card_y + card_height)],
        radius=card_radius,
        fill=card_bg
    )
    
    # Draw subtle card border
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_width, card_y + card_height)],
        radius=card_radius,
        outline=divider_color,
        width=1
    )
    
    # === DRAW CONTENT ===
    content_x = card_x + card_padding
    current_y = card_y + 28
    
    # Title section
    title_text = " uvx cursor-wrapped"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((img_width - title_w) // 2, current_y), title_text, fill=gold_accent, font=title_font)
    current_y += 50
    
    # Divider
    draw.line([(content_x, current_y), (content_x + content_width, current_y)], fill=divider_color, width=1)
    current_y += section_spacing
    
    # === STATS SECTION ===
    stats_data = [
        ("Lines Accepted", f"{stats['accepted_lines_added']:,}"),
        ("Agent Requests", f"{stats['total_agent_requests']:,}"),
        ("Total Tokens", total_tokens),
        ("Tabs Accepted", tabs_val),
        ("Active Days", f"{stats['active_days']} / {total_days}"),
        ("Longest Streak", f"{stats['streak_longest']} days"),
    ]
    
    def draw_stat_row(y, label, value, highlight=False):
        # Draw label
        draw.text((content_x, y), label, fill=text_secondary, font=label_font)
        
        # Measure label width
        label_bbox = draw.textbbox((0, 0), label, font=label_font)
        label_w = label_bbox[2] - label_bbox[0]
        
        # Measure value width
        value_bbox = draw.textbbox((0, 0), value, font=value_font)
        value_w = value_bbox[2] - value_bbox[0]
        
        # Draw dot leaders
        dots_start = content_x + label_w + 10
        dots_end = content_x + content_width - value_w - 10
        dot_spacing = 8
        dot_y = y + 10
        
        for dot_x in range(int(dots_start), int(dots_end), dot_spacing):
            draw.ellipse([(dot_x, dot_y), (dot_x + 2, dot_y + 2)], fill=text_dim)
        
        # Draw value (right-aligned)
        value_color = secondary_accent if highlight else primary_accent
        draw.text((content_x + content_width - value_w, y), value, fill=value_color, font=value_font)
    
    for i, (label, value) in enumerate(stats_data):
        highlight = (i == 0)  # Highlight the first stat
        draw_stat_row(current_y, label, value, highlight)
        current_y += row_height
    
    current_y += 8
    
    # Divider
    draw.line([(content_x, current_y), (content_x + content_width, current_y)], fill=divider_color, width=1)
    current_y += section_spacing
    
    # === HIGHLIGHTS SECTION ===
    highlights_data = [
        ("Top Model", top_model),
        ("Favorite Coding Day", power_day),
    ]
    
    for label, value in highlights_data:
        # Draw star icon (simple text for now)
        star_text = "★"
        draw.text((content_x, current_y), star_text, fill=gold_accent, font=label_font)
        
        # Draw label
        draw.text((content_x + 24, current_y), label, fill=text_secondary, font=label_font)
        
        # Measure for value positioning
        full_label = star_text + " " + label
        label_bbox = draw.textbbox((0, 0), label, font=label_font)
        value_bbox = draw.textbbox((0, 0), value, font=value_font)
        value_w = value_bbox[2] - value_bbox[0]
        
        # Draw value (right-aligned)
        draw.text((content_x + content_width - value_w, current_y), value, fill=text_primary, font=value_font)
        current_y += row_height
    
    current_y += 8
    
    # Divider
    draw.line([(content_x, current_y), (content_x + content_width, current_y)], fill=divider_color, width=1)
    current_y += 14
    
    # === FOOTER ===
    footer_text = "github.com/riyapatel25/cursorWrapped"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=small_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    draw.text(((img_width - footer_w) // 2, current_y), footer_text, fill=text_dim, font=small_font)
    
    # Save to temp file (will be deleted after clipboard copy)
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(temp_file.name, "PNG")
    temp_file.close()
    return temp_file.name


def generate_ascii_card(wrapped_data):
    """Generate an ASCII card summary for sharing."""
    stats = wrapped_data['stats']
    acceptance_rate = wrapped_data['acceptance_rate']
    sorted_models = wrapped_data['sorted_models']
    best_day = wrapped_data['best_day']
    day_full = wrapped_data['day_full']
    total_days = wrapped_data.get('total_days', 199)
    token_stats = wrapped_data.get('token_stats')
    
    top_model = sorted_models[0][0] if sorted_models else "N/A"
    if 'claude' in top_model.lower():
        top_model = top_model.replace('claude-', '').replace('-', ' ').title()
    top_model = top_model[:18] if len(top_model) > 18 else top_model
    
    power_day = day_full[best_day] if best_day else "N/A"
    
    # Token stats
    total_tokens = "N/A"
    if token_stats:
        total_tok = token_stats.get('total_input_tokens', 0) + token_stats.get('total_output_tokens', 0)
        total_tokens = format_large_number(total_tok, " tokens")
    
    # Tab stats
    tab_shown = stats.get('total_tabs_shown', 0)
    tab_accepted = stats.get('total_tabs_accepted', 0)
    tab_rate = (tab_accepted / tab_shown * 100) if tab_shown > 0 else 0
    tabs_val = f"{tab_accepted:,} ({tab_rate:.0f}%)"
    
    # Pre-format values - all padded to exactly 15 chars
    lines_val = f"{stats['accepted_lines_added']:,}".rjust(15)
    requests_val = f"{stats['total_agent_requests']:,}".rjust(15)
    tokens_val = total_tokens.rjust(15)
    tabs_formatted = tabs_val.rjust(15)
    active_val = f"{stats['active_days']} / {total_days}".rjust(15)
    streak_val = f"{stats['streak_longest']} days".rjust(15)
    top_model_val = top_model.rjust(18)
    power_day_val = power_day.rjust(18)
    
    # Fixed width: 44 inner chars + 2 border chars = 46 total per line
    W = 44  # inner width
    
    lines = []
    lines.append("╔" + "═" * W + "╗")
    lines.append("║" + " " * W + "║")
    lines.append("║" + "✦ CURSOR WRAPPED 2025 ✦".center(W) + "║")
    lines.append("║" + " " * W + "║")
    lines.append("╠" + "═" * W + "╣")
    lines.append("║" + " " * W + "║")
    lines.append("║" + f"  Lines Accepted     {lines_val}      ".ljust(W) + "║")
    lines.append("║" + f"  Agent Requests     {requests_val}      ".ljust(W) + "║")
    lines.append("║" + f"  Total Tokens       {tokens_val}      ".ljust(W) + "║")
    lines.append("║" + f"  Tabs Accepted      {tabs_formatted}      ".ljust(W) + "║")
    lines.append("║" + f"  Active Days        {active_val}      ".ljust(W) + "║")
    lines.append("║" + f"  Longest Streak     {streak_val}      ".ljust(W) + "║")
    lines.append("║" + " " * W + "║")
    lines.append("╠" + "═" * W + "╣")
    lines.append("║" + " " * W + "║")
    lines.append("║" + f"  ★ Top Model   {top_model_val}       ".ljust(W) + "║")
    lines.append("║" + f"  ★ Favorite Coding Day   {power_day_val}       ".ljust(W) + "║")
    lines.append("║" + " " * W + "║")
    lines.append("╠" + "═" * W + "╣")
    lines.append("║" + "github.com/riyapatel25/cursorWrapped".center(W) + "║")
    lines.append("╚" + "═" * W + "╝")
    
    return "\n".join(lines)


def generate_imessage_text(wrapped_data):
    """Generate a text summary for iMessage sharing."""
    return generate_ascii_card(wrapped_data)


def generate_tweet(wrapped_data):
    """Generate a tweet for X/Twitter sharing."""
    stats = wrapped_data['stats']
    acceptance_rate = wrapped_data['acceptance_rate']
    
    # Keep it concise for Twitter
    tweet = f"""My Cursor Wrapped 2025 🚀

{stats['accepted_lines_added']:,} lines of AI code
{stats['total_agent_requests']:,} agent requests  
{stats['streak_longest']} day streak
{int(acceptance_rate)}% acceptance rate

Get yours ↓
github.com/riyapatel25/cursorWrapped"""
    
    return tweet


def copy_to_clipboard(text):
    """Copy text to clipboard (macOS/Linux/Windows)."""
    try:
        if sys.platform == 'darwin':
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return True
        elif sys.platform == 'linux':
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return True
        elif sys.platform == 'win32':
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            process.communicate(text.encode('utf-8'))
            return True
    except:
        pass
    return False


def copy_image_to_clipboard(filepath):
    """Copy image file to clipboard (macOS/Windows)."""
    try:
        abs_path = os.path.abspath(filepath)
        
        if sys.platform == 'darwin':
            # macOS - use osascript to copy PNG to clipboard
            script = f'''
            set theFile to POSIX file "{abs_path}"
            set theImage to read theFile as «class PNGf»
            set the clipboard to theImage
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True)
            return result.returncode == 0
            
        elif sys.platform == 'win32':
            # Windows - use PowerShell
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            $image = [System.Drawing.Image]::FromFile("{abs_path}")
            [System.Windows.Forms.Clipboard]::SetImage($image)
            '''
            result = subprocess.run(['powershell', '-Command', ps_script], capture_output=True)
            return result.returncode == 0
            
        elif sys.platform == 'linux':
            # Linux - use xclip
            result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', abs_path], capture_output=True)
            return result.returncode == 0
    except Exception as e:
        pass
    return False


def open_twitter_compose(tweet):
    """Open Twitter/X compose with pre-filled tweet."""
    encoded_tweet = urllib.parse.quote(tweet)
    url = f"https://twitter.com/intent/tweet?text={encoded_tweet}"
    
    try:
        if sys.platform == 'darwin':
            os.system(f'open "{url}"')
            return True
        elif sys.platform == 'linux':
            os.system(f'xdg-open "{url}"')
            return True
        elif sys.platform == 'win32':
            os.startfile(url)
            return True
    except:
        pass
    return False


def show_menu(wrapped_data):
    """Show replay/share menu after wrapped display."""
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    
    while True:
        print(f"  {CYAN}{BOLD}What would you like to do?{RESET}")
        print()
        print(f"  {WHITE}[1]{RESET} Replay Wrapped 🔄")
        print(f"  {WHITE}[2]{RESET} Share via iMessage 💬")
        print(f"  {WHITE}[3]{RESET} Share on 𝕏")
        print(f"  {WHITE}[4]{RESET} Exit")
        print()
        
        try:
            choice = input(f"  {WHITE}Enter choice (1-4):{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        
        if choice == '1':
            print("\033[2J\033[H", end="")
            print_wrapped_stats(
                wrapped_data['stats'], 
                wrapped_data['raw_data'], 
                wrapped_data['token_stats']
            )
        elif choice == '2':
            # iMessage - generate image, copy to clipboard, open Messages
            print()
            
            if HAS_PIL:
                print(f"  {DIM}Generating summary card image...{RESET}")
                temp_path = generate_terminal_image(wrapped_data)
                
                if temp_path:
                    try:
                        # Copy image to clipboard
                        if copy_image_to_clipboard(temp_path):
                            print(f"  {GREEN}✓{RESET} {WHITE}{BOLD}Summary card image{RESET} copied to clipboard!")
                            print(f"  {DIM}(A shareable image of your Cursor Wrapped stats){RESET}")
                            print()
                            print(f"  {DIM}{'─' * 50}{RESET}")
                            print()
                            print(f"  {WHITE}{BOLD}Ready to share!{RESET}")
                            print()
                            print(f"  {WHITE}1.{RESET} Messages will open")
                            print(f"  {WHITE}2.{RESET} Choose a contact to send to")
                            print(f"  {WHITE}3.{RESET} Press {CYAN}Cmd+V{RESET} to paste the summary image")
                            print(f"  {WHITE}4.{RESET} Send it!")
                            print()
                            print(f"  {DIM}{'─' * 50}{RESET}")
                            print()
                            
                            # Tab prompt to open Messages
                            print(f"  {CYAN}┌{'─' * 34}┐{RESET}")
                            print(f"  {CYAN}│{RESET}  {WHITE}{BOLD}⇥  Press Tab to open Messages{RESET}   {CYAN}│{RESET}")
                            print(f"  {CYAN}└{'─' * 34}┘{RESET}")
                            sys.stdout.flush()
                            
                            # Wait for Tab key
                            try:
                                import termios
                                import tty
                                fd = sys.stdin.fileno()
                                old_settings = termios.tcgetattr(fd)
                                try:
                                    tty.setraw(fd)
                                    while True:
                                        ch = sys.stdin.read(1)
                                        if ch == '\t' or ch == '\r' or ch == '\n':
                                            break
                                        elif ch == '\x03':
                                            raise KeyboardInterrupt
                                finally:
                                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                            except (ImportError, Exception):
                                input()  # Fallback
                            
                            # Open Messages app on macOS
                            if sys.platform == 'darwin':
                                subprocess.run(['open', '-a', 'Messages'], capture_output=True)
                                print(f"\n  {GREEN}✓{RESET} Messages opened! Paste your summary image with Cmd+V 💬")
                            else:
                                print(f"\n  {DIM}Open your messaging app and paste the image!{RESET}")
                        else:
                            print(f"  {YELLOW}⚠{RESET}  Could not copy image to clipboard")
                            # Fallback to text
                            text = generate_ascii_card(wrapped_data)
                            if copy_to_clipboard(text):
                                print(f"  {GREEN}✓{RESET} ASCII card copied to clipboard instead!")
                    finally:
                        # Clean up temp file - no data saved locally
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                    print()
            else:
                # Fallback without PIL
                print(f"  {YELLOW}⚠{RESET}  PIL/Pillow not installed for image generation.")
                print(f"  {DIM}Install with: pip install Pillow{RESET}")
                print()
                text = generate_ascii_card(wrapped_data)
                print(f"  {DIM}{'─' * 50}{RESET}")
                for line in text.split('\n'):
                    print(f"  {CYAN}{line}{RESET}")
                print(f"  {DIM}{'─' * 50}{RESET}")
                print()
                if copy_to_clipboard(text):
                    print(f"  {GREEN}✓{RESET} ASCII card copied to clipboard!")
                print()
            
        elif choice == '3':
            # X/Twitter - generate terminal screenshot and copy to clipboard
            print()
            
            if HAS_PIL:
                print(f"  {DIM}Generating summary card image...{RESET}")
                temp_path = generate_terminal_image(wrapped_data)
                
                if temp_path:
                    try:
                        # Copy image to clipboard
                        if copy_image_to_clipboard(temp_path):
                            print(f"  {GREEN}✓{RESET} {WHITE}{BOLD}Summary card image{RESET} copied to clipboard!")
                            print(f"  {DIM}(A shareable image of your Cursor Wrapped stats){RESET}")
                            print()
                            print(f"  {DIM}{'─' * 50}{RESET}")
                            print()
                            print(f"  {WHITE}{BOLD}Ready to share!{RESET}")
                            print()
                            print(f"  {WHITE}1.{RESET} X will open with your tweet text")
                            print(f"  {WHITE}2.{RESET} Press {CYAN}Cmd+V{RESET} (or Ctrl+V) to paste the summary image")
                            print(f"  {WHITE}3.{RESET} Tweet it!")
                            print()
                            print(f"  {DIM}{'─' * 50}{RESET}")
                            print()
                            
                            # Tab prompt to open X
                            print(f"  {CYAN}┌{'─' * 34}┐{RESET}")
                            print(f"  {CYAN}│{RESET}  {WHITE}{BOLD}⇥  Press Tab to open X{RESET}          {CYAN}│{RESET}")
                            print(f"  {CYAN}└{'─' * 34}┘{RESET}")
                            sys.stdout.flush()
                            
                            # Wait for Tab key
                            try:
                                import termios
                                import tty
                                fd = sys.stdin.fileno()
                                old_settings = termios.tcgetattr(fd)
                                try:
                                    tty.setraw(fd)
                                    while True:
                                        ch = sys.stdin.read(1)
                                        if ch == '\t' or ch == '\r' or ch == '\n':
                                            break
                                        elif ch == '\x03':
                                            raise KeyboardInterrupt
                                finally:
                                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                            except (ImportError, Exception):
                                input()  # Fallback
                            
                            # Open Twitter with simple tweet text
                            tweet = "here's my cursor 2025 wrapped:\n\n"
                            open_twitter_compose(tweet)
                            print(f"\n  {GREEN}✓{RESET} X opened! Paste your summary image with Cmd+V 🚀")
                        else:
                            print(f"  {YELLOW}⚠{RESET}  Could not copy image to clipboard")
                            print(f"  {WHITE}Take a screenshot of the summary above instead!{RESET}")
                            print()
                            
                            # Tab prompt to open X
                            print(f"  {CYAN}┌{'─' * 34}┐{RESET}")
                            print(f"  {CYAN}│{RESET}  {WHITE}{BOLD}⇥  Press Tab to open X{RESET}          {CYAN}│{RESET}")
                            print(f"  {CYAN}└{'─' * 34}┘{RESET}")
                            sys.stdout.flush()
                            
                            # Wait for Tab key
                            try:
                                import termios
                                import tty
                                fd = sys.stdin.fileno()
                                old_settings = termios.tcgetattr(fd)
                                try:
                                    tty.setraw(fd)
                                    while True:
                                        ch = sys.stdin.read(1)
                                        if ch == '\t' or ch == '\r' or ch == '\n':
                                            break
                                        elif ch == '\x03':
                                            raise KeyboardInterrupt
                                finally:
                                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                            except (ImportError, Exception):
                                input()  # Fallback
                            
                            tweet = "here's my cursor 2025 wrapped:\n\ngithub.com/riyapatel25/cursorWrapped"
                            open_twitter_compose(tweet)
                    finally:
                        # Clean up temp file - no data saved locally
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                    print()
            else:
                print(f"  {YELLOW}⚠{RESET}  PIL/Pillow not installed for image generation.")
                print(f"  {DIM}Install with: pip install Pillow{RESET}")
                print()
                
                # Fallback to manual screenshot
                print(f"  {CYAN}{BOLD}📸 Screenshot this summary instead:{RESET}")
                print()
                card = generate_ascii_card(wrapped_data)
                for line in card.split('\n'):
                    print(f"  {CYAN}{line}{RESET}")
                print()
                
                tweet = "here's my cursor 2025 wrapped:\n\ngithub.com/riyapatel25/cursorWrapped"
                if copy_to_clipboard(tweet):
                    print(f"  {GREEN}✓{RESET} Tweet text copied!")
                print()
                input(f"  {DIM}Press Enter after taking screenshot...{RESET}")
                open_twitter_compose(tweet)
                print()
            
        elif choice == '4':
            print(f"\n  {DIM}Keep shipping! 🚀{RESET}\n")
            break
        else:
            print(f"\n  {DIM}Invalid choice. Please enter 1-4.{RESET}\n")


def main():
    """Main function."""
    
    auth_cookie = get_auth_cookie()
    
    if not auth_cookie:
        print("\nCould not get auth token. Please try again.")
        return
    
    raw_data = fetch_yearly_analytics(auth_cookie)
    
    if not raw_data:
        print("\nCould not fetch analytics data.")
        return
    
    token_events = fetch_token_usage(auth_cookie)
    token_stats = analyze_token_usage(token_events) if token_events else None
    
    stats = analyze_yearly_data(raw_data)
    
    wrapped_data = print_wrapped_stats(stats, raw_data, token_stats)
    
    if wrapped_data:
        wrapped_data['raw_data'] = raw_data
        wrapped_data['token_stats'] = token_stats
        show_menu(wrapped_data)


if __name__ == "__main__":
    main()
