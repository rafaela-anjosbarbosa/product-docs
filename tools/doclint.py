\
import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Minimal YAML loader (fallback) to avoid deps.
# Supports: key: value, nested dict via indentation, lists with "- ".
# For full YAML features, you can replace with PyYAML safely.
def load_simple_yaml(text: str) -> Any:
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    # Remove empty and comment-only lines
    raw = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        raw.append(ln)

    def parse_block(start: int, indent: int) -> Tuple[Any, int]:
        obj = None
        i = start
        while i < len(raw):
            ln = raw[i]
            cur_indent = len(ln) - len(ln.lstrip(" "))
            if cur_indent < indent:
                break
            if cur_indent > indent:
                # should not happen at top of block; let parent handle
                break

            stripped = ln.strip()

            # list item
            if stripped.startswith("- "):
                if obj is None:
                    obj = []
                if not isinstance(obj, list):
                    raise ValueError(f"Invalid YAML: mixed mapping/list near line: {ln}")
                item_text = stripped[2:].strip()
                # item can be "key: value" mapping
                if ":" in item_text and not item_text.startswith('"') and not item_text.startswith("'"):
                    key, val = item_text.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    item: Dict[str, Any] = {}
                    if val == "":
                        # nested block
                        nested, j = parse_block(i + 1, indent + 2)
                        item[key] = nested
                        obj.append(item)
                        i = j
                        continue
                    else:
                        item[key] = parse_scalar(val)
                        # may have more nested keys on following indented lines
                        nested, j = parse_block(i + 1, indent + 2)
                        if isinstance(nested, dict):
                            item.update(nested)
                        elif nested is not None:
                            # unusual
                            item["_nested"] = nested
                        obj.append(item)
                        i = j
                        continue
                else:
                    obj.append(parse_scalar(item_text))
                    i += 1
                    continue

            # mapping entry
            if ":" in stripped:
                if obj is None:
                    obj = {}
                if not isinstance(obj, dict):
                    raise ValueError(f"Invalid YAML: mixed list/mapping near line: {ln}")
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip()
                if val == "":
                    nested, j = parse_block(i + 1, indent + 2)
                    obj[key] = nested
                    i = j
                    continue
                else:
                    obj[key] = parse_scalar(val)
                    # attach nested if exists (for keys like 'behavior:' sometimes val present)
                    i += 1
                    continue
            else:
                raise ValueError(f"Invalid YAML line: {ln}")

        return obj if obj is not None else {}, i

    def parse_scalar(val: str) -> Any:
        v = val.strip()
        # strip quotes
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        # booleans
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        # numbers
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d+\.\d+", v):
            return float(v)
        return v

    def parse_scalar(val: str) -> Any:
        v = val.strip()
        # Folded block marker not supported; store as-is
        if v in (">", "|"):
            return v
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d+\.\d+", v):
            return float(v)
        return v

    parsed, _ = parse_block(0, 0)

    # Handle very common folded style "purpose: >" blocks (simple support)
    # We'll re-scan original text for keys with ">" or "|" and capture subsequent indented lines.
    # This is intentionally minimal.
    def inject_folded(key: str, marker: str, data: dict):
        pattern = re.compile(rf"^{re.escape(key)}:\s*{re.escape(marker)}\s*$", re.MULTILINE)
        m = pattern.search(text)
        if not m:
            return
        start = m.end()
        rest = text[start:].splitlines()
        collected = []
        for ln in rest:
            if not ln.strip():
                collected.append("")
                continue
            if not ln.startswith("  "):
                break
            collected.append(ln[2:])
        data[key] = "\n".join(collected).strip()

    if isinstance(parsed, dict):
        for k in ("purpose",):
            if parsed.get(k) in (">", "|"):
                inject_folded(k, ">", parsed)
                inject_folded(k, "|", parsed)

    return parsed


