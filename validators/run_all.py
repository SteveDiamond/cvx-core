#!/usr/bin/env python3
"""
Cross-language validation runner for CVX-Core.

This script runs validators for all supported languages (cvxpy, cvxjs, cvxrust)
and produces a unified report showing consistency across implementations.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ValidatorResult:
    """Result from running a single validator."""

    language: str
    success: bool
    passed: int
    total: int
    output: str
    error: Optional[str] = None


def run_python_validator(validators_dir: Path) -> ValidatorResult:
    """Run the Python/cvxpy validator."""
    script = validators_dir / "python" / "validate_cvxpy.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=validators_dir.parent,
            timeout=60,
        )

        # Parse output to extract pass/total
        output = result.stdout + result.stderr
        passed, total = 0, 0
        for line in output.split("\n"):
            if "Validation Results:" in line:
                # Format: "CVXPY Validation Results: X/Y atoms passed"
                parts = line.split(":")[-1].strip()
                if "/" in parts:
                    nums = parts.split()[0]  # "X/Y"
                    passed, total = map(int, nums.split("/"))

        return ValidatorResult(
            language="python/cvxpy",
            success=result.returncode == 0,
            passed=passed,
            total=total,
            output=output,
        )
    except subprocess.TimeoutExpired:
        return ValidatorResult(
            language="python/cvxpy",
            success=False,
            passed=0,
            total=0,
            output="",
            error="Timeout after 60 seconds",
        )
    except Exception as e:
        return ValidatorResult(
            language="python/cvxpy",
            success=False,
            passed=0,
            total=0,
            output="",
            error=str(e),
        )


def run_typescript_validator(validators_dir: Path) -> ValidatorResult:
    """Run the TypeScript/cvxjs validator."""
    script = validators_dir / "typescript" / "validate_cvxjs.ts"
    cvxjs_dir = validators_dir.parent.parent / "cvxjs"

    if not cvxjs_dir.exists():
        return ValidatorResult(
            language="typescript/cvxjs",
            success=False,
            passed=0,
            total=0,
            output="",
            error=f"cvxjs directory not found at {cvxjs_dir}",
        )

    try:
        # Run with tsx (TypeScript executor)
        result = subprocess.run(
            ["npx", "tsx", str(script)],
            capture_output=True,
            text=True,
            cwd=cvxjs_dir,
            timeout=60,
        )

        output = result.stdout + result.stderr
        passed, total = 0, 0
        for line in output.split("\n"):
            if "Validation Results:" in line:
                parts = line.split(":")[-1].strip()
                if "/" in parts:
                    nums = parts.split()[0]
                    passed, total = map(int, nums.split("/"))

        return ValidatorResult(
            language="typescript/cvxjs",
            success=result.returncode == 0,
            passed=passed,
            total=total,
            output=output,
        )
    except FileNotFoundError:
        return ValidatorResult(
            language="typescript/cvxjs",
            success=False,
            passed=0,
            total=0,
            output="",
            error="npx/tsx not found. Install with: npm install -g tsx",
        )
    except subprocess.TimeoutExpired:
        return ValidatorResult(
            language="typescript/cvxjs",
            success=False,
            passed=0,
            total=0,
            output="",
            error="Timeout after 60 seconds",
        )
    except Exception as e:
        return ValidatorResult(
            language="typescript/cvxjs",
            success=False,
            passed=0,
            total=0,
            output="",
            error=str(e),
        )


def run_rust_validator(validators_dir: Path) -> ValidatorResult:
    """Run the Rust/cvxrust validator."""
    rust_dir = validators_dir / "rust"

    if not rust_dir.exists():
        return ValidatorResult(
            language="rust/cvxrust",
            success=False,
            passed=0,
            total=0,
            output="",
            error=f"Rust validator directory not found at {rust_dir}",
        )

    try:
        # Build and run with cargo
        result = subprocess.run(
            ["cargo", "run", "--release"],
            capture_output=True,
            text=True,
            cwd=rust_dir,
            timeout=120,
        )

        output = result.stdout + result.stderr
        passed, total = 0, 0
        for line in output.split("\n"):
            if "Validation Results:" in line:
                parts = line.split(":")[-1].strip()
                if "/" in parts:
                    nums = parts.split()[0]
                    passed, total = map(int, nums.split("/"))

        return ValidatorResult(
            language="rust/cvxrust",
            success=result.returncode == 0,
            passed=passed,
            total=total,
            output=output,
        )
    except FileNotFoundError:
        return ValidatorResult(
            language="rust/cvxrust",
            success=False,
            passed=0,
            total=0,
            output="",
            error="cargo not found. Install Rust from rustup.rs",
        )
    except subprocess.TimeoutExpired:
        return ValidatorResult(
            language="rust/cvxrust",
            success=False,
            passed=0,
            total=0,
            output="",
            error="Timeout after 120 seconds",
        )
    except Exception as e:
        return ValidatorResult(
            language="rust/cvxrust",
            success=False,
            passed=0,
            total=0,
            output="",
            error=str(e),
        )


def print_summary(results: list[ValidatorResult]) -> None:
    """Print a summary of all validation results."""
    print("\n" + "=" * 70)
    print("CVX-CORE CROSS-LANGUAGE VALIDATION SUMMARY")
    print("=" * 70 + "\n")

    # Summary table
    print(f"{'Language':<25} {'Status':<10} {'Passed':<10} {'Total':<10}")
    print("-" * 55)

    all_passed = True
    for r in results:
        status = "PASS" if r.success else "FAIL"
        if r.error:
            status = "ERROR"
            all_passed = False
        elif not r.success:
            all_passed = False

        print(f"{r.language:<25} {status:<10} {r.passed:<10} {r.total:<10}")
        if r.error:
            print(f"  Error: {r.error}")

    print("-" * 55)

    # Overall status
    if all_passed:
        print("\n✓ All validators passed!")
    else:
        print("\n✗ Some validators failed. See details above.")

    print()


def print_detailed(results: list[ValidatorResult]) -> None:
    """Print detailed output from each validator."""
    for r in results:
        print("\n" + "=" * 70)
        print(f"DETAILED OUTPUT: {r.language}")
        print("=" * 70)
        if r.output:
            print(r.output)
        if r.error:
            print(f"ERROR: {r.error}")


def main():
    parser = argparse.ArgumentParser(
        description="Run CVX-Core validators across all languages"
    )
    parser.add_argument(
        "--languages",
        "-l",
        nargs="+",
        choices=["python", "typescript", "rust", "all"],
        default=["all"],
        help="Languages to validate (default: all)",
    )
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed output from each validator",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    validators_dir = Path(__file__).parent
    results = []

    languages = args.languages
    if "all" in languages:
        languages = ["python", "typescript", "rust"]

    print("Running CVX-Core validators...")
    print("-" * 40)

    if "python" in languages:
        print("Running Python/cvxpy validator...")
        results.append(run_python_validator(validators_dir))

    if "typescript" in languages:
        print("Running TypeScript/cvxjs validator...")
        results.append(run_typescript_validator(validators_dir))

    if "rust" in languages:
        print("Running Rust/cvxrust validator...")
        results.append(run_rust_validator(validators_dir))

    if args.json:
        output = [
            {
                "language": r.language,
                "success": r.success,
                "passed": r.passed,
                "total": r.total,
                "error": r.error,
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        print_summary(results)
        if args.detailed:
            print_detailed(results)

    # Exit with error if any validator failed
    if not all(r.success for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
