"""Feed the checked-in JSON snapshot to the Java lesson without third-party packages."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE.parents[1] / "data" / "hk-study-rooms" / "library-study-rooms.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=2, choices=range(1, 37), metavar="1..36")
    parser.add_argument("--simulate-timeout", action="store_true")
    args = parser.parse_args()
    if not args.query.strip():
        parser.error("query must be nonblank")

    records = json.loads(SNAPSHOT.read_text(encoding="utf-8-sig"))["records"]
    lines = []
    ids = set()
    for item in records:
        fields = [item[key] for key in ("id", "name", "district", "address")]
        if not all(isinstance(value, str) and value for value in fields):
            raise ValueError("missing room field")
        if any(any(char in value for char in "\r\n\t") for value in fields):
            raise ValueError("unsupported delimiter in room field")
        if item["id"] in ids:
            raise ValueError("duplicate room ID: " + item["id"])
        ids.add(item["id"])
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
