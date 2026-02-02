# tiktok-metadata-collector/
A sandbox for tiktok scraping

## Repo Folder Structure
tiktok-metadata-collector/
│
├── README.md
├── .gitignore
├── requirements.txt
│
├── scripts/
│   └── collect_tiktok_seed_users.py
│
├── seeds/
│   ├── 2026-02-01/
│   │   ├── travel_brands.txt
│   │   ├── tourism_boards.txt
│   │   └── creators_general.txt
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
