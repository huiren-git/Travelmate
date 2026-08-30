"""Create anonymized human-scoring materials from one completed benchmark run."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()
    rows = json.loads((args.artifact_dir / "results.json").read_text(encoding="utf-8"))
    public, key = [], []
    for number, row in enumerate(rows, 1):
        sample_id = f"S-{number:03d}"
        values = (row.get("final") or {}).get("values") or {}
        public.append({"sample_id": sample_id, "scenario": row["scenario_id"],
                       "input": row["input"], "itinerary": values.get("daily_itinerary") or values.get("draft_daily_itinerary"),
                       "summary": values.get("summary")})
        key.append({"sample_id": sample_id, "artifact": f"{row['scenario_id']}-{row['index']}.json"})
    (args.artifact_dir / "anonymous_samples.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.artifact_dir / "review_key_private.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.artifact_dir / "scoring_sheet.csv").write_text(
        "sample_id,reviewer_id,feasibility_1_5,personalization_1_5,completeness_1_5,clarity_1_5,safety_1_5,comments\n" +
        "\n".join(f"{x['sample_id']},,,,,," for x in public), encoding="utf-8")
    print(f"Created {len(public)} anonymous samples")


if __name__ == "__main__":
    main()
