#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List
import yaml


# ----------------------------
# Utils
# ----------------------------
def load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def clear_dir(path: Path):
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()


def ensure_list(x) -> List[Any]:
    return x if isinstance(x, list) else []


def md_link(text: str, href: str) -> str:
    return f"[{text}]({href})" if href else text


def md_id_link(_id: str, href: str) -> str:
    return f"[`{_id}`]({href})" if href else f"`{_id}`"


def safe_str(x: Any) -> str:
    return "" if x is None else str(x)


# ----------------------------
# Normalization
# Source of truth: modules/*/module.yml
#
# Expected shape (per screen):
# screens:
#  - id, name, purpose, figma{url}, runtime{url{prd}}
#    components:
#      - id, name, type, runtime{test_id}
#        requirements:
#          - id, name, acceptance_criteria
#            rules:
#              - id, name, expression, description
# ----------------------------
def normalize_module(module_yml: Dict[str, Any]) -> Dict[str, Any]:
    mod = module_yml.get("module") or {}
    screens = ensure_list(module_yml.get("screens"))

    # Collect uniques (useful for generating detail pages + links)
    comps: Dict[str, Dict[str, Any]] = {}
    reqs: Dict[str, Dict[str, Any]] = {}
    rules: Dict[str, Dict[str, Any]] = {}
    flows: Dict[str, Dict[str, Any]] = {}

    def put(store: Dict[str, Dict[str, Any]], obj: Dict[str, Any]):
        _id = obj.get("id")
        if not _id:
            return
        if _id not in store:
            store[_id] = obj
        else:
            # merge only missing fields
            for k, v in obj.items():
                if k not in store[_id] or store[_id][k] in ("", None, [], {}):
                    store[_id][k] = v

    for s in screens:
        # flows at screen level optional
        for f in ensure_list(s.get("flows")):
            if isinstance(f, dict):
                put(flows, f)

        for c in ensure_list(s.get("components")):
            if not isinstance(c, dict):
                continue
            put(comps, c)

            for rq in ensure_list(c.get("requirements")):
                if not isinstance(rq, dict):
                    continue
                put(reqs, rq)

                for rn in ensure_list(rq.get("rules")):
                    if isinstance(rn, dict):
                        put(rules, rn)

    return {
        "module": mod,
        "screens": screens,
        "components": list(comps.values()),
        "requirements": list(reqs.values()),
        "rules": list(rules.values()),
        "flows": list(flows.values()),
    }


