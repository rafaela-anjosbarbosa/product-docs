#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List
import yaml


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


def md_list_links(items: List[Dict[str, Any]], base: str) -> str:
    # items: [{id,name}]
    if not items:
        return "_(nenhum)_\n"
    out = []
    for it in items:
        _id = it.get("id", "")
        name = it.get("name") or _id
        out.append(f"- [{_id} — {name}]({base}/{_id}/)\n")
    return "".join(out)


def ensure_list(x):
    return x if isinstance(x, list) else []


def normalize_module(module_yml: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aceita module.yml com:
      module: {id,name,owner}
      screens: [ {id,name,figma,runtime,components:[...], requirements:[...], rules:[...], flows:[...]} ]
    e também permite componentes/requisitos/regras dentro do componente (atalho).
    """
    mod = module_yml.get("module") or {}
    screens = ensure_list(module_yml.get("screens"))

    # coletores globais do módulo (dedup por id)
    comps: Dict[str, Dict[str, Any]] = {}
    reqs: Dict[str, Dict[str, Any]] = {}
    rules: Dict[str, Dict[str, Any]] = {}
    flows: Dict[str, Dict[str, Any]] = {}

    # helpers
    def put(d: Dict[str, Dict[str, Any]], obj: Dict[str, Any], kind: str):
        _id = obj.get("id")
        if not _id:
            return
        if _id not in d:
            d[_id] = obj
        else:
            # merge leve sem sobrescrever o que já existe
            for k, v in obj.items():
                if k not in d[_id] or d[_id][k] in ("", None, [], {}):
                    d[_id][k] = v

    for s in screens:
        # screen-level arrays (opcionais)
        for r in ensure_list(s.get("requirements")):
            put(reqs, r, "requirement")
        for r in ensure_list(s.get("rules")):
            put(rules, r, "rule")
        for f in ensure_list(s.get("flows")):
            put(flows, f, "flow")

        for c in ensure_list(s.get("components")):
            put(comps, c, "component")

            # atalhos: component pode conter rules/requirements
            for rr in ensure_list(c.get("rules")):
                put(rules, rr, "rule")
            for rq in ensure_list(c.get("requirements")):
                put(reqs, rq, "requirement")

    return {
        "module": mod,
        "screens": screens,
        "components": list(comps.values()),
        "requirements": list(reqs.values()),
        "rules": list(rules.values()),
        "flows": list(flows.values()),
    }


def render_module_pages(system: str, module_slug: str, module_data: Dict[str, Any], out_root: Path):
    """
    Gera páginas em:
      docs/generated/<system>/modules/<module_slug>/{screens,components,requirements,rules,flows}/...
    """
    mod = module_data["module"] or {}
    mod_id = mod.get("id", module_slug)
    mod_name = mod.get("name", module_slug)
    owner = mod.get("owner", "")

    base = out_root / "modules" / module_slug
    write(base / "index.md",
          f"# {mod_id} — {mod_name}\n\n"
          f"**Owner:** `{owner}`\n\n"
          f"- [Telas](./screens/)\n"
          f"- [Componentes](./components/)\n"
          f"- [Requisitos](./requirements/)\n"
          f"- [Regras](./rules/)\n"
          f"- [Fluxos](./flows/)\n")

    # Indexes
    screens = []
    for s in module_data["screens"]:
        sid = s.get("id")
        if sid:
            screens.append({"id": sid, "name": s.get("name")})

    components = [{"id": c.get("id"), "name": c.get("name")} for c in module_data["components"] if c.get("id")]
    requirements = [{"id": r.get("id"), "name": r.get("name") or r.get("title")} for r in module_data["requirements"] if r.get("id")]
    rules = [{"id": r.get("id"), "name": r.get("name") or r.get("title")} for r in module_data["rules"] if r.get("id")]
    flows = [{"id": f.get("id"), "name": f.get("name") or f.get("title")} for f in module_data["flows"] if f.get("id")]

    write(base / "screens" / "index.md", "# Telas\n\n" + md_list_links(screens, "."))
    write(base / "components" / "index.md", "# Componentes\n\n" + md_list_links(components, "."))
    write(base / "requirements" / "index.md", "# Requisitos\n\n" + md_list_links(requirements, "."))
    write(base / "rules" / "index.md", "# Regras\n\n" + md_list_links(rules, "."))
    write(base / "flows" / "index.md", "# Fluxos\n\n" + md_list_links(flows, "."))

    # Detail pages: Screens
    by_id_req = {r.get("id"): r for r in module_data["requirements"] if r.get("id")}
    by_id_rule = {r.get("id"): r for r in module_data["rules"] if r.get("id")}
    by_id_flow = {f.get("id"): f for f in module_data["flows"] if f.get("id")}
    by_id_comp = {c.get("id"): c for c in module_data["components"] if c.get("id")}

    for s in module_data["screens"]:
        sid = s.get("id")
        if not sid:
            continue
        figma = s.get("figma") or {}
        runtime = s.get("runtime") or {}

        # refs: podem ser IDs (strings) ou objetos (dicts)
        comp_ids = []
        for c in ensure_list(s.get("components")):
            if isinstance(c, dict) and c.get("id"):
                comp_ids.append(c["id"])
            elif isinstance(c, str):
                comp_ids.append(c)

        req_ids = []
        for r in ensure_list(s.get("requirements")):
            if isinstance(r, dict) and r.get("id"):
                req_ids.append(r["id"])
            elif isinstance(r, str):
                req_ids.append(r)

        rule_ids = []
        for r in ensure_list(s.get("rules")):
            if isinstance(r, dict) and r.get("id"):
                rule_ids.append(r["id"])
            elif isinstance(r, str):
                rule_ids.append(r)

        flow_ids = []
        for f in ensure_list(s.get("flows")):
            if isinstance(f, dict) and f.get("id"):
                flow_ids.append(f["id"])
            elif isinstance(f, str):
                flow_ids.append(f)

        md = []
        md.append(f"# {sid} — {s.get('name', sid)}\n")
        if s.get("purpose"):
            md.append("## Objetivo\n")
            md.append(str(s.get("purpose")).strip() + "\n")

        md.append("## Links\n")
        if figma.get("url"):
            md.append(f"- Figma: [{figma.get('url')}]({figma.get('url')})\n")
        url = runtime.get("url") or {}
        if isinstance(url, dict) and url.get("prd"):
            md.append(f"- Sistema (PRD): [{url.get('prd')}]({url.get('prd')})\n")

        md.append("## Componentes\n")
        md.append("\n".join([f"- `{cid}`" for cid in comp_ids]) + ("\n" if comp_ids else "_(nenhum)_\n"))

        md.append("\n## Requisitos\n")
        md.append("\n".join([f"- `{rid}`" for rid in req_ids]) + ("\n" if req_ids else "_(nenhum)_\n"))

        md.append("\n## Regras\n")
        md.append("\n".join([f"- `{rid}`" for rid in rule_ids]) + ("\n" if rule_ids else "_(nenhum)_\n"))

        md.append("\n## Fluxos\n")
        md.append("\n".join([f"- `{fid}`" for fid in flow_ids]) + ("\n" if flow_ids else "_(nenhum)_\n"))

        write(base / "screens" / sid / "index.md", "\n".join(md))

    # Detail pages: Components / Requirements / Rules / Flows (render simples)
    def render_entity(out_dir: Path, obj: Dict[str, Any]):
        _id = obj.get("id")
        if not _id:
            return
        title = obj.get("name") or obj.get("title") or _id
        lines = [f"# {_id} — {title}\n"]

        # links
        fig = obj.get("figma") or {}
        if fig.get("url") or fig.get("node_id"):
            lines.append("## Figma\n")
            if fig.get("url"):
                lines.append(f"- [{fig.get('url')}]({fig.get('url')})")
            if fig.get("node_id"):
                lines.append(f"- node_id: `{fig.get('node_id')}`")
            lines.append("")

        runtime = obj.get("runtime") or {}
        if runtime:
            lines.append("## Implementação\n")
            for k, v in runtime.items():
                if isinstance(v, dict):
                    continue
                lines.append(f"- {k}: `{v}`")
            lines.append("")

        # regra/requisito
        if obj.get("expression"):
            lines.append(f"**Expressão:** `{obj.get('expression')}`\n")
        if obj.get("description"):
            lines.append(str(obj.get("description")) + "\n")

        ac = obj.get("acceptance_criteria") or []
        if ac:
            lines.append("## Critérios de aceite\n")
            for c in ac:
                lines.append(f"- {c}")
            lines.append("")

        write(out_dir / _id / "index.md", "\n".join(lines).strip() + "\n")

    for c in module_data["components"]:
        render_entity(base / "components", c)
    for r in module_data["requirements"]:
        render_entity(base / "requirements", r)
    for r in module_data["rules"]:
        # compat: rule pode vir como {id,expression,description,message}
        render_entity(base / "rules", r)
    for f in module_data["flows"]:
        render_entity(base / "flows", f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs")
    ap.add_argument("--system", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    system_root = root / "20-systems" / args.system
    out_root = root / "generated" / args.system

    clear_dir(out_root)

    # Descobre módulos
    modules_dir = system_root / "modules"
    module_files = sorted(modules_dir.glob("*/module.yml")) if modules_dir.exists() else []

    # System landing
    hub = [f"# {args.system}\n\n"]
    hub.append("## Módulos\n\n")
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

            render_module_pages(args.system, slug, data, out_root)

    write(out_root / "index.md", "".join(hub))


if __name__ == "__main__":
    main()
