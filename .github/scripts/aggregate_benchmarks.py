##########################
### AI-generated file. ###
##########################

"""Aggregate and merge benchmark JSON files.

The workflow runs the same benchmark suite on multiple independent runners.
This script reads every JSON file produced by those attempts, normalizes the
contained benchmark values, and writes a compact mapping JSON where each value is
the median across attempts. It can also merge independent hyperfine JSON files
from one runner into a single hyperfine-style JSON file.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from compare_benchmarks import Benchmark, extract_benchmarks


def collect_benchmarks(paths: list[Path]) -> dict[str, list[Benchmark]]:
    """Collect benchmarks from multiple JSON files.

    Args:
        paths (list[Path]): Paths to hyperfine, pytest-benchmark, or compact
            mapping JSON files.

    Returns:
        dict[str, list[Benchmark]]: Benchmarks grouped by benchmark name.
    """

    collected: dict[str, list[Benchmark]] = {}
    for path in paths:
        for name, benchmark in extract_benchmarks(path).items():
            collected.setdefault(name, []).append(benchmark)
    return collected


def aggregate(collected: dict[str, list[Benchmark]]) -> dict[str, dict[str, object]]:
    """Aggregate grouped benchmarks using the median value.

    Args:
        collected (dict[str, list[Benchmark]]): Benchmarks grouped by benchmark
            name.

    Returns:
        dict[str, dict[str, object]]: Compact mapping JSON data. Each benchmark
        contains ``value``, ``unit``, ``metric``, ``attempts``, and
        ``attempt_values``.
    """

    aggregated: dict[str, dict[str, object]] = {}
    for name, benchmarks in sorted(collected.items()):
        values = [benchmark.value for benchmark in benchmarks]
        unit = next((benchmark.unit for benchmark in benchmarks if benchmark.unit), "")
        metric = next((benchmark.metric for benchmark in benchmarks if benchmark.metric), "value")
        aggregated[name] = {
            "value": statistics.median(values),
            "unit": unit,
            "metric": f"median-of-attempt-{metric}",
            "attempts": len(values),
            "attempt_values": values,
        }
    return aggregated


def merge_hyperfine_results(paths: list[Path]) -> dict[str, Any]:
    """Merge hyperfine result files.

    Args:
        paths (list[Path]): Hyperfine JSON files to merge.

    Returns:
        dict[str, Any]: Hyperfine-style JSON object containing all result rows.

    Raises:
        ValueError: If any file has no hyperfine ``results`` list.
    """

    merged: dict[str, Any] = {"results": []}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        results = data.get("results", []) if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise ValueError(f"{path} has no hyperfine results list")
        merged["results"].extend(results)
    return merged


def main_from_paths(input_dir: Path, output: Path) -> int:
    """Aggregate all JSON files in a directory and write the result.

    Args:
        input_dir (Path): Directory containing benchmark JSON files.
        output (Path): Path where the aggregate JSON should be written.

    Returns:
        int: Always ``0`` on success.

    Raises:
        ValueError: If no JSON files are found in ``input_dir``.
    """

    paths = sorted(input_dir.rglob("*.json"))
    if not paths:
        raise ValueError(f"No benchmark JSON files found in {input_dir}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(aggregate(collect_benchmarks(paths)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def merge_from_paths(input_dir: Path, output: Path) -> int:
    """Merge all hyperfine JSON files in a directory and write the result.

    Args:
        input_dir (Path): Directory containing hyperfine JSON files.
        output (Path): Path where the merged JSON should be written.

    Returns:
        int: Always ``0`` on success.

    Raises:
        ValueError: If no JSON files are found in ``input_dir``.
    """

    paths = sorted(input_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"No hyperfine JSON files found in {input_dir}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(merge_hyperfine_results(paths), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def main() -> int:
    """Run the benchmark aggregation command line interface.

    Returns:
        int: Always ``0`` on success.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("aggregate", "merge-hyperfine"),
        default="aggregate",
        help="Operation to perform.",
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "merge-hyperfine":
        return merge_from_paths(input_dir=args.input_dir, output=args.output)
    return main_from_paths(input_dir=args.input_dir, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
