import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from harness.zfam import BUILD_DIR, coverage  # noqa: E402


def pytest_terminal_summary(terminalreporter):
    if not coverage.hit:
        return
    rows = coverage.report()
    tr = terminalreporter
    tr.write_sep("=", "zFAM COBOL paragraph coverage")
    tr.write_line(f"{'Program':<10} {'Hit':>5} {'Total':>6} {'Cover':>7}")
    total_hit = total = 0
    for name, hit, count in rows:
        total_hit += hit
        total += count
        tr.write_line(f"{name:<10} {hit:>5} {count:>6} {100 * hit / count:>6.1f}%")
    tr.write_line(f"{'TOTAL':<10} {total_hit:>5} {total:>6} {100 * total_hit / total:>6.1f}%")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "coverage.json").write_text(json.dumps({
        "programs": {name: {"hit": hit, "total": count} for name, hit, count in rows},
        "paragraphs_hit": {k: sorted(v) for k, v in coverage.hit.items()},
        "total": {"hit": total_hit, "total": total},
    }, indent=2))
