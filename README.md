"# GitHub API Sprint Analytics

A collection of Python scripts for generating GitHub analytics reports based on sprint date ranges. Designed for OKR tracking and developer productivity analysis.

## 🚀 Quick Start

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Configure environment variables by copying `.env-example` to `.env`:
   ```bash
   cp .env-example .env
   ```

4. Edit `.env` with your GitHub configuration:
   ```
   GITHUB_TOKEN="your_github_token_here"
   GITHUB_ORGANIZATION="your-org"
   GITHUB_REPOSITORY="your-repo"
   GITHUB_USERNAME="your-username"
   ```

## 📊 Available Scripts

### 1. Pull Request Reports (`2025/pull-request/pr.py`)

Generates CSV reports of pull requests targeting release branches within sprint date ranges.

**Usage:**
```bash
python3 2025/pull-request/pr.py --sprint 236 --batch-size 50
```

**Options:**
- `--sprint` (required): Sprint number (236, 237, etc.)
- `--org`: GitHub organization (overrides env var)
- `--repo`: GitHub repository (overrides env var)  
- `--user`: GitHub username to analyze (overrides env var)
- `--batch-size`: Batch size for processing (default: 25)
- `--branch-prefix`: Target branch prefix (default: "release/")

**Output:** `csvs/dika-pr-sprint-{sprint}-{timestamp}.csv`

### 2. Commit Reports (`2025/commit/commit.py`)

Lists commits by a specific user within sprint date ranges.

**Usage:**
```bash
python3 2025/commit/commit.py --sprint 236 --user dika-paper
```

**Options:**
- `--sprint` (required): Sprint number
- `--org`: GitHub organization (overrides env var)
- `--repo`: GitHub repository (overrides env var)
- `--user`: GitHub username to analyze (overrides env var)

**Output:** `csvs/{user}-commit-list-sprint-{sprint}-{timestamp}.csv`

### 3. Code Review Reports (`2025/code-review/review.py`)

Tracks code review comments from a specific user on other people's PRs (excludes self-reviews).

**Usage:**
```bash
python3 2025/code-review/review.py --sprint 236 --user reviewer-username
```

**Options:**
- `--sprint` (required): Sprint number
- `--org`: GitHub organization (overrides env var)
- `--repo`: GitHub repository (overrides env var)
- `--user`: GitHub username to find comments from (overrides env var)
- `--batch-size`: Batch size for processing (default: 25)

**Output:** 
- `csvs/{user}-comments-sprint-{sprint}-{timestamp}.csv`
- `csvs/{user}-comments-full-sprint-{sprint}-{timestamp}.json`

## 📅 Sprint Configuration

Available sprints are defined in `2025/sprint_config.py`:
- Sprint 234: 2025-06-10 to 2025-06-23
- Sprint 235: 2025-06-24 to 2025-07-07  
- Sprint 236: 2025-07-08 to 2025-07-21
- Sprint 237: 2025-07-21 to 2025-08-05

## 📈 Features

- **Progress Tracking**: Scripts can resume from interruptions
- **Batch Processing**: Handles large datasets efficiently
- **Rate Limiting**: Respects GitHub API limits
- **Comprehensive Reports**: Includes lines added/deleted, file counts, URLs
- **Flexible Configuration**: Command-line overrides for all settings

## 🔧 Requirements

- Python 3.8+
- GitHub Personal Access Token
- `python-dotenv` package

## 📝 Output Format

All scripts generate CSV reports with detailed metrics:
- PR reports: Target branches, code changes, merge status
- Commit reports: Author info, file changes, commit messages
- Review reports: Comment details, PR context, review activity" 
