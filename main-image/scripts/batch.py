#!/usr/bin/env python3
"""Track a local image batch. The host runs the image tool and verifies each output."""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def fingerprint(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def init_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY, payload TEXT NOT NULL, issue TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS shots (
            sku TEXT NOT NULL, id TEXT NOT NULL, position INTEGER NOT NULL,
            card TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
            file TEXT, digest TEXT, error TEXT,
            PRIMARY KEY (sku, id)
        );
    """)


def portable_path(path, root):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def image_refs(value, base, root):
    refs = value if isinstance(value, list) else str(value or "").split("|")
    return [ref if ref.startswith("https://") else portable_path((base / ref).resolve(), root)
            for item in refs if (ref := str(item).strip())]


def import_products(db, args):
    source = Path(args.input).resolve()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = json.load(stream) if source.suffix.lower() == ".json" else list(csv.DictReader(stream))
    if not isinstance(rows, list) or not rows:
        raise ValueError("The source must contain a non-empty list of products.")
    seen = set()
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        if not sku or sku in seen:
            raise ValueError(f"Missing or duplicate SKU: {sku!r}")
        seen.add(sku)
        row = {key: val for key, val in row.items() if key and val not in ("", None)}
        row["sku"] = sku
        row["images"] = image_refs(row.get("images"), source.parent, args.root)
        eligibility = str(row.get("eligible", "true")).strip().lower()
        missing = [ref for ref in row["images"] if not ref.startswith("https://") and not (args.root / ref).is_file()]
        if eligibility not in {"true", "yes", "1", "通过"}:
            issue = "skipped: source eligibility"
        elif not row["images"] or missing:
            issue = "missing images: " + (", ".join(missing) if missing else "no image references")
        else:
            issue = ""
        payload = dump(row)
        previous = db.execute("SELECT payload FROM products WHERE sku = ?", (sku,)).fetchone()
        if previous and previous["payload"] != payload:
            raise ValueError(f"Input changed for {sku}. Use a new batch database for a changed product row.")
        db.execute("""INSERT INTO products (sku, payload, issue) VALUES (?, ?, ?)
                      ON CONFLICT(sku) DO UPDATE SET issue = excluded.issue""", (sku, payload, issue))
    emit({"imported_skus": sorted(seen)})


def product(db, sku):
    item = db.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if item is None:
        raise ValueError(f"Unknown SKU: {sku}")
    return item


def approve(db, args):
    if bool(args.sku) == args.all:
        raise ValueError("List SKU IDs or use --all.")
    skus = args.sku or [row["sku"] for row in db.execute("SELECT sku FROM products WHERE issue = ''")]
    for sku in skus:
        item = product(db, sku)
        if item["issue"]:
            raise ValueError(f"{sku}: {item['issue']}")
        db.execute("UPDATE products SET approved = 1 WHERE sku = ?", (sku,))
    emit({"approved_skus": skus})


def set_plan(db, args):
    item = product(db, args.sku)
    if not item["approved"] or item["issue"]:
        raise ValueError(f"{args.sku} must be approved and have usable inputs.")
    cards = json.loads(Path(args.cards).read_text(encoding="utf-8-sig"))
    if not isinstance(cards, list) or not cards:
        raise ValueError("The plan must be a non-empty JSON array of cards.")
    existing = {row["id"]: row for row in db.execute("SELECT * FROM shots WHERE sku = ?", (args.sku,))}
    if any(row["status"] == "running" for row in existing.values()):
        raise ValueError("Resolve running shots before replacing a plan.")
    seen = set()
    for position, card in enumerate(cards, start=1):
        shot_id = card.get("id", "")
        if not isinstance(shot_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", shot_id) or shot_id in seen:
            raise ValueError(f"Missing, invalid or duplicate shot ID: {shot_id!r}")
        seen.add(shot_id)
        encoded = dump(card)
        before = existing.get(shot_id)
        if before and before["card"] == encoded:
            db.execute("UPDATE shots SET position = ? WHERE sku = ? AND id = ?", (position, args.sku, shot_id))
            continue
        db.execute("""INSERT OR REPLACE INTO shots (sku, id, position, card) VALUES (?, ?, ?, ?)""",
                   (args.sku, shot_id, position, encoded))
    for shot_id in existing.keys() - seen:
        db.execute("DELETE FROM shots WHERE sku = ? AND id = ?", (args.sku, shot_id))
    emit({"sku": args.sku, "shots": len(cards)})


def current_status(row, root):
    if row["status"] != "complete":
        return row["status"]
    try:
        return "complete" if fingerprint(root / row["file"]) == row["digest"] else "missing"
    except OSError:
        return "missing"


def pending(db, args):
    if args.sku:
        product(db, args.sku)
    statuses = {"failed", "missing"} if args.retry else {"ready", "failed", "missing"}
    query = """SELECT s.*, p.payload FROM shots s JOIN products p USING (sku)
               WHERE (? IS NULL OR s.sku = ?) AND p.approved = 1 AND p.issue = ''
               ORDER BY s.sku, s.position"""
    rows = []
    for row in db.execute(query, (args.sku, args.sku)):
        status = current_status(row, args.root)
        if status in statuses:
            product_data = json.loads(row["payload"])
            product_data["images"] = [ref if ref.startswith("https://") else str(args.root / ref)
                                      for ref in product_data["images"]]
            rows.append({"sku": row["sku"], "id": row["id"], "status": status,
                         "product": product_data, "card": json.loads(row["card"])})
    emit(rows)


def find_shot(db, args):
    row = db.execute("SELECT * FROM shots WHERE sku = ? AND id = ?", (args.sku, args.id)).fetchone()
    if row is None:
        raise ValueError(f"Unknown shot: {args.sku}/{args.id}")
    return row


def start(db, args):
    item = product(db, args.sku)
    row = find_shot(db, args)
    if item["issue"] or not item["approved"] or current_status(row, args.root) not in {"ready", "failed", "missing"}:
        raise ValueError("Only an approved, pending shot may be started.")
    db.execute("UPDATE shots SET status = 'running', file = NULL, digest = NULL, error = NULL WHERE sku = ? AND id = ?",
               (args.sku, args.id))


def record(db, args):
    row = find_shot(db, args)
    if current_status(row, args.root) == "complete":
        raise ValueError("This shot already has a verified result. Update the card or use a new batch to revise it.")
    if args.file:
        output = Path(args.file).resolve(strict=True)
        if not output.is_file() or not output.stat().st_size:
            raise ValueError("The verified result must be a non-empty file.")
        saved_path = portable_path(output, args.root)
        owner = db.execute("SELECT sku, id FROM shots WHERE file = ? AND NOT (sku = ? AND id = ?)",
                           (saved_path, args.sku, args.id)).fetchone()
        if owner:
            raise ValueError(f"Result path already belongs to {owner['sku']}/{owner['id']}.")
        fields = ("complete", saved_path, fingerprint(output), None)
    else:
        fields = ("failed", None, None, args.error)
    db.execute("UPDATE shots SET status = ?, file = ?, digest = ?, error = ? WHERE sku = ? AND id = ?",
               (*fields, args.sku, args.id))


def report(db, args):
    rows = []
    for item in db.execute("SELECT * FROM products ORDER BY sku"):
        name = json.loads(item["payload"]).get("name", "")
        shots = list(db.execute("SELECT * FROM shots WHERE sku = ? ORDER BY position", (item["sku"],)))
        if not shots:
            status = "blocked" if item["issue"] else "awaiting_plan" if item["approved"] else "awaiting_approval"
            rows.append({"sku": item["sku"], "name": name, "id": "", "status": status,
                         "file": "", "error": item["issue"]})
            continue
        for shot in shots:
            status = current_status(shot, args.root)
            rows.append({"sku": item["sku"], "name": name, "id": shot["id"], "status": status,
                         "file": shot["file"] or "", "error": shot["error"] or item["issue"]})
    if args.csv:
        destination = Path(args.csv).resolve()
        if destination.exists():
            raise ValueError("Choose a new report filename to preserve existing files.")
        with destination.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["sku", "name", "id", "status", "file", "error"])
            writer.writeheader()
            for row in rows:
                writer.writerow({key: "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
                                 for key, value in row.items()})
    emit(rows)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("import").add_argument("input")
    approval = actions.add_parser("approve")
    approval.add_argument("sku", nargs="*")
    approval.add_argument("--all", action="store_true")
    plan = actions.add_parser("plan")
    plan.add_argument("sku")
    plan.add_argument("cards")
    queue = actions.add_parser("pending")
    queue.add_argument("--sku")
    queue.add_argument("--retry", action="store_true")
    for name in ("start", "record"):
        shot = actions.add_parser(name)
        shot.add_argument("sku")
        shot.add_argument("id")
        if name == "record":
            outcome = shot.add_mutually_exclusive_group(required=True)
            outcome.add_argument("--file")
            outcome.add_argument("--error")
    actions.add_parser("report").add_argument("--csv")
    return parser.parse_args()


def main():
    args = parse_args()
    path = Path(args.database).resolve()
    args.root = path.parent
    if args.action != "import" and not path.is_file():
        raise ValueError("Create the task database with import first.")
    handlers = {"import": import_products, "approve": approve, "plan": set_plan,
                "pending": pending, "start": start, "record": record, "report": report}
    with closing(sqlite3.connect(path, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        init_schema(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            handlers[args.action](db, args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, AttributeError, sqlite3.Error) as error:
        print(f"Batch error: {error}", file=sys.stderr)
        raise SystemExit(1)
