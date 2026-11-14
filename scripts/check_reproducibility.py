import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from generator.config import DEFAULT_SEED, SCALES  # noqa: E402
from generator.export import STATIC_FILES  # noqa: E402

HASH_PREFIX_LENGTH = 16


def run_generator(seed, scale, output_dir):
    command = [sys.executable, str(ROOT / "generate.py"), "--seed", str(seed), "--scale", scale, "--output-dir", str(output_dir)]
    subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT)


def hash_files(output_dir):
    return {
        path.relative_to(output_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output_dir.rglob("*")) if path.is_file()
    }


def read_row_counts(output_dir):
    manifest = json.loads((output_dir / "data" / "manifest.json").read_text(encoding="utf-8"))
    return {entry["path"]: entry["rows"] for entry in manifest["files"]}, {entry["path"]: entry["sha256"] for entry in manifest["files"]}


def run_once(seed, scale):
    with tempfile.TemporaryDirectory() as folder:
        output_dir = Path(folder)
        run_generator(seed, scale, output_dir)
        rows, manifest_hashes = read_row_counts(output_dir)
        return {"hashes": hash_files(output_dir), "rows": rows, "manifest_hashes": manifest_hashes}


def short(digest):
    return digest[:HASH_PREFIX_LENGTH] if digest else "missing"


def compare_same_seed(first, second):
    rows = []
    for path in sorted(set(first["hashes"]) | set(second["hashes"])):
        same_hash = first["hashes"].get(path) == second["hashes"].get(path)
        same_rows = first["rows"].get(path) == second["rows"].get(path)
        rows.append((path, first["rows"].get(path, "n/a"), short(first["hashes"].get(path)), short(second["hashes"].get(path)), same_hash and same_rows))
    return rows


def compare_other_seed(first, other):
    rows = []
    for path in sorted(first["hashes"]):
        same = first["hashes"][path] == other["hashes"].get(path)
        expected_same = path in STATIC_FILES
        rows.append((path, short(first["hashes"][path]), short(other["hashes"].get(path)), "same" if expected_same else "different", same == expected_same))
    return rows


def manifest_is_accurate(run):
    listed = run["manifest_hashes"]
    return all(run["hashes"].get(path) == digest for path, digest in listed.items())


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def status(flag):
    return "pass" if flag else "FAIL"


def build_report(seed, other_seed, scale, same_rows, other_rows, manifest_ok, passed):
    sections = [
        "# Reproducibility report",
        f"Scale: {scale}. Seed: {seed}. Comparison seed: {other_seed}. SHA-256 values are shown as the first {HASH_PREFIX_LENGTH} hex characters.",
        f"Overall: {'PASS' if passed else 'FAIL'}",
        "## Same seed, two runs\n\n" + markdown_table(["File", "Rows", "Run 1", "Run 2", "Match"], [(*row[:4], status(row[4])) for row in same_rows]),
        "## Different seed\n\n" + markdown_table(["File", f"Seed {seed}", f"Seed {other_seed}", "Expected", "Result"], [(*row[:4], status(row[4])) for row in other_rows]),
        f"## Manifest\n\nEvery checksum listed in data/manifest.json matches the file on disk: {status(manifest_ok)}.",
    ]
    return "\n\n".join(sections) + "\n"


def parse_args():
    parser = argparse.ArgumentParser(description="Check that the generator output is reproducible.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", choices=sorted(SCALES), default="starter")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "reproducibility_report.md")
    return parser.parse_args()


def main():
    args = parse_args()
    other_seed = args.seed + 1
    first, second = run_once(args.seed, args.scale), run_once(args.seed, args.scale)
    other = run_once(other_seed, args.scale)
    same_rows = compare_same_seed(first, second)
    other_rows = compare_other_seed(first, other)
    manifest_ok = manifest_is_accurate(first) and manifest_is_accurate(second)
    passed = all(row[4] for row in same_rows) and all(row[4] for row in other_rows) and manifest_ok
    args.report.write_text(build_report(args.seed, other_seed, args.scale, same_rows, other_rows, manifest_ok, passed), encoding="utf-8", newline="\n")
    print(f"same seed, {len(same_rows)} files: " + ("all identical" if all(row[4] for row in same_rows) else "DIFFERENCES FOUND"))
    print("different seed: " + ("checksums changed as expected" if all(row[4] for row in other_rows) else "UNEXPECTED RESULT"))
    print(f"manifest checksums match files: {manifest_ok}")
    print("result: " + ("PASS" if passed else "FAIL"))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
