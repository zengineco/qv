#!/usr/bin/env python3
# ============================================================
# QV (QikVote) v0.4.0 - pollcreator.py
# Seeds ballots into QV from curated question sets.
# F-Keys | www.f-keys.com
# ============================================================
#
# WORKFLOW STACK:
# 1. Load creator key from --key or the QV_CREATOR_KEY environment variable
# 2. Read one or more seed files from seeds/ (JSON: list of ballot objects)
# 3. Filter by --channel / --limit, then for each ballot:
#    a. POST to qv-publish with notify=false, telegram=false (silent seeding)
#    b. On 409 duplicate/similar, skip and report the live ballot it collides with
# 4. Print a per-ballot result table and a summary
#
# Seeding NEVER notifies. Creating 40 ballots with notifications on would fire
# 40 push notifications at every subscriber. Use --notify only for a single
# deliberate publish.
#
# ASSET MANIFEST:
# - https://ihclxurachkewtgnrldc.supabase.co/functions/v1/qv-publish
# - seeds/*.json
# - stdlib only (urllib, json, argparse) - no pip install required
#
# BOOT ORDER: parse args -> resolve key -> load seeds -> publish loop -> summary
# ============================================================

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://ihclxurachkewtgnrldc.supabase.co/functions/v1/qv-publish"
SEED_DIR = Path(__file__).parent / "seeds"


def post(payload, timeout=30):
    """One call to qv-publish. Returns (http_status, parsed_body)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"ok": False, "error": body[:200]}
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}


def load_seeds(names):
    """Load seed files by name (or all of them). Returns a list of ballots."""
    if not SEED_DIR.is_dir():
        sys.exit("No seeds/ directory next to pollcreator.py")
    if names:
        files = []
        for n in names:
            p = SEED_DIR / (n if n.endswith(".json") else n + ".json")
            if not p.is_file():
                sys.exit("No such seed file: %s" % p)
            files.append(p)
    else:
        files = sorted(SEED_DIR.glob("*.json"))
    if not files:
        sys.exit("No seed files found in %s" % SEED_DIR)

    ballots = []
    for f in files:
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit("%s is not valid JSON: %s" % (f.name, e))
        if not isinstance(items, list):
            sys.exit("%s must contain a JSON list" % f.name)
        for it in items:
            it["_source"] = f.stem
            ballots.append(it)
    return ballots


def validate(b):
    """Reject a malformed ballot before it costs a network round trip."""
    q = (b.get("question") or "").strip()
    if not (3 <= len(q) <= 140):
        return "question must be 3-140 chars"
    if len((b.get("detail") or "")) > 500:
        return "detail over 500 chars"
    for k in ("label_a", "label_b"):
        if len((b.get(k) or "")) > 25:
            return "%s over 25 chars" % k
    ch = b.get("channel") or "general"
    if not ch.replace("-", "").isalnum() or not ch.islower() or not (2 <= len(ch) <= 32):
        return "channel must be lowercase a-z0-9- (2-32)"
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Seed QV ballots from curated question sets.",
        epilog="Seeding is silent by default. Pass --notify only for a single deliberate publish.",
    )
    ap.add_argument("seeds", nargs="*", help="seed file names (default: every file in seeds/)")
    ap.add_argument("--key", help="creator key (default: $QV_CREATOR_KEY)")
    ap.add_argument("--channel", help="only publish ballots in this channel")
    ap.add_argument("--limit", type=int, help="publish at most N ballots")
    ap.add_argument("--minutes", type=int, default=0, help="auto-close after N minutes (0 = open-ended)")
    ap.add_argument("--dry-run", action="store_true", help="show what would publish, send nothing")
    ap.add_argument("--force", action="store_true", help="publish even when QV flags a duplicate")
    ap.add_argument("--notify", action="store_true", help="DO send push notifications (off by default)")
    ap.add_argument("--telegram", action="store_true", help="DO post to the Telegram channel (off by default)")
    ap.add_argument("--delay", type=float, default=0.4, help="seconds between calls (default 0.4)")
    args = ap.parse_args()

    key = args.key or os.environ.get("QV_CREATOR_KEY", "")
    if not key and not args.dry_run:
        sys.exit(
            "No creator key. Set it for this shell:\n"
            "  Windows PowerShell:  $env:QV_CREATOR_KEY = 'qvc_...'\n"
            "  bash:                export QV_CREATOR_KEY=qvc_...\n"
            "or pass --key qvc_...   (never commit the key)"
        )

    ballots = load_seeds(args.seeds)
    if args.channel:
        ballots = [b for b in ballots if (b.get("channel") or "general") == args.channel]
    if args.limit:
        ballots = ballots[: args.limit]
    if not ballots:
        sys.exit("Nothing to publish after filtering.")

    print("QV pollcreator - %d ballot(s)%s" % (len(ballots), "  [DRY RUN]" if args.dry_run else ""))
    if not args.dry_run:
        print("push: %s   telegram: %s" % ("ON" if args.notify else "silent",
                                           "ON" if args.telegram else "silent"))
    print("-" * 68)

    created = skipped = failed = 0
    for i, b in enumerate(ballots, 1):
        q = (b.get("question") or "").strip()
        ch = b.get("channel") or "general"
        bad = validate(b)
        if bad:
            print("[%2d] SKIP  %-50s  (%s)" % (i, q[:50], bad))
            failed += 1
            continue

        if args.dry_run:
            print("[%2d] would publish  #%-12s %s" % (i, ch, q[:60]))
            created += 1
            continue

        payload = {
            "key": key,
            "action": "create",
            "question": q,
            "detail": b.get("detail", ""),
            "label_a": b.get("label_a", "YES"),
            "label_b": b.get("label_b", "NO"),
            "channel": ch,
            "minutes": args.minutes,
            "notify": bool(args.notify),
            "telegram": bool(args.telegram),
            "confirm": bool(args.force),
        }
        status, out = post(payload)

        if out.get("ok"):
            created += 1
            print("[%2d] OK    %-8s #%-10s %s" % (i, out.get("id", "?"), ch, q[:45]))
        elif status == 409:
            skipped += 1
            m = (out.get("matches") or [{}])[0]
            print("[%2d] DUP   %-50s -> already live as %s (%d votes)"
                  % (i, q[:50], m.get("id", "?"), m.get("votes", 0)))
        elif status == 401:
            sys.exit("Creator key rejected. Check QV_CREATOR_KEY.")
        else:
            failed += 1
            print("[%2d] FAIL  %-50s  (%s %s)" % (i, q[:50], status, out.get("error", "?")))

        time.sleep(args.delay)

    print("-" * 68)
    print("created %d   duplicate %d   failed %d" % (created, skipped, failed))
    if created and not args.dry_run:
        print("Live at https://qv.f-keys.com")


if __name__ == "__main__":
    main()
