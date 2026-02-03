#!/usr/bin/env python3
"""
collect_user_metadata.py

Purpose:
- Step 1 of the process
- Collects TikTok metadata based on a given seed list of usernames 
- Collects metadata for user profile + last N videos - gives the video ID, which powers src/collect_video_metadata_from_ids.py
- Output is one json file per run
- Uses yt-dlp library
- No media downloaded; metadata only

Input:
- A txt file with one TikTokusername per line
- seeds/yyy-mm-dd/file_name.txt

Note:
- Increase sleep / jitter if repeatedly getting ERRORS, as repeated ERROR can indicate bot detection

"""

import argparse
import json
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None

def safe_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None

def extract_hashtags(text: Optional[str]) -> List[str]:
    if not text:
        return []
    tags = re.findall(r"#([A-Za-z0-9_]+)", text)
    # de-dup while preserving order
    seen = set()
    out = []
    for t in tags:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(tl)
    return out

@dataclass
class YtDlpResult:
    raw: Optional[Dict[str, Any]]
    error: Optional[str]
    returncode: int
    stderr: str = ""


def run_ytdlp_json(
    url: str,
    max_videos: int,
    user_agent: Optional[str] = None,
    timeout_sec: int = 120,
) -> YtDlpResult:
    """
    Run yt-dlp to fetch metadata JSON for a TikTok profile.
    -J: dump JSON
    --flat-playlist: avoids deep extraction / downloads; still gives usable metadata
    --playlist-end: last N items
    """
    cmd = [
        "yt-dlp",
        "-J",
        "--flat-playlist",
        "--playlist-end", str(max_videos),
        url,
    ]

    if user_agent:
        cmd.extend(["--user-agent", user_agent])

    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return YtDlpResult(raw=None, error="timeout", returncode=124)
    except FileNotFoundError:
        return YtDlpResult(raw=None, error="yt-dlp not found. Install with: pip install yt-dlp", returncode=127)
    except Exception as e:
        return YtDlpResult(raw=None, error=f"exception: {e}", returncode=1)

    stderr = (p.stderr or "").strip()
    if p.returncode != 0:
        short_err = stderr[-2000:] if len(stderr) > 2000 else stderr
        return YtDlpResult(raw=None, error=short_err or "yt-dlp failed", returncode=p.returncode, stderr=stderr)

    try:
        raw = json.loads(p.stdout)
        return YtDlpResult(raw=raw, error=None, returncode=0, stderr=stderr)
    except json.JSONDecodeError:
        return YtDlpResult(raw=None, error="failed to parse yt-dlp JSON output", returncode=2, stderr=stderr)


