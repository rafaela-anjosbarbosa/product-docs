#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any, Dict, List
import yaml

def load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def md_escape(s: str) -> str:
    return (s or "").replace("\n", " ").strip()

def md_list(items: List[str]) -> str:
    items = [i for i in items if i]
    return "\n".join([f"- `{i}`" for i in items]) if items else "_(nenhum)_"

def md_link(text: str, href: str) -> str:
    return f"[{text}]({href})" if href else text

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def gen_screen_pages(system_root: Path, out_root: Path):
    screens_dir = system_root / "21-screens"
    out_dir = out_root / "screens"
    index_lines = ["# Telas\n"]
    if not screens_dir.exists():
        write(out_dir / "index.md", "# Telas\n\n_(nenhuma)_\n")
        return

    for screen_folder in sorted([d for d in screens_dir.iterdir() if d.is_dir()]):
        yml = screen_folder / "screen.yml"
        if not yml.exists():
            continue
        data = load_yaml(yml)
        sid = data.get("id", screen_folder.name)
        name = data.get("name", sid)

        figma = data.get("figma", {}) or {}
        figma_url = figma.get("url", "")
        runtime = data.get("runtime", {}) or {}
        runtime_url = runtime.get("url", {}) or {}
        prd_url = runtime_url.get("prd", "")

        components = [c.get("id") for c in (data.get("components") or []) if isinstance(c, dict)]
        requirements = data.get("requirements") or []
        rules = data.get("rules") or []
        flows = data.get("flows") or []

        page = []
        page.append(f"# {sid} — {name}\n")
        page.append(f"**Status:** `{data.get('status','')}`  \n**Módulo:** `{data.get('module','')}`  \n**Owner:** `{data.get('owner','')}`\n")

        purpose = data.get("purpose", "")
        if purpose:
            page.append("## Objetivo\n")
            page.append(purpose.strip() + "\n")

        page.append("## Links\n")
        if figma_url:
            page.append(f"- Figma: {md_link('abrir', figma_url)}\n")
        if prd_url:
            page.append(f"- Sistema (PRD): {md_link('abrir', prd_url)}\n")

        page.append("## Componentes\n")
        page.append(md_list(components) + "\n")

        page.append("## Requisitos\n")
        page.append(md_list(requirements) + "\n")

        page.append("## Regras\n")
        page.append(md_list(rules) + "\n")

        page.append("## Fluxos\n")
        page.append(md_list(flows) + "\n")

        out_path = out_dir / sid / "index.md"
        write(out_path, "\n".join(page))
        index_lines.append(f"- [{sid}](./{sid}/)\n")

    write(out_dir / "index.md", "".join(index_lines))

def gen_simple_entity_pages(src_dir: Path, out_dir: Path, title: str, id_key: str = "id"):
    index_lines = [f"# {title}\n\n"]
    if not src_dir.exists():
        write(out_dir / "index.md", f"# {title}\n\n_(nenhum)_\n")
        return

    files = sorted(list(src_dir.glob("*.yml")))
    for p in files:
        data = load_yaml(p)
        _id = data.get(id_key, p.stem)
        name = data.get("name") or data.get("title") or _id

        page = [f"# {_id} — {md_escape(name)}\n"]

        # Render common metadata
        for k in ("status", "priority", "type", "domain"):
            if k in data:
                page.append(f"- **{k}:** `{data.get(k)}`")
        page.append("")

        # Render known structures (best-effort)
        scope = data.get("scope")
        if isinstance(scope, dict):
            page.append("## Escopo\n")
            page.append(f"- Tela: `{scope.get('screen','')}`")
            page.append(f"- Componente: `{scope.get('component','')}`")
            page.append(f"- Evento: `{scope.get('event','')}`\n")

        rule = data.get("rule")
        if isinstance(rule, dict):
            page.append("## Regra\n")
            if rule.get("expression"):
                page.append(f"**Expressão:** `{rule.get('expression')}`  ")
            if rule.get("description"):
                page.append(rule.get("description"))
            page.append("")

        behavior = data.get("behavior")
        if isinstance(behavior, dict):
            page.append("## Comportamento\n")
            main = behavior.get("main") or []
            if main:
                page.append("**Fluxo principal**")
                for step in main:
                    if isinstance(step, dict) and "step" in step:
                        page.append(f"- {step['step']}")
                    else:
                        page.append(f"- {step}")
            alts = behavior.get("alternatives") or []
            if alts:
                page.append("\n**Alternativas**")
                for alt in alts:
                    if isinstance(alt, dict):
                        when = alt.get("when", "")
                        page.append(f"- Quando: `{when}`")
            page.append("")

        ac = data.get("acceptance_criteria") or []
        if ac:
            page.append("## Critérios de aceite\n")
            for c in ac:
                page.append(f"- {c}")
            page.append("")

        links = data.get("links")
        if isinstance(links, dict):
            page.append("## Links relacionados\n")
            for group, vals in links.items():
                if isinstance(vals, list) and vals:
                    page.append(f"**{group}:** " + " ".join([f"`{v}`" for v in vals]))
            page.append("")

        out_path = out_dir / _id / "index.md"
        write(out_path, "\n".join(page).strip() + "\n")
        index_lines.append(f"- [{]()_
