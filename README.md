# 2026 FIFA World Cup ICS Feed

Apple Calendar subscription feed for all 2026 World Cup matches, auto-updated via GitHub Actions.

## Setup

### 1. Get an API key

Sign up at [dashboard.api-sports.io](https://dashboard.api-sports.io) (free tier: 100 req/day).

### 2. Create a GitHub repo

Push this folder to a new public GitHub repo.

### 3. Add the API key as a secret

Repo → Settings → Secrets and variables → Actions → New repository secret:
- Name: `API_FOOTBALL_KEY`
- Value: your API key

### 4. Enable GitHub Pages

Repo → Settings → Pages → Source: Deploy from a branch → Branch: `main` / folder: `/output`

### 5. Trigger the first run

Actions → "Refresh World Cup ICS" → Run workflow

The calendar will be available at:
```
https://<your-username>.github.io/<repo-name>/worldcup.ics
```

### 6. Subscribe on iPhone

Calendar → Add Calendar → Add Subscription Calendar → paste the URL above.
Set refresh: Every Hour.

## Local development

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env with your API key
python generate_ics.py
```

Output: `output/worldcup.ics`
