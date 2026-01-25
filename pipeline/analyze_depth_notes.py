import json
from pathlib import Path

IN_PATH = Path("pipeline/out/noaa_details.json")
OUT_PATH = Path("pipeline/out/depth_notes.json")
REGEX_HITS_OUT_PATH = Path("pipeline/out/depth_regex_hits.json")

# json file with only depth notes for text analysis
def isolate_depth_notes():
    with IN_PATH.open("r", encoding="utf-8") as f:
        species_data = json.load(f)

    depth_notes_list = []
    for item in species_data:
        depth_notes = item.get("depth_notes", "")
        if depth_notes:
            depth_notes_list.append({
                "common_name": item.get("common_name"),
                "depth_notes": depth_notes
            })

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(depth_notes_list, f, indent=2)

if __name__ == "__main__":
    isolate_depth_notes()
    print(f"Wrote depth notes to {OUT_PATH}")