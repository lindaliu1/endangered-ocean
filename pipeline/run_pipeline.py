from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def _run(cmd: list[str]) -> None:
	print(f"\n$ {' '.join(cmd)}")
	subprocess.run(cmd, check=True)

def main() -> int:
	parser = argparse.ArgumentParser(
		description=(
			"Run the NOAA scrape pipeline steps in order (list -> details). "
			"Optionally load results into Postgres (including Supabase) via backend/load_to_db.py."
		),
	)
	parser.add_argument(
			"--python",
			help="Path to python executable to use (defaults to current interpreter).",
			default=None,
	)
	parser.add_argument(
		"--skip-list",
		action="store_true",
		help="Skip scrape_noaa_list.py",
	)
	parser.add_argument(
		"--skip-details",
		action="store_true",
		help="Skip scrape_noaa_details.py",
	)
	parser.add_argument(
		"--load",
		action="store_true",
		help="After scraping, run backend/load_to_db.py (requires DATABASE_URL).",
	)
	args = parser.parse_args()

	# Ensure consistent working directory for relative paths inside the scripts.
	os.chdir(REPO_ROOT)

	py = args.python or sys.executable  # use the chosen interpreter / venv

	try:
		if not args.skip_list:
			_run([py, "-m", "pipeline.scrape_noaa_list"])
		else:
			print("Skipping scrape_noaa_list.py")

		if not args.skip_details:
			_run([py, "-m", "pipeline.scrape_noaa_details"])
		else:
			print("Skipping scrape_noaa_details.py")

		if args.load:
			if not os.environ.get("DATABASE_URL"):
				raise SystemExit(
					"DATABASE_URL is not set. Example:\n"
					"  export DATABASE_URL=\"postgresql://USER:PASSWORD@HOST:5432/DBNAME\""
				)
			_run([py, "-m", "backend.load_to_db"])

		print("\nDone.")
		return 0
	except subprocess.CalledProcessError as e:
		print(f"\nPipeline step failed with exit code {e.returncode}", file=sys.stderr)
		return e.returncode

if __name__ == "__main__":
	raise SystemExit(main())
