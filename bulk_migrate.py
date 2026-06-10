#!/usr/bin/env python3
"""
Bulk migration from CSV input.

Reads a CSV file (exported by inventory.py --export-csv) with source/target
mappings and runs migrations sequentially, tracking progress.

Usage:
    python bulk_migrate.py --input-csv inventory.csv
    python bulk_migrate.py --input-csv inventory.csv --dry-run
    python bulk_migrate.py --input-csv inventory.csv --skip-migrated
"""

import argparse
import csv
import json
import sys
import time
from migrate_function_app import (
    export_v1_metadata,
    transform_to_v2,
    deploy_v2_function_app,
    get_managed_environment_location,
    _discover_environment_id,
)


def load_csv(input_file):
    """Load migration plan from CSV."""
    rows = []
    with open(input_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def validate_csv(rows):
    """Validate CSV has required fields for migration."""
    required = ["source_app_name", "source_resource_group", "source_subscription_id"]
    target_required = ["target_subscription_id", "target_resource_group", "target_app_name"]
    errors = []

    for i, row in enumerate(rows, start=2):  # row 1 is header
        for field in required:
            if not row.get(field, "").strip():
                errors.append(f"Row {i}: missing {field}")

        # Target fields required for non-migrated rows
        status = row.get("migration_status", "").strip().lower()
        if status != "migrated":
            for field in target_required:
                if not row.get(field, "").strip():
                    errors.append(f"Row {i}: missing {field} (required for pending migration)")

    return errors


def print_progress(completed, total, current_app, status="in-progress"):
    """Print a progress line."""
    pct = (completed / total * 100) if total > 0 else 0
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    status_icon = {"in-progress": "⟳", "success": "✓", "failed": "✗", "skipped": "→"}.get(status, " ")
    print(f"\r  [{bar}] {pct:5.1f}% ({completed}/{total}) {status_icon} {current_app}", end="", flush=True)


def run_bulk_migration(rows, dry_run=False, skip_migrated=True):
    """Run migration for each row in the CSV."""
    total = len(rows)
    pending = [r for r in rows if r.get("migration_status", "").strip().lower() != "migrated" or not skip_migrated]
    skipped = total - len(pending)

    print("=" * 70)
    print("Bulk Migration — Azure Function App v1 → v2")
    print("=" * 70)
    print(f"\n  Total in CSV: {total}")
    print(f"  Already migrated (skipped): {skipped}")
    print(f"  To migrate: {len(pending)}")
    if dry_run:
        print(f"  Mode: DRY RUN (no deployments)")
    print()

    results = []
    completed = 0

    for row in pending:
        source_app = row["source_app_name"].strip()
        source_rg = row["source_resource_group"].strip()
        source_sub = row["source_subscription_id"].strip()
        target_sub = row["target_subscription_id"].strip()
        target_rg = row["target_resource_group"].strip()
        target_app = row["target_app_name"].strip()
        environment_id = row.get("target_environment_id", "").strip()

        print_progress(completed, len(pending), source_app, "in-progress")

        if dry_run:
            results.append({
                "source": source_app,
                "target": target_app,
                "status": "dry-run",
                "message": "Would migrate",
            })
            completed += 1
            print_progress(completed, len(pending), source_app, "skipped")
            print()
            continue

        try:
            # Auto-discover environment if not specified
            if not environment_id:
                environment_id = _discover_environment_id(target_sub, target_rg)
                if not environment_id:
                    raise ValueError(f"No managed environment found in {target_rg}")

            # Export
            v1_metadata = export_v1_metadata(source_sub, source_rg, source_app)

            # Get target location from environment
            target_location = get_managed_environment_location(target_sub, environment_id)

            # Transform
            v2_metadata = transform_to_v2(v1_metadata, target_app, target_location=target_location)

            # Deploy
            deploy_v2_function_app(target_sub, target_rg, target_app, v2_metadata, environment_id)

            results.append({
                "source": source_app,
                "target": target_app,
                "status": "success",
                "message": "Deployed successfully",
            })
            completed += 1
            print_progress(completed, len(pending), source_app, "success")
            print()

        except Exception as e:
            results.append({
                "source": source_app,
                "target": target_app,
                "status": "failed",
                "message": str(e),
            })
            completed += 1
            print_progress(completed, len(pending), source_app, "failed")
            print(f"\n    Error: {e}")

    # Summary
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    dry_runs = sum(1 for r in results if r["status"] == "dry-run")

    print()
    print("=" * 70)
    print("Bulk Migration Summary")
    print("=" * 70)
    pct = (successes / len(pending) * 100) if len(pending) > 0 else 0
    print(f"  Success: {successes} | Failed: {failures} | Dry-run: {dry_runs}")
    print(f"  Overall progress: {pct:.1f}%")

    if failures > 0:
        print(f"\n  Failed migrations:")
        for r in results:
            if r["status"] == "failed":
                print(f"    ✗ {r['source']} → {r['target']}: {r['message']}")

    # Write results to JSON
    results_file = "bulk_migration_results.json"
    with open(results_file, "w") as f:
        json.dump({"results": results, "summary": {"success": successes, "failed": failures, "total": len(pending)}}, f, indent=2)
    print(f"\n  Results saved to {results_file}")

    return 0 if failures == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Run bulk migration from a CSV plan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV columns (from inventory.py --export-csv):
  source_app_name, source_resource_group, source_subscription_id,
  source_location, migration_status,
  target_subscription_id, target_resource_group, target_app_name,
  target_environment_id, notes
""",
    )
    parser.add_argument("--input-csv", required=True, help="CSV file with migration plan")
    parser.add_argument("--dry-run", action="store_true", help="Validate plan without deploying")
    parser.add_argument("--skip-migrated", action="store_true", default=True,
                        help="Skip rows already marked as Migrated (default: true)")
    parser.add_argument("--no-skip-migrated", action="store_false", dest="skip_migrated",
                        help="Process all rows including already-migrated ones")

    args = parser.parse_args()

    print(f"\nLoading migration plan from {args.input_csv}...")
    rows = load_csv(args.input_csv)

    if not rows:
        print("✗ CSV is empty")
        sys.exit(1)

    errors = validate_csv(rows)
    if errors:
        print(f"\n✗ CSV validation failed ({len(errors)} errors):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        sys.exit(1)

    print(f"✓ Loaded {len(rows)} rows")
    exit_code = run_bulk_migration(rows, dry_run=args.dry_run, skip_migrated=args.skip_migrated)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
