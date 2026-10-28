#!/usr/bin/env python3
"""Structural guard for neotec_coworker. Run before every push: python verify_tree.py"""

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
APP = ROOT / "neotec_coworker"
MOD = APP / "neotec_coworker"
MODULE = "Neotec Coworker"
CORE_DOCTYPES = {"User", "Role", "DocType", "Notification Log", "File", "Has Role"}
BANNED = re.compile(r"(?i)\b(openbot|copilotkit|agno|agentos|strands|a2ui|ag-ui|langgraph|crewai|alphax)\b")
errors = []


def err(msg):
    errors.append(msg)


def scrub(s):
    return s.lower().replace(" ", "_").replace("-", "_")


# 1. required files
for rel in ["pyproject.toml", "README.md", "CHANGELOG.md", "license.txt", "neotec_coworker/__init__.py",
            "neotec_coworker/hooks.py", "neotec_coworker/modules.txt", "neotec_coworker/patches.txt",
            "neotec_coworker/public/css/coworker.css", "neotec_coworker/public/js/coworker_launcher.js",
            "neotec_coworker/public/images/logo.svg"]:
    if not (ROOT / rel).exists():
        err(f"missing {rel}")

if (APP / "modules.txt").read_text().strip() != MODULE:
    err("modules.txt must contain exactly the module name")

# 2. doctypes
names = set()
links = []
for folder in sorted((MOD / "doctype").iterdir()):
    if not folder.is_dir() or folder.name.startswith("__"):
        continue
    js = folder / f"{folder.name}.json"
    py = folder / f"{folder.name}.py"
    for f in (js, py, folder / "__init__.py"):
        if not f.exists():
            err(f"{folder.name}: missing {f.name}")
    if not js.exists():
        continue
    d = json.loads(js.read_text())
    names.add(d["name"])
    if scrub(d["name"]) != folder.name:
        err(f"{folder.name}: name {d['name']} does not match folder")
    if d.get("module") != MODULE:
        err(f"{d['name']}: module is {d.get('module')}")
    fns = [f["fieldname"] for f in d["fields"]]
    if len(fns) != len(set(fns)):
        err(f"{d['name']}: duplicate fieldnames")
    if d.get("field_order") != fns:
        err(f"{d['name']}: field_order out of sync")
    if d.get("title_field") and d["title_field"] not in fns:
        err(f"{d['name']}: title_field {d['title_field']} missing")
    an = d.get("autoname", "")
    if an.startswith("field:") and an[6:] not in fns:
        err(f"{d['name']}: autoname field missing")
    for f in d["fields"]:
        if f["fieldtype"] in ("Link", "Table") and f.get("options"):
            links.append((d["name"], f["fieldname"], f["options"]))
        if f["fieldtype"] == "Dynamic Link" and f.get("options") not in fns:
            err(f"{d['name']}.{f['fieldname']}: dynamic link source missing")
    if py.exists():
        cls = d["name"].replace(" ", "").replace("-", "")
        tree = ast.parse(py.read_text())
        if cls not in [n.name for n in tree.body if isinstance(n, ast.ClassDef)]:
            err(f"{d['name']}: controller class {cls} not found")
for dt, field, target in links:
    if target not in names and target not in CORE_DOCTYPES:
        err(f"{dt}.{field}: link target {target} unknown")

# 3. pages and workspace
for page in ("coworker", "coworker_setup"):
    for ext in ("json", "js"):
        if not (MOD / "page" / page / f"{page}.{ext}").exists():
            err(f"page {page}: missing .{ext}")
ws = MOD / "workspace" / "neotec_coworker" / "neotec_coworker.json"
if ws.exists():
    w = json.loads(ws.read_text())
    for l in w["links"]:
        if l["type"] == "Link" and l["link_to"] not in names:
            err(f"workspace link to unknown {l['link_to']}")
else:
    err("workspace missing")

# 4. hooks resolve to real functions
hooks = ast.parse((APP / "hooks.py").read_text())
dotted = set()
for node in ast.walk(hooks):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) \
            and node.value.startswith("neotec_coworker.") and "/" not in node.value:
        dotted.add(node.value)
for path in sorted(dotted):
    mod, fn = path.rsplit(".", 1)
    f = ROOT / (mod.replace(".", "/") + ".py")
    if not f.exists():
        err(f"hook {path}: module file missing")
        continue
    if fn not in {n.name for n in ast.parse(f.read_text()).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}:
        err(f"hook {path}: function missing")

# 5. every python file compiles; no stray third-party product names; version consistent
for f in ROOT.rglob("*"):
    if f.is_dir() or "node_modules" in f.parts or f.name == "verify_tree.py":
        continue
    if f.suffix == ".py":
        try:
            compile(f.read_text(), str(f), "exec")
        except SyntaxError as e:
            err(f"{f}: {e}")
    if f.suffix in (".py", ".js", ".json", ".md", ".css", ".csv", ".txt", ".toml"):
        m = BANNED.search(f.read_text(errors="ignore"))
        if m:
            err(f"{f.relative_to(ROOT)}: contains '{m.group(0)}'")

version = re.search(r'__version__ = "([^"]+)"', (APP / "__init__.py").read_text()).group(1)
if f"## {version}" not in (ROOT / "CHANGELOG.md").read_text():
    err(f"CHANGELOG has no entry for {version}")

# 6. every seeded tool exists in code
reg = set(re.findall(r'@tool\("([a-z0-9_]+)"', "".join(p.read_text() for p in (APP / "tools").glob("*.py"))))
seed = (APP / "setup" / "seed.py").read_text()
for t in set(re.findall(r'"([a-z_]+)": "(?:Default|Ask|Auto|Off)"', seed)) | set(re.findall(r'"([a-z_]+)"', seed.split("READ_CORE = [")[1].split("]")[0])):
    if t not in reg:
        err(f"seed grants unknown tool {t}")

if errors:
    print("verify_tree: FAILED")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"verify_tree: OK  ({len(names)} doctypes, {len(reg)} tools, version {version})")