# ----------------------------
# Rendering
# Output:
# docs/generated/<system>/
#   index.md                          (lists modules)
#   modules/<slug>/
#       index.md                      (ONLY: Telas + Fluxos)
#       screens/index.md
#       screens/<SCREEN_ID>/index.md  (shows component -> requirement -> rules)
#       flows/index.md (+ details if you define flows)
#       components/<ID>/index.md      (optional details)
#       requirements/<ID>/index.md    (optional details)
#       rules/<ID>/index.md           (optional details)
# ----------------------------
def render_entity_page(title_id: str, title_name: str, obj: Dict[str, Any]) -> str:
    lines: List[str] = [f"# {title_id} — {title_name}\n"]

    # optional metadata
    for k in ("type", "status", "priority"):
        if k in obj:
            lines.append(f"- **{k}:** `{safe_str(obj.get(k))}`")
    if len(lines) > 1:
        lines.append("")

    # expression/description for rules
    if obj.get("expression"):
        lines.append(f"**Expressão:** `{safe_str(obj.get('expression'))}`  ")
    if obj.get("description"):
        lines.append(safe_str(obj.get("description")))
        lines.append("")

    ac = ensure_list(obj.get("acceptance_criteria"))
    if ac:
        lines.append("## Critérios de aceite\n")
        for c in ac:
            lines.append(f"- {safe_str(c)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_module_pages(system: str, module_slug: str, module_data: Dict[str, Any], out_root: Path):
    base = out_root / "modules" / module_slug

    mod = module_data.get("module") or {}
    mod_id = mod.get("id", module_slug)
    mod_name = mod.get("name", module_slug)
    owner = mod.get("owner", "")

    # ---- module landing (as requested: no component/req/rule links here) ----
    screens = []
    for s in module_data.get("screens", []):
        sid = s.get("id")
        if sid:
            screens.append({"id": sid, "name": s.get("name", sid)})

    flows = []
    for f in module_data.get("flows", []):
        fid = f.get("id")
        if fid:
            flows.append({"id": fid, "name": f.get("name") or f.get("title") or fid})

    module_md = [f"# {mod_id} — {mod_name}\n\n"]
    if owner:
        module_md.append(f"**Owner:** `{owner}`\n\n")

    module_md.append("## Telas\n\n")
    if screens:
        for it in screens:
            module_md.append(f"- [{it['id']} — {it['name']}](./screens/{it['id']}/)\n")
    else:
        module_md.append("_(nenhuma)_\n")

    module_md.append("\n## Fluxos\n\n")
    if flows:
        for it in flows:
            module_md.append(f"- [{it['id']} — {it['name']}](./flows/{it['id']}/)\n")
    else:
        module_md.append("_(nenhum)_\n")

    write(base / "index.md", "".join(module_md))

    # ---- indices ----
    write(
        base / "screens" / "index.md",
        "# Telas\n\n" + ("".join([f"- [{s['id']} — {s['name']}](./{s['id']}/)\n" for s in screens]) if screens else "_(nenhuma)_\n"),
    )

    write(
        base / "flows" / "index.md",
        "# Fluxos\n\n" + ("".join([f"- [{f['id']} — {f['name']}](./{f['id']}/)\n" for f in flows]) if flows else "_(nenhum)_\n"),
    )

    # Optional indices (not linked from module page, but used by links inside screens)
    comps = [{"id": c.get("id"), "name": c.get("name") or c.get("title") or c.get("id")} for c in module_data.get("components", []) if c.get("id")]
    reqs = [{"id": r.get("id"), "name": r.get("name") or r.get("title") or r.get("id")} for r in module_data.get("requirements", []) if r.get("id")]
    rns  = [{"id": r.get("id"), "name": r.get("name") or r.get("title") or r.get("id")} for r in module_data.get("rules", []) if r.get("id")]

    write(base / "components" / "index.md", "# Componentes\n\n" + ("".join([f"- [{c['id']} — {c['name']}](./{c['id']}/)\n" for c in comps]) if comps else "_(nenhum)_\n"))
    write(base / "requirements" / "index.md", "# Requisitos\n\n" + ("".join([f"- [{r['id']} — {r['name']}](./{r['id']}/)\n" for r in reqs]) if reqs else "_(nenhum)_\n"))
    write(base / "rules" / "index.md", "# Regras\n\n" + ("".join([f"- [{r['id']} — {r['name']}](./{r['id']}/)\n" for r in rns]) if rns else "_(nenhum)_\n"))

    # ---- detail pages: screens with traceability (component -> requirement -> rules) ----
    for s in module_data.get("screens", []):
        sid = s.get("id")
        if not sid:
            continue

        figma = s.get("figma") or {}
        runtime = s.get("runtime") or {}
        url = runtime.get("url") or {}
        prd_url = url.get("prd", "") if isinstance(url, dict) else ""

        lines: List[str] = []
        lines.append(f"# {sid} — {s.get('name', sid)}\n")

        purpose = s.get("purpose")
        if purpose:
            lines.append("## Objetivo\n")
            lines.append(safe_str(purpose).strip() + "\n")

        # Links
        lines.append("## Links\n")
        if figma.get("url"):
            lines.append(f"- Figma: {md_link(figma.get('url'), figma.get('url'))}")
        if prd_url:
            lines.append(f"- Sistema (PRD): {md_link(prd_url, prd_url)}")
        if not figma.get("url") and not prd_url:
            lines.append("_(nenhum)_")
        lines.append("")

        # Traceability
        lines.append("## Componentes e Regras\n")
        comps_screen = ensure_list(s.get("components"))

        if not comps_screen:
            lines.append("_(nenhum)_\n")
        else:
            for c in comps_screen:
                if not isinstance(c, dict):
                    continue
                cid = c.get("id", "")
                cname = c.get("name") or cid
                ctype = c.get("type", "")
                c_rt = c.get("runtime") or {}
                c_test_id = c_rt.get("test_id") if isinstance(c_rt, dict) else ""

                # Component header
                comp_header = f"### {cid} — {cname}"
                if ctype:
                    comp_header += f"  \n**Tipo:** `{ctype}`"
                if c_test_id:
                    comp_header += f"  \n**Implementação (test_id):** `{c_test_id}`"
                lines.append(comp_header + "\n")

                reqs_comp = ensure_list(c.get("requirements"))
                if not reqs_comp:
                    lines.append("_(sem requisitos vinculados)_\n")
                    continue

                for rq in reqs_comp:
                    if not isinstance(rq, dict):
                        continue
                    rid = rq.get("id", "")
                    rname = rq.get("name") or rq.get("title") or rid

                    # Link requirement to module requirement page
                    req_href = f"../../requirements/{rid}/" if rid else ""
                    lines.append(f"- **Requisito:** {md_id_link(rid, req_href)} — {rname}")

                    # acceptance criteria (optional inline)
                    ac = ensure_list(rq.get("acceptance_criteria"))
                    if ac:
                        for ccc in ac:
                            lines.append(f"  - _Aceite:_ {safe_str(ccc)}")

                    # rules under requirement
                    rules_req = ensure_list(rq.get("rules"))
                    if rules_req:
                        lines.append("  - **Regras:**")
                        for rn in rules_req:
                            if not isinstance(rn, dict):
                                continue
                            nid = rn.get("id", "")
                            nname = rn.get("name") or rn.get("title") or nid
                            rn_href = f"../../rules/{nid}/" if nid else ""
                            expr = rn.get("expression")
                            if expr:
                                lines.append(f"    - {md_id_link(nid, rn_href)} — {nname}  \n      `expressão:` `{safe_str(expr)}`")
                            else:
                                lines.append(f"    - {md_id_link(nid, rn_href)} — {nname}")
                    else:
                        lines.append("  - **Regras:** _(nenhuma)_")

                lines.append("")  # spacing between components

        write(base / "screens" / sid / "index.md", "\n".join(lines).strip() + "\n")

    # ---- optional detail pages for entities (so the links work) ----
    for c in module_data.get("components", []):
        cid = c.get("id")
        if not cid:
            continue
        cname = c.get("name") or c.get("title") or cid
        write(base / "components" / cid / "index.md", render_entity_page(cid, cname, c))

    for r in module_data.get("requirements", []):
        rid = r.get("id")
        if not rid:
            continue
        rname = r.get("name") or r.get("title") or rid
        write(base / "requirements" / rid / "index.md", render_entity_page(rid, rname, r))

    for rn in module_data.get("rules", []):
        nid = rn.get("id")
        if not nid:
            continue
        nname = rn.get("name") or rn.get("title") or nid
        write(base / "rules" / nid / "index.md", render_entity_page(nid, nname, rn))

    for f in module_data.get("flows", []):
        fid = f.get("id")
        if not fid:
            continue
        fname = f.get("name") or f.get("title") or fid
        write(base / "flows" / fid / "index.md", render_entity_page(fid, fname, f))


# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs")
    ap.add_argument("--system", required=True, help="folder name in docs/20-systems/<system>")
    args = ap.parse_args()

    root = Path(args.root)
    system_root = root / "20-systems" / args.system
    out_root = root / "generated" / args.system

    clear_dir(out_root)

    modules_dir = system_root / "modules"
    module_files = sorted(modules_dir.glob("*/module.yml")) if modules_dir.exists() else []

    # System landing: list modules
    hub: List[str] = [f"# {args.system}\n\n", "## Módulos\n\n"]

    if not module_files:
        hub.append("_(nenhum)_\n")
    else:
        for mf in module_files:
            slug = mf.parent.name
            data = normalize_module(load_yaml(mf))
            mod = data.get("module") or {}
            mod_id = mod.get("id", slug)
            mod_name = mod.get("name", slug)

            hub.append(f"- [{mod_id} — {mod_name}](./modules/{slug}/)\n")

            # generate module
            render_module_pages(args.system, slug, data, out_root)

    write(out_root / "index.md", "".join(hub))


if __name__ == "__main__":
    main()
