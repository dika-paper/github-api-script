#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub PR Code Review Report Generator

This script generates reports for code review comments from a specific GitHub user.
It only includes comments on OTHER people's PRs (excludes self-reviews).
For production use, consider using the PyGithub library instead of raw HTTP requests.

Requirements:
    pip install python-dotenv

Usage:
    python review.py --help
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
        "User-Agent": "PR-Comment-Report/1.0"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            # Validate response structure
            if not isinstance(data, dict) and not isinstance(data, list):
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

def get_filtered_prs(query):
    """Get PRs that match the query with pagination."""
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

def get_pr_comments(pr_number, username):
    """Get comments from a specific PR by a specific user."""
    comments_url = f"https://api.github.com/repos/{ORGANIZATION}/{REPOSITORY}/issues/{pr_number}/comments"
    
    comments_data = github_request(comments_url)
    if not comments_data or not isinstance(comments_data, list):
        return []
    
    # Filter comments by the specified username
    user_comments = []
    for comment in comments_data:
        if not isinstance(comment, dict):
            continue
            
        comment_user = comment.get('user', {})
        if not isinstance(comment_user, dict):
            continue
            
        if comment_user.get('login', '').lower() == username.lower():
            user_comments.append({
                'id': comment.get('id', 0),
                'body': comment.get('body', ''),
                'created_at': comment.get('created_at', ''),
                'updated_at': comment.get('updated_at', ''),
                'url': comment.get('html_url', '')
            })
    
    return user_comments

def process_prs_for_comments(items, username, batch_size=25):
    """Process PRs in batches to find comments from specific user."""
    progress_file = f"comment_processing_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Try to load existing progress
    progress = load_progress(progress_file)
    if progress:
        print(f"Resuming from previous progress: {len(progress.get('processed', []))} PRs already processed")
        processed_prs = progress.get('processed', [])
        start_index = len(processed_prs)
        all_comments = progress.get('all_comments', [])
    else:
        processed_prs = []
        start_index = 0
        all_comments = []
    
    for i in range(start_index, len(items), batch_size):
        batch = items[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}: PRs {i+1}-{min(i+batch_size, len(items))} of {len(items)}")
        
        batch_comments = []
        
        for j, pr in enumerate(batch):
            pr_index = i + j + 1
            pr_number = pr.get('number', 0)
            pr_title = pr.get('title', 'Unknown Title')
            
            # Double-check: Skip if this PR was created by the same user (safety check)
            pr_author = pr.get('user', {}).get('login', '') if isinstance(pr.get('user'), dict) else ''
            if pr_author.lower() == username.lower():
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping self-authored PR")
                continue
            
            # Get PR details to check target branch
            pr_detail_url = pr.get('pull_request', {}).get('url')
            if not pr_detail_url:
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping - no PR detail URL")
                continue
                
            pr_details = github_request(pr_detail_url)
            if not pr_details or not isinstance(pr_details, dict):
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping - failed to get PR details")
                continue
            
            # Check if target branch is staging or starts with 'release/'
            base_info = pr_details.get('base')
            if not isinstance(base_info, dict):
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping - invalid base branch info")
                continue
                
            base_branch = base_info.get('ref', '')
            if not isinstance(base_branch, str):
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping - invalid base branch")
                continue
                
            if base_branch != 'staging' and not base_branch.startswith('release/'):
                print(f"  {pr_index}/{len(items)}: PR #{pr_number}: Skipping - targeting {base_branch}")
                continue
            
            print(f"  {pr_index}/{len(items)}: PR #{pr_number}: {pr_title[:50]}... (target: {base_branch})")
            
            # Get comments for this PR
            pr_comments = get_pr_comments(pr_number, username)
            
            if pr_comments:
                print(f"    Found {len(pr_comments)} comment(s)")
                for comment in pr_comments:
                    comment_info = {
                        'pr_number': pr_number,
                        'pr_title': pr_title,
                        'pr_author': pr_author,
                        'target_branch': base_branch,
                        'pr_url': pr.get('html_url', ''),
                        'comment_id': comment['id'],
                        'comment_body': comment['body'][:200] + '...' if len(comment['body']) > 200 else comment['body'],
                        'comment_full_body': comment['body'],
                        'created_at': comment['created_at'],
                        'updated_at': comment['updated_at'],
                        'comment_url': comment['url']
                    }
                    batch_comments.append(comment_info)
            else:
                print(f"    No comments from {username}")
            
            # Small delay between requests
            time.sleep(0.1)
        
        # Add batch results to main list
        all_comments.extend(batch_comments)
        processed_prs.extend(batch)
        
        # Save progress after each batch
        progress_data = {
            'timestamp': datetime.now().isoformat(),
            'total_prs': len(items),
            'processed_count': len(processed_prs),
            'comments_found': len(all_comments),
            'processed': processed_prs,
            'all_comments': all_comments
        }
        save_progress(progress_data, progress_file)
        
        print(f"  Batch complete: {len(batch_comments)} comments found in this batch")
        print(f"  Total so far: {len(all_comments)} comments from {len(processed_prs)} processed PRs")
    
    return all_comments, progress_file

