#!/usr/bin/env python3
import argparse
import glob
import os
import subprocess
import sys
from typing import Set, List


def run_cmd(cmd: List[str]) -> str:
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
    )
    if result.returncode != 0:
        return ""
    return result.stdout

def get_installed_packages() -> Set[str]:
    out = run_cmd(["dpkg-query", "-W", "-f=${Package}\n"])
    pkgs = {line.strip() for line in out.splitlines() if line.strip()}
    return pkgs

def get_available_packages_from_lists() -> Set[str]:
    pkg_files = glob.glob("/var/lib/apt/lists/*_Packages")
    if not pkg_files:
        return set()

    packages: Set[str] = set()
    for path in pkg_files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # Lines look like: "Package: foo"
                    if line.startswith("Package: "):
                        pkg = line.split(":", 1)[1].strip()
                        if pkg:
                            packages.add(pkg)
        except OSError:
            continue
    return packages

def get_available_packages_fallback() -> Set[str]:
    out = run_cmd(["apt-cache", "pkgnames"])
    return {line.strip() for line in out.splitlines() if line.strip()}

def get_available_packages() -> Set[str]:
    pkgs = get_available_packages_from_lists()
    if pkgs:
        return pkgs
    print("Warning: no *_Packages files found; falling back to 'apt-cache pkgnames' (slower)...", file=sys.stderr)
    return get_available_packages_fallback()

def get_package_info(pkg: str) -> tuple[str, str]:
    out = run_cmd(["dpkg-query", "-W", "-f=${Version}\n${Description}\n", pkg])
    if not out:
        return "unknown", ""
    lines = out.splitlines()
    version = lines[0].strip() if lines else "unknown"
    desc = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    return version, desc

def remove_packages(orphans: List[str], assume_yes: bool) -> int:
    if not orphans:
        return 0

    cmd = ["apt-get", "remove", "--purge"]
    if assume_yes:
        cmd.append("-y")
    cmd.extend(orphans)

    proc = subprocess.run(cmd)
    return proc.returncode

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find installed packages that are no longer in any configured APT repo and optionally remove them."
    )
    parser.add_argument("-n", action="store_true", dest="dry_run",
                        help="Dry-run (only list packages, do not remove anything)")
    parser.add_argument("-y", action="store_true", dest="assume_yes",
                        help="Non-interactive: remove all orphan packages without asking")
    args = parser.parse_args()

    # basic sanity checks
    for cmd in ("dpkg-query", "apt-get"):
        if not shutil.which(cmd := cmd):  # small trick, but still Python 3.8+ safe
            print(f"Error: {cmd} not found in PATH.", file=sys.stderr)
            return 1

    print("Collecting installed packages...")
    installed = get_installed_packages()

    print("Collecting packages from current APT repositories...")
    available = get_available_packages()

    print("Computing difference (installed - available)...")
    orphans = sorted(installed - available)

    if not orphans:
        print("No orphan packages found. Everything installed exists in a configured repo.")
        return 0

    print("\nThe following packages are installed but not present in any current APT repo:")
    for pkg in orphans:
        print(f"  {pkg}")
    print()

    if args.dry_run:
        print("Dry-run mode: no changes will be made.")
        return 0

    if args.assume_yes:
        print("Non-interactive mode: removing all orphan packages...")
        return remove_packages(orphans, assume_yes=True)

    for pkg in orphans:
        version, desc = get_package_info(pkg)
        print()
        print(f"Package: {pkg}")
        print(f"Version: {version}")
        if desc:
            print("Desc   :", desc.splitlines()[0])  # first line is usually enough
        ans = input("Remove this package? [y/N] ").strip().lower()
        if ans.startswith("y"):
            rc = remove_packages([pkg], assume_yes=False)
            if rc != 0:
                print(f"apt-get failed for {pkg} (exit code {rc}), continuing...", file=sys.stderr)
        else:
            print(f"Skipping {pkg}")

    return 0

if __name__ == "__main__":
    import shutil
    sys.exit(main())
