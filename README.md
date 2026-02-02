# tiktok-metadata-collector/
A sandbox for tiktok scraping

## Repo Folder Structure

```
tiktok-metadata-collector/
│
├── README.md
├── requirements.txt
│
├── src/
│   └── collect_user_metadata.py
│
├── seeds/
│   ├── 2026-02-01/
│   │   ├── travel_brands.txt
│   │   ├── tourism_boards.txt
│   │   └── content_creators.txt
│   │
│   ├── 2026-02-15/
│   │   ├── travel_creators_high_engagement.txt
│   │   └── airlines.txt
│   │
│   └── README.md
│
├── outputs/
│   ├── raw/
│   │   ├── 2026-02-01/
│   │   │   ├── tiktok_seed_users_20260201_214501.json
│   │   │   └── tiktok_seed_users_20260201_221833.json
│   │   │
│   │   └── 2026-02-15/
│   │       └── tiktok_seed_users_20260215_090212.json
│   │
│   └── README.md
│
├── notebooks/
│   └── explore_seed_outputs.ipynb
│
└── logs/
    └── runs.log
```

## How to Update Seed Files and Run the TikTok Metadata Collector

This guide documents the **repeatable workflow** for:
- updating seed files
- running the user metadata collector
- locating and verifying JSON outputs

Follow these steps **in order** each time you run a new snapshot.

---

### 0) Navigate to the repo root

```bash
cd ~/Documents/repos/tiktok-metadata-collector
```

1) Activate the virtual environment
source venv/bin/activate
Confirm dependencies are available:
yt-dlp --version
which yt-dlp
Expected:
yt-dlp prints a version
which yt-dlp points to .../venv/bin/yt-dlp
2) Create a new dated seed folder
Seeds are immutable snapshots. Use one folder per date.
Manual date
mkdir -p seeds/2026-02-01
Automatic (recommended)
mkdir -p "seeds/$(date +%F)"
3) Update or create seed files
Each file contains one TikTok username per line.
Example files
travel_brands.txt
tourism_boards.txt
creators_general.txt
Edit a file
open -e seeds/2026-02-01/travel_brands.txt
File format rules
one username per line
no @ required
comments allowed with #
Example:
# Travel brands – snapshot 2026-02-01
lonelyplanet
airbnb
expedia
Copy a previous snapshot (common workflow)
cp seeds/2026-01-15/travel_brands.txt seeds/2026-02-01/travel_brands.txt
open -e seeds/2026-02-01/travel_brands.txt
4) Create an output folder for this run
Mirror the seed date for traceability.
mkdir -p outputs/raw/2026-02-01
Or automatically:
mkdir -p "outputs/raw/$(date +%F)"
5) Run the collector for one seed file
From the repo root:
python scripts/collect_tiktok_seed_users.py \
  --seed seeds/2026-02-01/travel_brands.txt \
  --out outputs/raw/2026-02-01 \
  --max-videos 25 \
  --sleep 3 \
  --jitter 2
What this does:
reads the seed file
collects profile + last N videos
waits politely between users
writes one timestamped JSON file
6) Watch terminal output
Example:
[1/50] lonelyplanet … OK (25 videos)
[2/50] natgeo … OK (25 videos)
[3/50] visitdubai … ERROR
...
Done. Wrote: outputs/raw/2026-02-01/tiktok_seed_users_20260201_214501.json
Failures: 4
Errors are normal and expected.
7) Locate the JSON output
List newest first:
ls -lt outputs/raw/2026-02-01 | head
Get the most recent file:
ls -t outputs/raw/2026-02-01/*.json | head -n 1
8) Quick validation check
With jq installed:
jq '.user_count_succeeded, .user_count_failed' \
  outputs/raw/2026-02-01/tiktok_seed_users_*.json
Without jq:
head -n 40 outputs/raw/2026-02-01/tiktok_seed_users_*.json
9) Run remaining seed categories
python scripts/collect_tiktok_seed_users.py \
  --seed seeds/2026-02-01/tourism_boards.txt \
  --out outputs/raw/2026-02-01 \
  --max-videos 25
python scripts/collect_tiktok_seed_users.py \
  --seed seeds/2026-02-01/creators_general.txt \
  --out outputs/raw/2026-02-01 \
  --max-videos 25
Each run creates a new timestamped JSON.
10) If TikTok starts blocking requests
Slow the crawl:
--sleep 6 --jitter 4
Full example:
python scripts/collect_tiktok_seed_users.py \
  --seed seeds/2026-02-01/travel_brands.txt \
  --out outputs/raw/2026-02-01 \
  --max-videos 25 \
  --sleep 6 \
  --jitter 4
Optional User-Agent:
--user-agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15"
11) Deactivate when finished
deactivate
Optional: Run all seed files in one block
DATE="2026-02-01"
OUT="outputs/raw/$DATE"
mkdir -p "$OUT"

python scripts/collect_tiktok_seed_users.py --seed "seeds/$DATE/travel_brands.txt"    --out "$OUT" --max-videos 25 --sleep 3 --jitter 2
python scripts/collect_tiktok_seed_users.py --seed "seeds/$DATE/tourism_boards.txt"  --out "$OUT" --max-videos 25 --sleep 3 --jitter 2
python scripts/collect_tiktok_seed_users.py --seed "seeds/$DATE/creators_general.txt" --out "$OUT" --max-videos 25 --sleep 3 --jitter 2
Core principles
Seeds are immutable snapshots
One JSON output per run
Outputs always reference the seed file used
Errors are logged, not fatal
Slow > blocked
This workflow is intentionally boring — and that’s what makes it reliable.