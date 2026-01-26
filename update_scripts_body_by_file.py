#!/usr/bin/env python3

import sys
from xml.etree import ElementTree as ET

def main():
  if len(sys.argv) != 2:
    print("Usage: update_scripts_body_by_file.py /srv/path/to/script")
    exit(1)

  db = "/etc/openmediavault/config.xml"
  xpath = "services/scripts/files/file"

  tree = ET.parse(db)
  root = tree.getroot()

  spath = sys.argv[1]
  fname = spath.split("/")[-1]

  # Find the matching script element
  script_element = None
  for file in root.findall(xpath):
    name = file.find("name").text
    ext = file.find("ext").text
    if f"{name}.{ext}" == fname:
      script_element = file
      break

  if not script_element:
    print(f"Script '{fname}' not found in database")
    exit(1)

  # Read the existing script content
  existing_content = script_element.find("body").text

  # Read the new script content
  with open(spath, 'r') as f:
    new_content = f.read().rstrip()

  # Update the script content only if it has changed
  if existing_content != new_content:
    script_element.find("body").text = new_content
    tree.write(db)
    print(f"Script '{fname}' updated successfully")
  else:
    print(f"Script '{fname}' content is already up-to-date")

if __name__ == "__main__":
  main()
