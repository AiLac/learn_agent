"""Feed the checked-in JSON snapshot to the Java lesson without third-party packages."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "hk-study-rooms"
SNAPSHOTS = {"starter": DATA / "library-study-rooms.json",
             "expanded": DATA / "search-v2" / "places.json"}


MIXED = HERE.parents[1] / "data" / "hk-poi" / "mixed-v1"
CATEGORIES = ("study_room", "park", "sports", "pool", "beach", "museum", "market")


def load_mixed(category):
    manifest = json.loads((MIXED / "manifest.json").read_text(encoding="utf-8"))
    base = manifest["base"]
    if category in (None, base["category"]):
        base_places = json.loads((MIXED / base["path"]).read_text(encoding="utf-8"))
        base_facts = json.loads((MIXED / base["evidence_path"]).read_text(encoding="utf-8"))
        by_place = {}
        for fact in base_facts["documents"]:
            by_place.setdefault(fact["place_id"], []).append(fact["text"])
        for place in base_places["records"]:
            yield place, [base["label"], place["name_tc"], place["name_en"], *by_place.get(place["id"], [])]
    for source in manifest["sources"]:
        if category is not None and category != source["id"]:
            continue
        shard = json.loads((MIXED / source["shard"]).read_text(encoding="utf-8"))
        for place in shard["records"]:
            extra = [source["label"], place["name_tc"], place["name_en"]]
            extra.extend(fact["text"] for fact in place["evidence"])
            yield place, extra


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--dataset", choices=(*SNAPSHOTS, "mixed"), default="starter",
                        help="mixed also searches aliases and evidence text")
    parser.add_argument("--category", choices=CATEGORIES, help="filter the mixed snapshot before searching")
    parser.add_argument("--limit", type=int, default=2, choices=range(1, 37), metavar="1..36")
    parser.add_argument("--simulate-timeout", action="store_true")
    args = parser.parse_args()
    if not args.query.strip():
        parser.error("query must be nonblank")

    if args.category and args.dataset != "mixed":
        parser.error("--category requires --dataset mixed")
    if args.dataset == "mixed":
        records = load_mixed(args.category)
    else:
        rows = json.loads(SNAPSHOTS[args.dataset].read_text(encoding="utf-8-sig"))["records"]
        records = ((item, []) for item in rows)
    lines = []
    ids = set()
    for item, extra in records:
        fields = [item[key] for key in ("id", "name", "district", "address")]
        if not all(isinstance(value, str) and value for value in fields):
            raise ValueError("missing room field")
        if any(any(char in value for char in "\r\n\t") for value in fields):
            raise ValueError("unsupported delimiter in room field")
        if item["id"] in ids:
            raise ValueError("duplicate room ID: " + item["id"])
        ids.add(item["id"])
        if extra:
            fields.append(" ".join(" ".join(value.split()) for value in extra))
        lines.append("\t".join(fields))
    command = ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",
               str(HERE / "RoomSearch.java"), args.query,
               str(args.limit), "timeout" if args.simulate_timeout else "normal"]
    try:
        process = subprocess.run(command, input=("\n".join(lines) + "\n").encode("utf-8"),
                                 stdout=subprocess.PIPE)
    except FileNotFoundError:
        parser.exit(1, "Java not found. Install JDK 17+ and put java on PATH.\n")
    # Decode Java output once so a Windows console can use its own text encoding.
    print(process.stdout.decode("utf-8"), end="")
    return process.returncode


if __name__ == "__main__":
    sys.exit(main())