def generate_final_report(all_comments, progress_file, sprint_name, username):
    """Generate the final CSV report."""
    if not all_comments:
        print(f"No comments found from user {username}!")
        return
    
    # Sort by created date (oldest first)
    all_comments.sort(key=lambda x: x['created_at'], reverse=False)
    
    # Generate timestamp and filename with sprint info
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"csvs/{username}-comments-sprint-{sprint_name}-{timestamp}.csv"
    
    # Create csvs directory if it doesn't exist
    os.makedirs('csvs', exist_ok=True)
    
    # Define CSV headers
    headers = [
        'PR Number', 'PR Title', 'PR Author', 'Target Branch', 'Comment ID', 'Comment Preview', 
        'Created At', 'Updated At', 'PR URL', 'Comment URL'
    ]
    
    # Write CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        for comment in all_comments:
            writer.writerow([
                comment['pr_number'],
                comment['pr_title'],
                comment['pr_author'],
                comment['target_branch'],
                comment['comment_id'],
                comment['comment_body'],
                comment['created_at'],
                comment['updated_at'],
                comment['pr_url'],
                comment['comment_url']
            ])
    
    # Also save full comment bodies to a separate JSON file for reference
    json_filename = f"csvs/{username}-comments-full-sprint-{sprint_name}-{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(all_comments, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"\nComplete CSV report saved to: {filename}")
    print(f"Full comment details saved to: {json_filename}")
    print(f"Found {len(all_comments)} comments from {username}")
    
    # Count unique PRs
    unique_prs = len(set(comment['pr_number'] for comment in all_comments))
    print(f"Comments across {unique_prs} different PRs")
    
    # Clean up progress file
    if os.path.exists(progress_file):
        os.remove(progress_file)
        print(f"Cleaned up progress file: {progress_file}")
    
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
        description='Generate GitHub PR code review reports for a specific user using sprint date ranges (excludes self-reviews)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''Environment Variables:
  GITHUB_TOKEN        GitHub personal access token (required)
  GITHUB_ORGANIZATION GitHub organization name (default: paper-indonesia)
  GITHUB_REPOSITORY   GitHub repository name (default: paperangularapp)
  GITHUB_USERNAME     GitHub username to analyze (default: dika-paper)

Available Sprints:
  {available_sprints}

Example:
  python review.py --sprint 224 --user reviewer-username
  python review.py --sprint 225 --org myorg --repo myrepo --user reviewer
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
                       help='GitHub username to find comments from (overrides env var)')
    parser.add_argument('--sprint', 
                       required=True,
                       help=f'Sprint name from config. Available: {available_sprints}')
    parser.add_argument('--batch-size', 
                       type=int, default=25,
                       help='Batch size for processing PRs (default: 25)')
    
    return parser.parse_args()

def main():
    print("PR Code Review Report Generator (Excludes Self-Reviews)")
    print("=" * 55)
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Use command line args or environment variables
    global ORGANIZATION, REPOSITORY
    ORGANIZATION = args.org or ORGANIZATION
    REPOSITORY = args.repo or REPOSITORY  
    username = args.user or USERNAME
    
    # Validate required configuration
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is required")
        print("Please set your GitHub token in the .env file or environment")
        return 1
    
    if not all([ORGANIZATION, REPOSITORY, username]):
        print("Error: Organization, repository, and username are required")
        print(f"Current values: org={ORGANIZATION}, repo={REPOSITORY}, user={username}")
        return 1
    
    # Get sprint dates
    try:
        start_date, end_date = get_sprint_dates(args.sprint)
        print(f"Sprint {args.sprint}: {start_date} to {end_date}")
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    # Search for PRs within sprint date range, excluding the user's own PRs
    # We'll filter for staging and release/* branches during processing since GitHub search doesn't support wildcards
    query = f"is:pr repo:{ORGANIZATION}/{REPOSITORY} created:{start_date}..{end_date} -author:{username}"
    print(f"Query: {query}")
    print(f"Searching PRs targeting staging or release/* branches for comments from user: {username} (excluding their own PRs)")
    
    print("\nStep 1: Fetching PRs (excluding user's own PRs)...")
    items, total_count = get_filtered_prs(query)
    print(f"Found {len(items)} PRs to check out of {total_count} total")
    
    if not items:
        print("No PRs found!")
        return 0
    
    print(f"\nStep 2: Checking {len(items)} PRs for comments from {username}...")
    all_comments, progress_file = process_prs_for_comments(items, username, batch_size=args.batch_size)
    
    print(f"\nStep 3: Generating final report...")
    report_filename = generate_final_report(all_comments, progress_file, args.sprint, username)
    
    print(f"\nDone! Check {report_filename} for the complete report.")
    return 0

if __name__ == "__main__":
    exit(main())