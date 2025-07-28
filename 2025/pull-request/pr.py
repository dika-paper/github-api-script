#!/usr/bin/env python3
"""
GitHub PR Report Generator

This script generates reports for pull requests targeting release branches.
For production use, consider using the PyGithub library instead of raw HTTP requests.

Requirements:
    pip install python-dotenv

Usage:
    python pr_report.py --help
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime
import os
import time
import argparse
import csv
import sys
from dotenv import load_dotenv

# Load environment variables from root directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add parent directory to path for sprint_config import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from sprint_config import config as sprint_config

# Configuration from environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
ORGANIZATION = os.getenv('GITHUB_ORGANIZATION', 'paper-indonesia')
REPOSITORY = os.getenv('GITHUB_REPOSITORY', 'paperangularapp')
USERNAME = os.getenv('GITHUB_USERNAME', 'dika-paper')

def github_request(url):
    """Make a simple GitHub API request with validation."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PR-Report/1.0"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            # Validate response structure
            if not isinstance(data, dict):
                print(f"Warning: Unexpected response format from {url}")
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason} for {url}")
        return None
    except Exception as e:
        print(f"Error requesting {url}: {e}")
        return None

def save_progress(data, filename):
    """Save progress to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Progress saved to {filename}")

def load_progress(filename):
    """Load progress from a JSON file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return None

def get_all_prs_fast(query):
    """Get all PRs with pagination, but only basic info."""
    all_items = []
    page = 1
    per_page = 100
    
    while True:
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://api.github.com/search/issues?q={encoded_query}&per_page={per_page}&page={page}"
        
        print(f"Fetching page {page}...")
        search_data = github_request(search_url)
        
        if not search_data:
            print(f"Failed to get page {page}")
            break
        
        # Validate search response structure
        if not isinstance(search_data, dict):
            print(f"Invalid search response format on page {page}")
            break
            
        items = search_data.get('items', [])
        total_count = search_data.get('total_count', 0)
        
        # Validate items is a list
        if not isinstance(items, list):
            print(f"Invalid items format on page {page}")
            break
        
        if not items:
            print(f"No more items on page {page}")
            break
            
        all_items.extend(items)
        print(f"Got {len(items)} PRs from page {page} (total so far: {len(all_items)}/{total_count})")
        
        if len(items) < per_page or len(all_items) >= total_count:
            break
            
        page += 1
        
        # Small delay to be nice to the API
        time.sleep(0.3)
    
    return all_items, search_data.get('total_count', len(all_items)) if search_data else len(all_items)

def process_prs_in_batches(items, batch_size=50):
    """Process PRs in batches with progress saving."""
    progress_file = f"pr_processing_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Try to load existing progress
    progress = load_progress(progress_file)
    if progress:
        print(f"Resuming from previous progress: {len(progress.get('processed', []))} PRs already processed")
        processed_prs = progress.get('processed', [])
        start_index = len(processed_prs)
    else:
        processed_prs = []
        start_index = 0
    
    release_prs = []
    
    for i in range(start_index, len(items), batch_size):
        batch = items[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}: PRs {i+1}-{min(i+batch_size, len(items))} of {len(items)}")
        
        batch_release_prs = []
        
        for j, pr in enumerate(batch):
            pr_index = i + j + 1
            print(f"  {pr_index}/{len(items)}: PR #{pr.get('number')}: {pr.get('title')[:50]}...")
            
            # Get PR details to check target branch
            pr_detail_url = pr.get('pull_request', {}).get('url')
            if not pr_detail_url:
                print(f"    Skipping - no PR detail URL")
                continue
                
            pr_details = github_request(pr_detail_url)
            if not pr_details or not isinstance(pr_details, dict):
                print(f"    Skipping - failed to get valid PR details")
                continue
            
            # Check if target branch starts with 'release/' with validation
            base_info = pr_details.get('base')
            if not isinstance(base_info, dict):
                print(f"    Skipping - invalid base branch info")
                continue
                
            base_branch = base_info.get('ref', '')
            if not isinstance(base_branch, str) or not base_branch.startswith('release/'):
                print(f"    Skipping - targeting {base_branch}")
                continue
            
            # Collect data for release PRs with validation
            head_info = pr_details.get('head', {})
            origin_branch = head_info.get('ref', '') if isinstance(head_info, dict) else ''
            
            pr_info = {
                'number': pr.get('number', 0),
                'title': pr.get('title', ''),
                'target_branch': base_branch,
                'origin_branch': origin_branch,
                'lines_added': pr_details.get('additions', 0) or 0,
                'lines_deleted': pr_details.get('deletions', 0) or 0,
                'created_at': pr.get('created_at', ''),
                'merged_at': pr_details.get('merged_at'),
                'state': pr.get('state', 'unknown'),
                'url': pr.get('html_url', '')
            }
            
            batch_release_prs.append(pr_info)
            print(f"    ✓ Added: {pr_info['origin_branch']} -> {pr_info['target_branch']}")
            
            # Small delay between requests
            time.sleep(0.1)
        
        # Add batch results to main list
        release_prs.extend(batch_release_prs)
        processed_prs.extend(batch)
        
        # Save progress after each batch
        progress_data = {
            'timestamp': datetime.now().isoformat(),
            'total_prs': len(items),
            'processed_count': len(processed_prs),
            'release_prs_found': len(release_prs),
            'processed': processed_prs,
            'release_prs': release_prs
        }
        save_progress(progress_data, progress_file)
        
        print(f"  Batch complete: {len(batch_release_prs)} release PRs found in this batch")
        print(f"  Total so far: {len(release_prs)} release PRs out of {len(processed_prs)} processed")
    
    return release_prs, progress_file