@dataclass
class DocIndex:
    screens: Dict[str, dict]
    components: Dict[str, dict]
    requirements: Dict[str, dict]
    rules: Dict[str, dict]
    flows: Dict[str, dict]
    messages: Dict[str, dict]  # id -> message obj
    errors: List[str]
    warnings: List[str]


ID_PATTERNS = {
    "screen": re.compile(r"^TELA_[A-Z0-9_]+$"),
    "component": re.compile(r"^(INP|BTN|LBL|SEL|TAB|GRD|CHK|RAD|TXT|LNK|ICO|MOD)_[A-Z0-9_]+$"),
    "requirement": re.compile(r"^RF-\d{3}$"),
    "rule": re.compile(r"^RN-\d{3}$"),
    "flow": re.compile(r"^UC-\d{3}-.+"),
    "message": re.compile(r"^MSG-[A-Z0-9-]+$"),
}


def read_yaml(path: Path) -> dict:
    return load_simple_yaml(path.read_text(encoding="utf-8"))


def index_docs(root: Path, system: str) -> DocIndex:
    base = root / "20-systems" / system
    errors: List[str] = []
    warnings: List[str] = []

    screens: Dict[str, dict] = {}
    components: Dict[str, dict] = {}
    requirements: Dict[str, dict] = {}
    rules: Dict[str, dict] = {}
    flows: Dict[str, dict] = {}
    messages: Dict[str, dict] = {}

    # Screens
    screens_dir = base / "21-screens"
    if screens_dir.exists():
        for screen_folder in screens_dir.iterdir():
            if not screen_folder.is_dir():
                continue
            yml = screen_folder / "screen.yml"
            if not yml.exists():
                continue
            data = read_yaml(yml)
            sid = str(data.get("id", "")).strip()
            if not sid:
                errors.append(f"[screen] missing id in {yml}")
                continue
            screens[sid] = {"path": str(yml), "data": data}

            # messages.yml (optional) inside screen folder
            msg_path = screen_folder / "messages.yml"
            if msg_path.exists():
                msg_data = read_yaml(msg_path)
                for m in (msg_data.get("messages") or []):
                    mid = str(m.get("id", "")).strip()
                    if mid:
                        messages[mid] = m

    # Components
    comp_dir = base / "22-components"
    if comp_dir.exists():
        for p in comp_dir.glob("*.yml"):
            data = read_yaml(p)
            cid = str(data.get("id", "")).strip()
            if not cid:
                errors.append(f"[component] missing id in {p}")
                continue
            components[cid] = {"path": str(p), "data": data}

    # Requirements
    req_dir = base / "23-requirements"
    if req_dir.exists():
        for p in req_dir.glob("RF-*.yml"):
            data = read_yaml(p)
            rid = str(data.get("id", "")).strip()
            if not rid:
                errors.append(f"[requirement] missing id in {p}")
                continue
            requirements[rid] = {"path": str(p), "data": data}

    # Rules
    rule_dir = base / "24-rules"
    if rule_dir.exists():
        for p in rule_dir.glob("RN-*.yml"):
            data = read_yaml(p)
            ruid = str(data.get("id", "")).strip()
            if not ruid:
                errors.append(f"[rule] missing id in {p}")
                continue
            rules[ruid] = {"path": str(p), "data": data}

    # Flows
    flow_dir = base / "25-flows"
    if flow_dir.exists():
        for p in flow_dir.glob("UC-*.yml"):
            data = read_yaml(p)
            fid = str(data.get("id", "")).strip()
            if not fid:
                errors.append(f"[flow] missing id in {p}")
                continue
            flows[fid] = {"path": str(p), "data": data}

    idx = DocIndex(
        screens=screens,
        components=components,
        requirements=requirements,
        rules=rules,
        flows=flows,
        messages=messages,
        errors=errors,
        warnings=warnings,
    )
    run_validations(idx)
    return idx


