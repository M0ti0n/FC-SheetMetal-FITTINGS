"""Builds the install zip for the FreeCAD Mod folder.

    python tools/release.py

* DOWNLOAD/HVACFittings.zip is always the latest build (stable download link)
* the build it replaces is moved to DOWNLOAD/OLD/HVACFittings-v<version>.zip
* the zip contains one folder, HVACFittings/, with only what FreeCAD needs
  (no tests, tools, docs, git or download folders)

    python tools/release.py --from-git <commit> <out.zip>
builds the zip of an older commit (used once to fill DOWNLOAD/OLD from the history).
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD = os.path.join(ROOT, "DOWNLOAD")
OLD = os.path.join(DOWNLOAD, "OLD")
CURRENT = os.path.join(DOWNLOAD, "HVACFittings.zip")
SKIP_DIRS = {".git", "tests", "tools", "docs", "DOWNLOAD", "__pycache__", "png", "variants", ".github"}
SKIP_FILES = {".gitignore"}


def version_of(package_xml_text):
    m = re.search(r"<version>([^<]+)</version>", package_xml_text)
    return m.group(1).strip() if m else "unknown"


def _wanted(rel):
    parts = rel.split("/")
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return False
    name = parts[-1]
    return not (name in SKIP_FILES or name.endswith(".pyc") or name.endswith("_preview.png"))


def build_from_tree(out_path, folder="HVACFittings"):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                full = os.path.join(base, f)
                rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                if _wanted(rel):
                    z.write(full, folder + "/" + rel)


def build_from_git(commit, out_path):
    """Zip of an older commit. The workbench was called HVAC Developments up to v0.2.1."""
    tar = subprocess.run(["git", "-C", ROOT, "archive", "--format=tar", commit],
                         check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        pkg = t.extractfile("package.xml").read().decode()
        folder = "HVACDevelopments" if "HVAC Developments" in pkg else "HVACFittings"
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            for m in t.getmembers():
                if m.isfile() and _wanted(m.name):
                    z.writestr(folder + "/" + m.name, t.extractfile(m).read())
    return version_of(pkg)


def zip_version(path):
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.endswith("/package.xml") and n.count("/") == 1][0]
        return version_of(z.read(name).decode())


def release():
    os.makedirs(OLD, exist_ok=True)
    new_version = version_of(open(os.path.join(ROOT, "package.xml")).read())
    if os.path.exists(CURRENT):
        old_version = zip_version(CURRENT)
        if old_version == new_version:
            print("DOWNLOAD/HVACFittings.zip is already v%s - rebuilding it in place" % new_version)
        else:
            target = os.path.join(OLD, "HVACFittings-v%s.zip" % old_version)
            shutil.move(CURRENT, target)
            print("moved the previous build to", os.path.relpath(target, ROOT))
    build_from_tree(CURRENT)
    print("built DOWNLOAD/HVACFittings.zip (v%s)" % new_version)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--from-git":
        print("v" + build_from_git(sys.argv[2], sys.argv[3]))
    else:
        release()
