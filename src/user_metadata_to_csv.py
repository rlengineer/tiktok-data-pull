#!/usr/bin/env python3
"""
seed_users_to_csv.py

Input:  seed-user run JSON shaped like:
  { run_started_at, ..., results: [ { scraped_at, source, profile:{...}, videos:[...]} , ... ] }

Output:
  - users.csv         (one row per user/profile result)
  - user_videos.csv   (one row per video, with user columns attached)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_get(d: Optional[Dict[str, Any]], key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input seed users JSON file")
    ap.add_argument("--out", dest="out_dir", required=True, help="Output directory for CSVs")
    args = ap.parse_args()

    in_path = Path(args.in_path).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = read_json(in_path)

    run_meta = {
        "run_started_at": data.get("run_started_at"),
        "run_finished_at": data.get("run_finished_at"),
        "seed_file": data.get("seed_file"),
        "requested_max_videos": data.get("requested_max_videos"),
        "user_count_requested": data.get("user_count_requested"),
        "user_count_succeeded": data.get("user_count_succeeded"),
        "user_count_failed": data.get("user_count_failed"),
    }

    users_rows: List[Dict[str, Any]] = []
    videos_rows: List[Dict[str, Any]] = []

    for r in data.get("results", []):
        # Some results may be failures with {username, error, returncode}
        profile = r.get("profile") if isinstance(r, dict) else None
        scraped_at = r.get("scraped_at")
        source = r.get("source")
        requested_max_videos = r.get("requested_max_videos")

        # Prefer profile.username, fallback to r.username
        username = safe_get(profile, "username", None) or r.get("username")

        user_row = {
            **run_meta,
            "scraped_at": scraped_at,
            "source": source,
            "requested_max_videos_user": requested_max_videos,
            "username": username,
            "profile_url": safe_get(profile, "profile_url"),
            "webpage_url": safe_get(profile, "webpage_url"),
            "extractor": safe_get(profile, "extractor"),
            "extractor_key": safe_get(profile, "extractor_key"),
            "uploader": safe_get(profile, "uploader"),
            "uploader_id": safe_get(profile, "uploader_id"),
            "channel": safe_get(profile, "channel"),
            "channel_id": safe_get(profile, "channel_id"),
            "description": safe_get(profile, "description"),
            "error": r.get("error"),
            "returncode": r.get("returncode"),
        }
        users_rows.append(user_row)

        # Videos nested under each successful user result
        for v in r.get("videos", []) if isinstance(r, dict) else []:
            if not isinstance(v, dict):
                continue
            hashtags = v.get("hashtags")
            videos_rows.append({
                **run_meta,
                "user_scraped_at": scraped_at,
                "user_source": source,
                "username": username,
                "profile_url": safe_get(profile, "profile_url"),
                "video_id": v.get("video_id"),
                "url": v.get("url"),
                "title": v.get("title"),
                "caption": v.get("caption"),
                "timestamp": v.get("timestamp"),
                "upload_date": v.get("upload_date"),
                "duration_sec": v.get("duration_sec"),
                "uploader": v.get("uploader"),
                "uploader_id": v.get("uploader_id"),
                "view_count": v.get("view_count"),
                "like_count": v.get("like_count"),
                "comment_count": v.get("comment_count"),
                "repost_count": v.get("repost_count"),
                "hashtags": ",".join(hashtags) if isinstance(hashtags, list) else None,
            })

    users_df = pd.DataFrame(users_rows)
    videos_df = pd.DataFrame(videos_rows)

    users_csv = out_dir / "users.csv"
    videos_csv = out_dir / "user_videos.csv"

    users_df.to_csv(users_csv, index=False)
    videos_df.to_csv(videos_csv, index=False)

    print(f"Wrote {users_csv} (rows={len(users_df):,}, cols={users_df.shape[1]:,})")
    print(f"Wrote {videos_csv} (rows={len(videos_df):,}, cols={videos_df.shape[1]:,})")


if __name__ == "__main__":
    main()