def validate_id(kind: str, _id: str, where: str, idx: DocIndex):
    pat = ID_PATTERNS.get(kind)
    if pat and not pat.match(_id):
        idx.warnings.append(f"[id] {kind} id '{_id}' fora do padrão em {where}")


def ensure_ref_exists(kind: str, ref_id: str, where: str, idx: DocIndex):
    ref_map = {
        "screen": idx.screens,
        "component": idx.components,
        "requirement": idx.requirements,
        "rule": idx.rules,
        "flow": idx.flows,
        "message": idx.messages,
    }
    m = ref_map.get(kind)
    if m is None:
        return
    if ref_id not in m:
        idx.errors.append(f"[ref] {kind} '{ref_id}' não encontrado. Referenciado em {where}")


def run_validations(idx: DocIndex):
    # Validate IDs and cross-refs

    # Screens
    for sid, item in idx.screens.items():
        data = item["data"]
        validate_id("screen", sid, item["path"], idx)

        for c in (data.get("components") or []):
            cid = c.get("id") if isinstance(c, dict) else c
            if cid:
                ensure_ref_exists("component", cid, item["path"], idx)

        for rid in (data.get("requirements") or []):
            if rid:
                ensure_ref_exists("requirement", rid, item["path"], idx)

        for ruid in (data.get("rules") or []):
            if ruid:
                ensure_ref_exists("rule", ruid, item["path"], idx)

        for fid in (data.get("flows") or []):
            if fid:
                ensure_ref_exists("flow", fid, item["path"], idx)

    # Components
    for cid, item in idx.components.items():
        data = item["data"]
        validate_id("component", cid, item["path"], idx)
        for s in (data.get("screens") or []):
            if s:
                ensure_ref_exists("screen", s, item["path"], idx)

        for v in (data.get("validations") or []):
            ref = v.get("ref") if isinstance(v, dict) else v
            if ref:
                # could be RN or RF
                if ref.startswith("RN-"):
                    ensure_ref_exists("rule", ref, item["path"], idx)
                elif ref.startswith("RF-"):
                    ensure_ref_exists("requirement", ref, item["path"], idx)

        for bref in (data.get("behavior_refs") or []):
            if bref and bref.startswith("UC-"):
                ensure_ref_exists("flow", bref, item["path"], idx)

    # Requirements
    for rid, item in idx.requirements.items():
        data = item["data"]
        validate_id("requirement", rid, item["path"], idx)

        scope = data.get("scope") or {}
        s = scope.get("screen")
        c = scope.get("component")
        if s:
            ensure_ref_exists("screen", s, item["path"], idx)
        if c:
            ensure_ref_exists("component", c, item["path"], idx)

        # messages referenced in behavior
        behavior = data.get("behavior") or {}
        alternatives = behavior.get("alternatives") or []
        for alt in alternatives:
            if isinstance(alt, dict):
                then = alt.get("then") or []
                for act in then:
                    if isinstance(act, dict) and "show_message" in act:
                        mid = act["show_message"]
                        ensure_ref_exists("message", mid, item["path"], idx)

        links = data.get("links") or {}
        for r in (links.get("rules") or []):
            ensure_ref_exists("rule", r, item["path"], idx)
        for f in (links.get("flows") or []):
            ensure_ref_exists("flow", f, item["path"], idx)
        for m in (links.get("messages") or []):
            ensure_ref_exists("message", m, item["path"], idx)

    # Rules
    for ruid, item in idx.rules.items():
        data = item["data"]
        validate_id("rule", ruid, item["path"], idx)
        msg = (data.get("message") or {}).get("ref")
        if msg:
            ensure_ref_exists("message", msg, item["path"], idx)

        applies = data.get("applies_to") or {}
        for s in (applies.get("screens") or []):
            ensure_ref_exists("screen", s, item["path"], idx)
        for c in (applies.get("components") or []):
            ensure_ref_exists("component", c, item["path"], idx)

    # Flows
    for fid, item in idx.flows.items():
        data = item["data"]
        validate_id("flow", fid, item["path"], idx)
        trig = data.get("trigger") or {}
        s = trig.get("screen")
        c = trig.get("component")
        if s:
            ensure_ref_exists("screen", s, item["path"], idx)
        if c:
            ensure_ref_exists("component", c, item["path"], idx)

        # refs in steps
        def scan_refs(obj):
            if isinstance(obj, list):
                for it in obj:
                    scan_refs(it)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "refs" and isinstance(v, list):
                        for ref in v:
                            if isinstance(ref, str):
                                if ref.startswith("RF-"):
                                    ensure_ref_exists("requirement", ref, item["path"], idx)
                                elif ref.startswith("RN-"):
                                    ensure_ref_exists("rule", ref, item["path"], idx)
                                elif ref.startswith("UC-"):
                                    ensure_ref_exists("flow", ref, item["path"], idx)
                                elif ref.startswith("MSG-"):
                                    ensure_ref_exists("message", ref, item["path"], idx)
                    else:
                        scan_refs(v)

        scan_refs(data.get("main_flow") or [])
        scan_refs(data.get("alternative_flows") or [])


