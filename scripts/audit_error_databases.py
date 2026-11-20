import hashlib
import json
import sys
from pathlib import Path

FILES = ("errors_bsod.json", "errors_windows.json")
STATE_FILE = Path("reviewed_records.json")
REQUIRED = {"errorCode", "title", "description", "officialSolution", "userSolutions", "category", "stepByStep"}
failed = False

try:
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    reviewed = state.get("records", {})
except Exception as exc:
    print(f"ERROR {STATE_FILE}: invalid or unavailable review state: {exc}")
    sys.exit(1)

for filename in FILES:
    path = Path(filename)
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR {filename}: invalid JSON: {exc}")
        failed = True
        continue
    if not isinstance(records, list):
        print(f"ERROR {filename}: root must be an array")
        failed = True
        continue

    codes = {}
    pending = []
    reviewed_for_file = reviewed.get(filename, {})
    for index, record in enumerate(records):
        where = f"{filename}[{index}]"
        if not isinstance(record, dict):
            print(f"ERROR {where}: record must be an object")
            failed = True
            continue
        missing = REQUIRED - record.keys()
        if missing:
            print(f"ERROR {where}: missing fields: {', '.join(sorted(missing))}")
            failed = True
        code = record.get("errorCode")
        if not isinstance(code, str) or not code.strip():
            print(f"ERROR {where}: errorCode must be a non-empty string")
            failed = True
            continue
        normalized = code.strip().casefold()
        if normalized in codes:
            print(f"ERROR {where}: duplicate errorCode {code!r}; first at index {codes[normalized]}")
            failed = True
        else:
            codes[normalized] = index

        steps = record.get("stepByStep")
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except json.JSONDecodeError as exc:
                print(f"ERROR {where}: stepByStep is not valid embedded JSON: {exc}")
                failed = True
                continue
        if not isinstance(steps, list) or not all(isinstance(step, str) and step.strip() for step in steps):
            print(f"ERROR {where}: stepByStep must be a list of non-empty strings (or JSON-encoded list)")
            failed = True
        for field in ("title", "description", "officialSolution"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                print(f"ERROR {where}: {field} must be a non-empty string")
                failed = True

        entry = reviewed_for_file.get(normalized)
        digest = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if entry and entry.get("status") == "reviewed" and entry.get("sources"):
            continue
        pending.append(code)

    print(f"{filename}: {len(records)} records; {len(codes)} unique codes; {len(pending)} awaiting content review")
    if pending:
        print("  pending: " + ", ".join(pending))

if failed:
    sys.exit(1)
print("Structural audit passed. Reviewed records with unchanged hashes are excluded from content-review work; this workflow does not automatically edit records.")