def generate_final_report(release_prs, progress_file, sprint_name):
    """Generate the final CSV report."""
    if not release_prs:
        print("No release PRs found!")
        return
    
    # Sort by PR number (descending)
    release_prs.sort(key=lambda x: x['number'], reverse=True)
    
    # Generate timestamp and filename with sprint info
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"csvs/dika-pr-sprint-{sprint_name}-{timestamp}.csv"
    
    # Define CSV headers
    headers = [
        'PR Number', 'Title', 'Target Branch', 'Origin Branch', 
        'Lines Added', 'Lines Deleted', 'Net Lines', 'Status', 
        'Created At', 'Merged At', 'URL'
    ]
    
    # Write CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        for pr in release_prs:
            status = "Merged" if pr['merged_at'] else pr['state'].title()
            net_lines = pr['lines_added'] - pr['lines_deleted']

            print(f"📈 PR #{pr}")
            
            writer.writerow([
                pr['number'],
                pr['title'],
                pr['target_branch'],
                pr['origin_branch'],
                pr['lines_added'],
                pr['lines_deleted'],
                net_lines,
                status,
                pr['created_at'],
                pr['merged_at'] or '',
                pr['url']
            ])
    
    print(f"\n🎉 Complete CSV report saved to: {filename}")
    print(f"📊 Found {len(release_prs)} PRs targeting release/* branches")
    print(f"📈 Total lines added: {sum(pr['lines_added'] for pr in release_prs):,}")
    print(f"📉 Total lines deleted: {sum(pr['lines_deleted'] for pr in release_prs):,}")
    print(f"📊 Net lines: {sum(pr['lines_added'] - pr['lines_deleted'] for pr in release_prs):,}")
    
    # Clean up progress file
    if os.path.exists(progress_file):
        os.remove(progress_file)
        print(f"🧹 Cleaned up progress file: {progress_file}")
    
    return filename

def get_sprint_dates(sprint_name):
    """Get start and end dates for a sprint from sprint_config."""
    if sprint_name not in sprint_config:
        available_sprints = ', '.join(sorted(sprint_config.keys()))
        raise ValueError(f"Sprint '{sprint_name}' not found. Available sprints: {available_sprints}")
    
    sprint_data = sprint_config[sprint_name]
    return sprint_data['start_date'], sprint_data['end_date']

def parse_arguments():
    """Parse command line arguments."""
    available_sprints = ', '.join(sorted(sprint_config.keys()))
    
    parser = argparse.ArgumentParser(
        description='Generate GitHub PR reports for release branches using sprint date ranges',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''Environment Variables:
  GITHUB_TOKEN        GitHub personal access token (required)
  GITHUB_ORGANIZATION GitHub organization name (default: paper-indonesia)
  GITHUB_REPOSITORY   GitHub repository name (default: paperangularapp)
  GITHUB_USERNAME     GitHub username to analyze (default: dika-paper)

Available Sprints:
  {available_sprints}

Example:
  python pr.py --sprint 224 --batch-size 50
  python pr.py --sprint 225 --org myorg --repo myrepo --user myuser
'''
    )
    
    parser.add_argument('--org', '--organization', 
                       default=None,
                       help='GitHub organization (overrides env var)')
    parser.add_argument('--repo', '--repository',
                       default=None, 
                       help='GitHub repository (overrides env var)')
    parser.add_argument('--user', '--username',
                       default=None,
                       help='GitHub username to analyze (overrides env var)')
    parser.add_argument('--sprint', 
                       required=True,
                       help=f'Sprint name from config. Available: {available_sprints}')
    parser.add_argument('--batch-size', 
                       type=int, default=25,
                       help='Batch size for processing PRs (default: 25)')
    parser.add_argument('--branch-prefix',
                       default='release/',
                       help='Target branch prefix to filter (default: release/)')
    
    return parser.parse_args()

def main():
    print("🚀 Fast PR Report Generator with Pagination & Progress Saving")
    print("=" * 60)
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Use command line args or environment variables
    org = args.org or ORGANIZATION
    repo = args.repo or REPOSITORY  
    user = args.user or USERNAME
    
    # Validate required configuration
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN environment variable is required")
        print("Please set your GitHub token in the .env file or environment")
        return 1
    
    if not all([org, repo, user]):
        print("❌ Error: Organization, repository, and username are required")
        print(f"Current values: org={org}, repo={repo}, user={user}")
        return 1
    
    # Get sprint dates
    try:
        start_date, end_date = get_sprint_dates(args.sprint)
        print(f"Sprint {args.sprint}: {start_date} to {end_date}")
    except ValueError as e:
        print(f"❌ Error: {e}")
        return 1
    
    # Search for all PRs within sprint date range
    query = f"is:pr author:{user} repo:{org}/{repo} created:{start_date}..{end_date}"
    print(f"Query: {query}")
    print(f"Branch filter: {args.branch_prefix}*")
    
    print("\n📥 Step 1: Fetching all PR metadata with pagination...")
    items, total_count = get_all_prs_fast(query)
    print(f"✅ Found {len(items)} PRs out of {total_count} total")
    
    if not items:
        print("❌ No PRs found!")
        return 0
    
    print(f"\n🔍 Step 2: Processing {len(items)} PRs in batches to find {args.branch_prefix}* targets...")
    release_prs, progress_file = process_prs_in_batches(items, batch_size=args.batch_size)
    
    print(f"\n📝 Step 3: Generating final report...")
    report_filename = generate_final_report(release_prs, progress_file, args.sprint)
    
    print(f"\n✨ Done! Check {report_filename} for the complete report.")
    return 0

if __name__ == "__main__":
    exit(main())