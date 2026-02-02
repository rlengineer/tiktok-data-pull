#!/usr/bin/env python3
"""
enriched_videos_to_csv.py

Supports:
1) "batch" enriched JSON:
   { run_started_at, ..., results: [ {video_id, url, username, scraped_at, yt_dlp:{...}}, ... ] }

2) "single video" JSON:
   { video_id, url, username, scraped_at, yt_dlp:{...} }

Outputs:
  - videos_enriched.csv  (one row per video)

Design choice:
- We do NOT fully flatten yt_dlp.formats (huge list).
- We extract "core" yt_dlp fields + a few helpful summaries.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_inputs(path: Path) -> List[Path]:
    if path.is_dir():
        return sorted([p for p in path.rglob("*.json") if p.is_file()])
    return [path]


def pick_best_format(formats: Any) -> Dict[str, Any]:
    """
    Pick a "best" format summary from yt_dlp.formats.
    Heuristic: choose the format with highest height, then highest tbr/filesize.
    """
    if not isinstance(formats, list) or not formats:
        return {}

    def score(fmt: Dict[str, Any]) -> Tuple[int, float, int]:
        h = fmt.get("height") or 0
        tbr = fmt.get("tbr") or 0.0
        fs = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        return (int(h), float(tbr), int(fs))

    best = None
    best_s = (-1, -1.0, -1)
    for f in formats:
        if not isinstance(f, dict):
            continue
        s = score(f)
        if s > best_s:
            best_s = s
            best = f

    if not isinstance(best, dict):
        return {}

    return {
        "best_format_id": best.get("format_id"),
        "best_ext": best.get("ext"),
        "best_vcodec": best.get("vcodec"),
        "best_acodec": best.get("acodec"),
        "best_width": best.get("width"),
        "best_height": best.get("height"),
        "best_tbr": best.get("tbr"),
        "best_filesize": best.get("filesize") or best.get("filesize_approx"),
    }


def first_thumbnail(thumbnails: Any) -> Dict[str, Any]:
    """
    Extract a couple useful thumbnail URLs without exploding the list.
    """
    if not isinstance(thumbnails, list) or not thumbnails:
        return {}
    # Prefer "cover" or "originCover" if present, else first
    preferred = {t.get("id"): t for t in thumbnails if isinstance(t, dict)}
    cover = preferred.get("cover") or preferred.get("originCover") or preferred.get("dynamicCover")
    if isinstance(cover, dict):
        return {"thumb_id": cover.get("id"), "thumb_url": cover.get("url")}
    t0 = thumbnails[0] if isinstance(thumbnails[0], dict) else None
    return {"thumb_id": t0.get("id"), "thumb_url": t0.get("url")} if isinstance(t0, dict) else {}


def normalize_record(item: Dict[str, Any], run_meta: Dict[str, Any]) -> Dict[str, Any]:
    yt = item.get("yt_dlp") if isinstance(item.get("yt_dlp"), dict) else {}

    formats_summary = pick_best_format(yt.get("formats"))
    thumb_summary = first_thumbnail(yt.get("thumbnails"))

    artists = yt.get("artists")
    artists_str = ",".join(artists) if isinstance(artists, list) else None

    return {
        **run_meta,
        "video_id": item.get("video_id") or yt.get("id"),
        "url": item.get("url") or yt.get("webpage_url") or yt.get("original_url"),
        "username": item.get("username") or yt.get("uploader"),
        "scraped_at": item.get("scraped_at"),

        # Core yt-dlp fields
        "yt_id": yt.get("id"),
        "title": yt.get("title"),
        "description": yt.get("description"),
        "timestamp": yt.get("timestamp"),
        "duration": yt.get("duration"),
        "view_count": yt.get("view_count"),
        "like_count": yt.get("like_count"),
        "comment_count": yt.get("comment_count"),
        "repost_count": yt.get("repost_count"),
        "save_count": yt.get("save_count"),

        # Channel/uploader identifiers
        "channel": yt.get("channel"),
        "channel_id": yt.get("channel_id"),
        "uploader": yt.get("uploader"),
        "uploader_id": yt.get("uploader_id"),
        "uploader_url": yt.get("uploader_url"),
        "channel_url": yt.get("channel_url"),

        # Audio/music
        "track": yt.get("track"),
        "album": yt.get("album"),
        "artists": artists_str,

        # Quick summaries from big lists
        **formats_summary,
        **thumb_summary,

        # Useful URL fields
        "webpage_url": yt.get("webpage_url"),
        "original_url": yt.get("original_url"),
        "extractor": yt.get("extractor"),
        "extractor_key": yt.get("extractor_key"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON file OR folder of JSONs")
    ap.add_argument("--out", dest="out_csv", required=True, help="Output CSV path")
    args = ap.parse_args()

    in_path = Path(args.in_path).expanduser().resolve()
    out_csv = Path(args.out_csv).expanduser().resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    for fp in iter_inputs(in_path):
        data = read_json(fp)

        # Determine if it's batch or single
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            run_meta = {
                "run_started_at": data.get("run_started_at"),
                "source_input": data.get("source_input"),
                "video_count_requested": data.get("video_count_requested"),
                "video_count_succeeded": data.get("video_count_succeeded"),
                "video_count_failed": data.get("video_count_failed"),
                "attempted_comments": data.get("attempted_comments"),
                "skipped_existing": data.get("skipped_existing"),
            }
            for item in data["results"]:
                if isinstance(item, dict):
                    rows.append(normalize_record(item, run_meta))
        elif isinstance(data, dict):
            # single video json file
            run_meta = {"source_file": str(fp)}
            rows.append(normalize_record(data, run_meta))
        else:
            # not recognized
            continue

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} (rows={len(df):,}, cols={df.shape[1]:,})")


if __name__ == "__main__":
    main()
