# Greenland Monitor — GitHub Deployment Guide

Complete step-by-step instructions to deploy the tracker on GitHub with automated monitoring.

---

## Prerequisites

- GitHub account (free tier works)
- Git installed locally
- ~10 minutes

---

## Step 1: Download and Extract

```bash
# Download the zip file from Claude's response
# Then extract it:
unzip greenland-monitor.zip
cd greenland_tracker
```

You should see:
```
greenland_tracker/
├── .github/
│   └── workflows/
│       └── monitor.yml      # GitHub Actions automation
├── data/
│   └── .gitkeep
├── docs/
│   └── .gitkeep
├── greenland_monitor.py     # Main tracker
├── analyze.py               # Pattern analysis
├── requirements.txt
└── README.md
```

---

## Step 2: Create GitHub Repository

### Option A: Using GitHub CLI (recommended)

```bash
# Install GitHub CLI if needed: https://cli.github.com/
# Then authenticate:
gh auth login

# Create repo and push in one command:
gh repo create greenland-monitor --public --source=. --push
```

### Option B: Manual via GitHub.com

1. Go to https://github.com/new
2. Repository name: `greenland-monitor`
3. Description: `Track aircraft over Greenland for mining intelligence`
4. Select **Public**
5. Do NOT initialize with README (we have one)
6. Click **Create repository**

Then push locally:
```bash
# Initialize git in the folder
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: Greenland airspace monitor"

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/greenland-monitor.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Step 3: Enable GitHub Actions Write Permissions

**This is critical — without it, the workflow can't save data.**

1. Go to your repo: `https://github.com/YOUR_USERNAME/greenland-monitor`
2. Click **Settings** (top menu, far right)
3. Left sidebar → **Actions** → **General**
4. Scroll to **Workflow permissions**
5. Select **"Read and write permissions"**
6. Check **"Allow GitHub Actions to create and approve pull requests"**
7. Click **Save**

![Workflow permissions setting](https://docs.github.com/assets/cb-40028/mw-1440/images/help/settings/actions-workflow-permissions-repository.webp)

---

## Step 4: Enable GitHub Pages

This hosts your live map at `https://YOUR_USERNAME.github.io/greenland-monitor/`

1. Still in **Settings**
2. Left sidebar → **Pages**
3. Under **Source**, select:
   - Branch: `main`
   - Folder: `/docs`
4. Click **Save**
5. Wait 1-2 minutes for initial deployment

Your map URL will be:
```
https://YOUR_USERNAME.github.io/greenland-monitor/greenland_monitor.html
```

---

## Step 5: Verify Automation is Running

1. Go to **Actions** tab in your repo
2. You should see the workflow "Monitor Greenland Airspace"
3. Click on it to see scheduled runs

The workflow runs every 30 minutes automatically. To test immediately:

1. Click **Actions** → **Monitor Greenland Airspace**
2. Click **Run workflow** (right side)
3. Select branch `main`
4. Click green **Run workflow** button
5. Watch the job execute (~30 seconds)

---

## Step 6: Check Your Data

After the first run completes:

```bash
# Pull the updated repo
git pull

# Check if data was collected
cat data/greenland_traffic.csv

# Open the map
open docs/greenland_monitor.html  # macOS
xdg-open docs/greenland_monitor.html  # Linux
start docs/greenland_monitor.html  # Windows
```

Or view online at your GitHub Pages URL.

---

## Monitoring Dashboard

### View Live Map
```
https://YOUR_USERNAME.github.io/greenland-monitor/greenland_monitor.html
```

### View Raw Data
```
https://github.com/YOUR_USERNAME/greenland-monitor/blob/main/data/greenland_traffic.csv
```

### View Action Logs
```
https://github.com/YOUR_USERNAME/greenland-monitor/actions
```

---

## Optional: Add OpenSky Credentials

Anonymous OpenSky access is limited to ~400 requests/day. For more:

1. Create free account at https://opensky-network.org/
2. Go to repo **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add two secrets:
   - Name: `OPENSKY_USERNAME` / Value: your username
   - Name: `OPENSKY_PASSWORD` / Value: your password

5. Update the workflow file to use them:

```yaml
# In .github/workflows/monitor.yml, change the run step to:
      - name: Run monitor
        env:
          OPENSKY_USER: ${{ secrets.OPENSKY_USERNAME }}
          OPENSKY_PASS: ${{ secrets.OPENSKY_PASSWORD }}
        run: python greenland_monitor.py
```

6. Update `greenland_monitor.py` to read credentials:

```python
# In main() function, change:
def main():
    username = os.environ.get('OPENSKY_USER')
    password = os.environ.get('OPENSKY_PASS')
    
    states = fetch_greenland_traffic(username=username, password=password)
    # ... rest of function
```

---

## Troubleshooting

### Workflow not running?

1. Check **Actions** tab — is it enabled?
2. Go to **Settings** → **Actions** → **General** → Ensure "Allow all actions" is selected
3. Check workflow file syntax at `.github/workflows/monitor.yml`

### No data being saved?

1. Verify write permissions (Step 3)
2. Check workflow logs in **Actions** tab for errors
3. OpenSky might be rate-limiting — wait an hour

### Map not showing?

1. Verify GitHub Pages is enabled (Step 4)
2. Check that `docs/greenland_monitor.html` exists
3. Wait 2-3 minutes for Pages to deploy after changes

### "Permission denied" on push?

```bash
# Re-authenticate
gh auth login

# Or use personal access token:
# Settings → Developer settings → Personal access tokens → Generate new token
# Select 'repo' scope
# Use token as password when pushing
```

### Want to pause monitoring?

1. Go to **Actions** → **Monitor Greenland Airspace**
2. Click **...** menu (top right)
3. Select **Disable workflow**

To resume, select **Enable workflow**.

---

## Running Analysis

After collecting a few days of data:

```bash
# Clone latest data
git pull

# Run pattern analysis
python analyze.py
```

This shows:
- Repeat visitors (same aircraft multiple times)
- Traffic near mining projects
- Private jets at unusual airports

---

## Customization

### Change polling frequency

Edit `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    # Every 15 minutes (more aggressive)
    - cron: '*/15 * * * *'
    
    # Every hour (conserve API calls)
    - cron: '0 * * * *'
    
    # Only during exploration season (May-Sept), every 30 min
    - cron: '*/30 * * 5-9 *'
```

### Add more airports

Edit `GREENLAND_AIRPORTS` dict in `greenland_monitor.py`:

```python
'BGXX': {'name': 'New Airport', 'iata': 'XXX', 'lat': 65.0, 'lon': -50.0,
         'runway_m': 800, 'type': 'regional', 'notes': 'Your notes'},
```

### Add more mining projects

Edit `MINING_PROJECTS` dict:

```python
'new_project': {'name': 'New Mine', 'lat': 61.0, 'lon': -45.0,
                'company': 'Mining Corp', 'commodity': 'Au, Cu',
                'status': 'Exploration'},
```

---

## Cost

**$0** — Everything uses free tiers:
- GitHub Free: unlimited public repos
- GitHub Actions Free: 2,000 minutes/month (this uses ~15 min/month)
- GitHub Pages Free: 1GB storage, 100GB bandwidth
- OpenSky Free: ~400 API calls/day

---

## Security Notes

- Repository is **public** — anyone can see your tracking
- If you want private, upgrade to GitHub Pro ($4/month)
- Never commit API keys to the repo — use Secrets
- The tracker only reads public ADS-B data, nothing sensitive

---

## Questions?

Open an issue at `https://github.com/YOUR_USERNAME/greenland-monitor/issues`
