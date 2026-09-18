"""Create a Step-8-only ZIP and a reproducible test/checksum report."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from common import file_digest, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parent
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("ZIP exists; use a new filename")
    if root in output.parents:
        raise ValueError("Write ZIP outside the package directory")
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(root/"tests"), "-v"],
                           capture_output=True, text=True)
    write_json(root / "results/unit_test_report.json", {"return_code": tests.returncode,
                "stdout": tests.stdout, "stderr": tests.stderr})
    if tests.returncode:
        raise RuntimeError("Unit tests failed; no ZIP generated")
    files = [f for f in root.rglob("*") if f.is_file() and "__pycache__" not in f.parts
             and f.name != "SHA256SUMS.json" and f.suffix != ".pyc"]
    manifest = {str(f.relative_to(root)).replace("\\", "/"): file_digest(f) for f in sorted(files)}
    write_json(root / "SHA256SUMS.json", manifest)
    files.append(root / "SHA256SUMS.json")
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for f in sorted(files):
            archive.write(f, "SupplyGrid_Step8/" + str(f.relative_to(root)).replace("\\", "/"))
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity failure")
        assert all(n.startswith("SupplyGrid_Step8/") for n in archive.namelist())
        assert not any(n.endswith(".joblib") or n.endswith(".csv") for n in archive.namelist())
    print(output, "files:", len(files), "bytes:", output.stat().st_size)


if __name__ == "__main__":
    main()
