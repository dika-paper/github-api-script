#!/usr/bin/env python3
"""
GitHub Commit List Generator for Sprint Analysis

This script lists commits for a specific user within a sprint date range.
Adapted from the PR report generator for commit analysis purposes.

Requirements:
    pip install python-dotenv

Usage:
    python commit.py --help
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
        "User-Agent": "Commit-List/1.0"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason} for {url}")
        return None
    except Exception as e:
        print(f"Error requesting {url}: {e}")
        return None

def get_all_commits_fast(org, repo, user, since_date, until_date):
    """Get all commits with pagination for a specific user and date range."""
    all_commits = []
    page = 1
    per_page = 100
    
    while True:
        commits_url = f"https://api.github.com/repos/{org}/{repo}/commits?author={user}&since={since_date}T00:00:00Z&until={until_date}T23:59:59Z&per_page={per_page}&page={page}"
        
        print(f"Fetching page {page}...")
        commits_data = github_request(commits_url)
        
        if not commits_data:
            print(f"Failed to get page {page}")
            break
        
        if not isinstance(commits_data, list):
            print(f"Invalid commits response format on page {page}")
            break
        
        if not commits_data:
            print(f"No more commits on page {page}")
            break
            
        all_commits.extend(commits_data)
        print(f"Got {len(commits_data)} commits from page {page} (total so far: {len(all_commits)})")
        
        if len(commits_data) < per_page:
            break
            
        page += 1
        time.sleep(0.3)
    
    return all_commits, len(all_commits)

def process_commits_for_listing(commits):
    """Process commits to get detailed information for listing."""
    commit_list = []
    
    for i, commit in enumerate(commits):
        commit_index = i + 1
        commit_info = commit.get('commit', {})
        commit_sha = commit.get('sha', '')[:7]
        commit_message = commit_info.get('message', '').split('\n')[0]  # First line only
        
        print(f"  {commit_index}/{len(commits)}: {commit_sha}: {commit_message[:50]}...")
        
        # Get commit stats (additions/deletions/files)
        commit_detail_url = commit.get('url')
        commit_stats = {'additions': 0, 'deletions': 0, 'files': 0}
        
        if commit_detail_url:
            commit_details = github_request(commit_detail_url)
            if commit_details and isinstance(commit_details, dict):
                stats = commit_details.get('stats', {})
                commit_stats = {
                    'additions': stats.get('additions', 0),
                    'deletions': stats.get('deletions', 0),
                    'files': len(commit_details.get('files', []))
                }
        
        # Extract commit information
        author_info = commit_info.get('author', {})
        committer_info = commit_info.get('committer', {})
        
        # Skip merge commits by GitHub
        if committer_info.get('name', '') == 'GitHub':
            print(f"    Skipping GitHub merge commit")
            continue
        
        # Skip merge commits by message
        if commit_message.startswith('Merge branch'):
            print(f"    Skipping merge branch commit")
            continue
        
        commit_data = {
            'sha': commit.get('sha', ''),
            'short_sha': commit_sha,
            'message': commit_message,
            'full_message': commit_info.get('message', ''),
            'author_name': author_info.get('name', ''),
            'author_email': author_info.get('email', ''),
            'author_date': author_info.get('date', ''),
            'committer_name': committer_info.get('name', ''),
            'committer_date': committer_info.get('date', ''),
            'lines_added': commit_stats['additions'],
            'lines_deleted': commit_stats['deletions'],
            'files_changed': commit_stats['files'],
            'url': commit.get('html_url', '')
        }
        
        commit_list.append(commit_data)
        print(f"    ✓ Added: +{commit_data['lines_added']} -{commit_data['lines_deleted']} files:{commit_data['files_changed']}")
        
        time.sleep(0.1)
    
    return commit_list

def generate_commit_list_report(commit_list, sprint_name, user):
    """Generate the final CSV report with commit list."""
    if not commit_list:
        print("No commits found!")
        return
    
    # Sort by commit date (ascending - oldest to newest)
    commit_list.sort(key=lambda x: x['author_date'], reverse=False)
    
    # Generate timestamp and filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"csvs/{user}-commit-list-sprint-{sprint_name}-{timestamp}.csv"
    
    # Ensure csvs directory exists
    os.makedirs('csvs', exist_ok=True)
    
    # Define CSV headers
    headers = [
        'Sprint', 'SHA', 'Short SHA', 'Message', 'Author Name', 'Author Email',
        'Author Date', 'Committer Name', 'Committer Date',
        'Lines Added', 'Lines Deleted', 'Net Lines', 'Files Changed', 'URL'
    ]
    
    # Write CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        for commit in commit_list:
            net_lines = commit['lines_added'] - commit['lines_deleted']
            
            writer.writerow([
                sprint_name,
                commit['sha'],
                commit['short_sha'],
                commit['message'],
                commit['author_name'],
                commit['author_email'],
                commit['author_date'],
                commit['committer_name'],
                commit['committer_date'],
                commit['lines_added'],
                commit['lines_deleted'],
                net_lines,
                commit['files_changed'],
                commit['url']
            ])
    
    print(f"\n🎉 Complete commit list saved to: {filename}")
    print(f"📊 Found {len(commit_list)} commits for user {user}")
    print(f"📈 Total lines added: {sum(commit['lines_added'] for commit in commit_list):,}")
    print(f"📉 Total lines deleted: {sum(commit['lines_deleted'] for commit in commit_list):,}")
    print(f"📊 Net lines: {sum(commit['lines_added'] - commit['lines_deleted'] for commit in commit_list):,}")
    print(f"📁 Total files changed: {sum(commit['files_changed'] for commit in commit_list):,}")
    
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
        description='List GitHub commits for a specific user within sprint date ranges',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''Environment Variables:
  GITHUB_TOKEN        GitHub personal access token (required)
  GITHUB_ORGANIZATION GitHub organization name (default: paper-indonesia)
  GITHUB_REPOSITORY   GitHub repository name (default: paperangularapp)
  GITHUB_USERNAME     GitHub username to analyze (default: dika-paper)

Available Sprints:
  {available_sprints}

Example:
  python commit.py --sprint 224 --user dika-paper
  python commit.py --sprint 225 --org myorg --repo myrepo --user myuser
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
    
    return parser.parse_args()

def main():
    print("🚀 Commit List Generator for Sprint Analysis")
    print("=" * 50)
    
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
    
    # Search for all commits within sprint date range for the specified user
    print(f"Fetching commits for {user} from {start_date} to {end_date}")
    
    print("\n📥 Step 1: Fetching all commit metadata with pagination...")
    commits, total_count = get_all_commits_fast(org, repo, user, start_date, end_date)
    print(f"✅ Found {len(commits)} commits out of {total_count} total")
    
    if not commits:
        print("❌ No commits found!")
        return 0
    
    print(f"\n🔍 Step 2: Processing {len(commits)} commits to get detailed information...")
    commit_list = process_commits_for_listing(commits)
    
    print(f"\n📝 Step 3: Generating commit list report...")
    report_filename = generate_commit_list_report(commit_list, args.sprint, user)
    
    print(f"\n✨ Done! Check {report_filename} for the complete commit list.")
    return 0

if __name__ == "__main__":
    exit(main())