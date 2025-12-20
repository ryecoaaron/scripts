#!/usr/bin/env python3
"""
Backup/restore a subtree from OpenMediaVault's XML database.
- Backup by service key:      borgbackup  => /config/services/borgbackup
- Backup by full path/xpath:  /config/services/borgbackup

Restore semantics:
- If target node exists: replace it
- If target node missing: create path and add it
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Tuple


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def require_root() -> None:
    if os.geteuid() != 0:
        raise SystemExit("This tool must be run as root (euid 0). Try: sudo ...")

def normalize_xpath(x: str) -> str:
    """
    Accepts:
      - "borgbackup" -> "/config/services/borgbackup"
      - "/config/services/borgbackup" -> same
      - "config/services/borgbackup" -> "/config/services/borgbackup"
    """
    x = x.strip()
    if not x:
        raise ValueError("Empty xpath/key.")
    if "/" not in x and not x.startswith("/"):
        return f"/config/services/{x}"
    if not x.startswith("/"):
        x = "/" + x
    return x


def xpath_to_segments(xpath: str) -> List[str]:
    # "/config/services/borgbackup" -> ["config", "services", "borgbackup"]
    xpath = xpath.strip()
    if not xpath.startswith("/"):
        raise ValueError("xpath must start with '/'.")
    segs = [s for s in xpath.split("/") if s]
    if not segs:
        raise ValueError("Invalid xpath.")
    return segs


def load_xml(path: Path) -> ET.ElementTree:
    try:
        return ET.parse(path)
    except FileNotFoundError:
        raise SystemExit(f"DB file not found: {path}")
    except ET.ParseError as ex:
        raise SystemExit(f"XML parse error in {path}: {ex}")


def find_child(parent: ET.Element, tag: str) -> Optional[ET.Element]:
    for c in list(parent):
        if c.tag == tag:
            return c
    return None


def ensure_path(root: ET.Element, segments: List[str]) -> Tuple[ET.Element, ET.Element]:
    """
    Ensure all segments exist under root, creating nodes as needed.

    Returns (parent_of_target, target_node)
    where target_node corresponds to last segment.
    """
    # Root element in OMV config.xml is typically <config>.
    # If the xpath begins with "config", we treat that as the document root.
    if segments[0] == root.tag:
        segments = segments[1:]
    if not segments:
        raise ValueError("xpath points to the root itself; not supported.")

    cur = root
    for tag in segments[:-1]:
        nxt = find_child(cur, tag)
        if nxt is None:
            nxt = ET.SubElement(cur, tag)
        cur = nxt

    target_tag = segments[-1]
    target = find_child(cur, target_tag)
    if target is None:
        target = ET.SubElement(cur, target_tag)
    return cur, target


def delete_child(parent: ET.Element, child: ET.Element) -> None:
    parent.remove(child)


def get_subtree_xml(root: ET.Element, xpath: str) -> Optional[str]:
    """
    Return pretty-printed XML for the element at xpath, or None if not found.
    """
    segs = xpath_to_segments(xpath)
    elem = find_by_path(root, segs)
    if elem is None:
        return None
    return element_to_pretty_xml(elem).rstrip("\n")


def normalize_diff_text(s: str) -> str:
    # 1) Strip trailing spaces/tabs on each line
    lines = [ln.rstrip(" \t") for ln in s.splitlines()]
    # 2) Remove trailing blank lines
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def print_subtree_diff(old_subtree: Optional[str], new_subtree: str, title: str) -> None:
    """
    Diff old vs new subtree. If old_subtree is None, show it as an add.
    """
    if old_subtree is None:
        old_subtree = ""

    old_subtree = normalize_diff_text(old_subtree)
    new_subtree = normalize_diff_text(new_subtree)

    if old_subtree == new_subtree:
        print("(no subtree changes)")
        return

    diff = difflib.unified_diff(
        old_subtree.splitlines(),
        new_subtree.splitlines(),
        fromfile=f"{title} (current)",
        tofile=f"{title} (restored)",
        lineterm="",
    )

    first_hunk = True
    for line in diff:
        if line.startswith("@@"):
            if not first_hunk:
                print()
            first_hunk = False
        print(line)


def element_to_pretty_xml(elem: ET.Element) -> str:
    # xml.etree doesn't pretty-print by default; use indent (py3.9+)
    # We'll clone into a new tree to avoid modifying original indentation.
    tmp = ET.Element(elem.tag, elem.attrib)
    tmp.text = elem.text
    tmp.tail = elem.tail
    for c in list(elem):
        tmp.append(deep_copy(c))

    ET.indent(tmp, space="  ", level=0)
    xml = ET.tostring(tmp, encoding="unicode")
    if not xml.endswith("\n"):
        xml += "\n"
    return xml


def serialize_tree(tree: ET.ElementTree) -> str:
    # Ensure pretty indentation for stable diff output
    root = tree.getroot()
    ET.indent(root, space="  ", level=0)
    return ET.tostring(root, encoding="unicode")


def print_unified_diff(old_text: str, new_text: str, fromfile: str, tofile: str) -> None:
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile=fromfile,
        tofile=tofile,
        lineterm=""
    )
    for line in diff:
        print(line)


def deep_copy(elem: ET.Element) -> ET.Element:
    new = ET.Element(elem.tag, elem.attrib)
    new.text = elem.text
    new.tail = elem.tail
    for c in list(elem):
        new.append(deep_copy(c))
    return new


def read_fragment(fragment_path: Path) -> ET.Element:
    data = fragment_path.read_text(encoding="utf-8").strip()
    if not data:
        raise SystemExit(f"Fragment file is empty: {fragment_path}")
    try:
        return ET.fromstring(data)
    except ET.ParseError as ex:
        raise SystemExit(f"Fragment XML parse error in {fragment_path}: {ex}")


def backup_section(db_path: Path, xpath: str, out_path: Path) -> None:
    tree = load_xml(db_path)
    root = tree.getroot()

    segs = xpath_to_segments(xpath)
    # Navigate without creating
    cur = root
    if segs[0] == root.tag:
        segs = segs[1:]
    for tag in segs:
        nxt = find_child(cur, tag)
        if nxt is None:
            raise SystemExit(f"Path not found in DB: {xpath}")
        cur = nxt

    out_path.write_text(element_to_pretty_xml(cur), encoding="utf-8")
    print(f"Wrote backup fragment: {out_path}")


def find_by_path(root: ET.Element, segments: List[str]) -> Optional[ET.Element]:
    """
    Navigate segments under root without creating anything.
    Supports xpaths that begin with the root tag (e.g. /config/... when root is <config>).
    """
    cur = root
    if segments and segments[0] == root.tag:
        segments = segments[1:]
    for tag in segments:
        nxt = find_child(cur, tag)
        if nxt is None:
            return None
        cur = nxt
    return cur

def count_children_at_xpath(root: ET.Element, parent_xpath: str, child_tag: str) -> int:
    parent_segs = xpath_to_segments(parent_xpath)
    parent = find_by_path(root, parent_segs)
    if parent is None:
        return 0
    return sum(1 for c in list(parent) if c.tag == child_tag)

def validate_singleton_service(root: ET.Element, restored_xpath: str) -> None:
    # Only enforce this check for the borgbackup service at the canonical location.
    if restored_xpath != "/config/services/borgbackup":
        return

    n = count_children_at_xpath(root, "/config/services", "borgbackup")
    if n != 1:
        raise SystemExit(
            f"Validation failed: expected exactly 1 <borgbackup> under /config/services, found {n}."
        )


def restore_section(db_path: Path, xpath: str, in_path: Path, dry_run: bool, show_diff: bool) -> None:
    tree = load_xml(db_path)
    root = tree.getroot()
    segs = xpath_to_segments(xpath)
    fragment = read_fragment(in_path)

    old_subtree = get_subtree_xml(root, xpath) if show_diff else None
    target_tag = segs[-1]
    if fragment.tag != target_tag:
        raise SystemExit(
            f"Fragment root tag <{fragment.tag}> does not match target <{target_tag}> for xpath {xpath}"
        )

    # Locate/create parent element (/config/services for borgbackup)
    parent_segs = segs[:-1]
    if parent_segs and parent_segs[0] == root.tag:
        ensure_chain = parent_segs[1:]
    else:
        ensure_chain = parent_segs

    cur = root
    for tag in ensure_chain:
        nxt = find_child(cur, tag)
        if nxt is None:
            nxt = ET.SubElement(cur, tag)
        cur = nxt
    parent_elem = cur

    # Replace semantics: remove all existing nodes with the same tag under parent
    existing_targets = [c for c in list(parent_elem) if c.tag == target_tag]
    for c in existing_targets:
        parent_elem.remove(c)

    parent_elem.append(deep_copy(fragment))

    # Validate invariants
    validate_singleton_service(root, xpath)

    if show_diff:
        # Use the fragment as the "after" view (normalized)
        new_subtree = element_to_pretty_xml(fragment).rstrip("\n")
        print_subtree_diff(old_subtree, new_subtree, title=xpath)

    if dry_run:
        print("[dry-run] No write performed.")
        return

    # Backup + write
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".bak.{ts}")
    shutil.copy2(db_path, backup_path)
    print(f"Backed up DB: {backup_path}")

    ET.indent(root, space="  ", level=0)
    tree.write(db_path, encoding="utf-8", xml_declaration=True)
    print(f"Wrote updated DB: {db_path}")


def main():
    p = argparse.ArgumentParser(
        description="Backup/restore a section of OMV's config.xml by xpath or service key."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("backup", help="Backup a subtree to a fragment XML file")
    pb.add_argument("target", help='Service key (e.g. "borgbackup") or xpath (e.g. "/config/services/borgbackup")')
    pb.add_argument("-o", "--out", required=True, help="Output fragment file path")

    pr = sub.add_parser("restore", help="Restore a fragment XML file into the DB")
    pr.add_argument("target", help='Service key (e.g. "borgbackup") or xpath (e.g. "/config/services/borgbackup")')
    pr.add_argument("-i", "--infile", required=True, help="Input fragment file path")
    pr.add_argument("--dry-run", action="store_true", help="Do not write DB file")
    pr.add_argument("--diff", action="store_true", help="Show a unified diff of DB changes")

    require_root()

    args = p.parse_args()
    db_path = Path("/etc/openmediavault/config.xml")
    xpath = normalize_xpath(args.target)

    if args.cmd == "backup":
        backup_section(db_path=db_path, xpath=xpath, out_path=Path(args.out))
    elif args.cmd == "restore":
        restore_section(db_path=db_path, xpath=xpath, in_path=Path(args.infile), dry_run=args.dry_run, show_diff=args.diff)

    else:
        raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