def build_trace_matrix(idx: DocIndex) -> str:
    # Matrix rows: Screen | Component | Requirements | Rules | Flows | Figma URL
    rows = []
    for sid, sitem in sorted(idx.screens.items(), key=lambda x: x[0]):
        sdata = sitem["data"]
        figma_url = ((sdata.get("figma") or {}).get("url")) or ""
        components = [c.get("id") if isinstance(c, dict) else c for c in (sdata.get("components") or [])]
        reqs = sdata.get("requirements") or []
        rules = sdata.get("rules") or []
        flows = sdata.get("flows") or []

        # expand by component for readability
        if not components:
            rows.append((sid, "", ", ".join(reqs), ", ".join(rules), ", ".join(flows), figma_url))
        else:
            for cid in components:
                rows.append((sid, cid, ", ".join(reqs), ", ".join(rules), ", ".join(flows), figma_url))

    md = []
    md.append("# Matriz de rastreabilidade (gerada)")
    md.append("")
    md.append("| Tela | Componente | Requisitos | Regras | Fluxos | Figma |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        tela, comp, reqs, rules, flows, figma = r
        md.append(f"| `{tela}` | `{comp}` | {fmt_list(reqs)} | {fmt_list(rules)} | {fmt_list(flows)} | {fmt_link(figma)} |")
    md.append("")
    return "\n".join(md)


def fmt_list(s: str) -> str:
    if not s:
        return ""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return " ".join([f"`{p}`" for p in parts])


def fmt_link(url: str) -> str:
    if not url:
        return ""
    return f"[link]({url})"


def main():
    ap = argparse.ArgumentParser(description="Docs-as-Code Lint + Traceability Matrix generator")
    ap.add_argument("--root", default="docs", help="Pasta root de docs (default: docs)")
    ap.add_argument("--system", required=True, help="Sistema (ex: sgn)")
    ap.add_argument("--write-matrix", action="store_true", help="Escreve matrix.md em 27-traceability")
    args = ap.parse_args()

    root = Path(args.root)
    idx = index_docs(root, args.system)

    # Report
    if idx.warnings:
        print("\nWarnings:")
        for w in idx.warnings:
            print(" -", w)

    if idx.errors:
        print("\nErrors:")
        for e in idx.errors:
            print(" -", e)
        raise SystemExit(2)

    print("\nOK: referências consistentes.")

    matrix = build_trace_matrix(idx)
    if args.write_matrix:
        out = root / "20-systems" / args.system / "27-traceability" / "matrix.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(matrix, encoding="utf-8")
        print("Matriz escrita em:", out.as_posix())
    else:
        print("\n--- MATRIX PREVIEW ---\n")
        print(matrix)


if __name__ == "__main__":
    main()