def normalize_profile(username: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    yt-dlp profile-level fields vary; return a stable profile object with best-effort mapping.
    """
    return {
        "username": username,
        "profile_url": f"https://www.tiktok.com/@{username}",
        "uploader": safe_str(raw.get("uploader")),
        "uploader_id": safe_str(raw.get("uploader_id")),
        "channel": safe_str(raw.get("channel")),
        "channel_id": safe_str(raw.get("channel_id")),
        "description": safe_str(raw.get("description")),
        "webpage_url": safe_str(raw.get("webpage_url") or raw.get("original_url")),
        # not always present:
        "extractor": safe_str(raw.get("extractor")),
        "extractor_key": safe_str(raw.get("extractor_key")),
    }


def normalize_video_entry(e: Dict[str, Any], fallback_username: str) -> Dict[str, Any]:
    """
    Normalize a single video entry into a stable schema.
    Note: With --flat-playlist, some stats may be missing.
    """
    title = safe_str(e.get("title"))
    description = safe_str(e.get("description"))
    caption = description or title  # best-effort
    uploader = safe_str(e.get("uploader") or e.get("uploader_id") or fallback_username)

    return {
        "video_id": safe_str(e.get("id")),
        "url": safe_str(e.get("url") or e.get("webpage_url")),
        "webpage_url": safe_str(e.get("webpage_url")),
        "title": title,
        "caption": caption,
        "hashtags": extract_hashtags(caption),
        "timestamp": safe_int(e.get("timestamp")),
        "upload_date": safe_str(e.get("upload_date")),
        "duration_sec": safe_int(e.get("duration")),
        "uploader": uploader,
        "uploader_id": safe_str(e.get("uploader_id")),
        # engagement metrics (may be None):
        "view_count": safe_int(e.get("view_count")),
        "like_count": safe_int(e.get("like_count")),
        "comment_count": safe_int(e.get("comment_count")),
        "repost_count": safe_int(e.get("repost_count")),
    }


def normalize_user_payload(username: str, raw: Dict[str, Any], max_videos: int) -> Dict[str, Any]:
    entries = raw.get("entries") or []
    videos = []
    for e in entries[:max_videos]:
        if isinstance(e, dict):
            videos.append(normalize_video_entry(e, username))

    return {
        "scraped_at": now_iso(),
        "source": "yt-dlp",
        "requested_max_videos": max_videos,
        "profile": normalize_profile(username, raw),
        "videos": videos,
    }


def read_seed_users(seed_path: Path) -> List[str]:
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    users: List[str] = []
    for line in seed_path.read_text(encoding="utf-8").splitlines():
        u = line.strip()
        if not u or u.startswith("#"):
            continue
        u = u.lstrip("@")
        # basic sanity
        if re.fullmatch(r"[A-Za-z0-9._]+", u) is None:
            # still allow it, but keep the raw
            users.append(u)
        else:
            users.append(u)
    # de-dup preserving order
    seen = set()
    out = []
    for u in users:
        if u.lower() not in seen:
            seen.add(u.lower())
            out.append(u)
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Collect TikTok metadata for seed usernames → JSON output.")
    ap.add_argument("--seed", type=str, default="../seeds/2026-02-01/tourism_boards_test.txt", help="Path to seed usernames file (one per line).")
    ap.add_argument("--out", type=str, default="outputs", help="Output directory.")
    ap.add_argument("--max-videos", type=int, default=20, help="Number of most recent videos to collect per user.")
    ap.add_argument("--sleep", type=float, default=2.0, help="Base sleep seconds between users.")
    ap.add_argument("--jitter", type=float, default=1.5, help="Random jitter seconds added to sleep.")
    ap.add_argument("--timeout", type=int, default=120, help="yt-dlp subprocess timeout in seconds per user.")
    ap.add_argument("--user-agent", type=str, default=None, help="Optional custom User-Agent string.")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first error.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    seed_path = Path(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        users = read_seed_users(seed_path)
    except Exception as e:
        print(f"ERROR reading seed file: {e}", file=sys.stderr)
        return 2

    run_started_at = now_iso()
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    total = len(users)
    if total == 0:
        print("No usernames found in seed file.")
        return 0

    print(f"Seed users: {total} | max_videos={args.max_videos}")
    print("Starting...\n")

    for i, username in enumerate(users, start=1):
        profile_url = f"https://www.tiktok.com/@{username}"
        print(f"[{i}/{total}] {username} … ", end="", flush=True)

        y = run_ytdlp_json(
            url=profile_url,
            max_videos=args.max_videos,
            user_agent=args.user_agent,
            timeout_sec=args.timeout,
        )

        if y.error or not y.raw:
            print("ERROR")
            errors.append({
                "username": username,
                "profile_url": profile_url,
                "scraped_at": now_iso(),
                "error": y.error or "unknown error",
                "returncode": y.returncode,
            })
            if args.fail_fast:
                break
        else:
            payload = normalize_user_payload(username, y.raw, args.max_videos)
            results.append(payload)
            print(f"OK ({len(payload['videos'])} videos)")

        # polite sleep
        delay = max(0.0, args.sleep + random.random() * args.jitter)
        time.sleep(delay)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"tiktok_seed_users_{ts}.json"

    final_payload = {
        "run_started_at": run_started_at,
        "run_finished_at": now_iso(),
        "seed_file": str(seed_path),
        "requested_max_videos": args.max_videos,
        "user_count_requested": total,
        "user_count_succeeded": len(results),
        "user_count_failed": len(errors),
        "results": results,
        "errors": errors,
    }

    out_file.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")

    print(f"\nDone. Wrote: {out_file}")
    if errors:
        print(f"Failures: {len(errors)} (common causes: rate limiting, bot detection, region blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
