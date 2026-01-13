# Product Docs (Docs-as-Code Starter)

Este repositório é um **starter** para documentação de produto/sistema no estilo **Docs-as-Code** (substituindo o papel do EA em: tela → componente → requisito → regra → fluxo), com:
- Estrutura de pastas padronizada
- Templates YAML
- Site de docs via **MkDocs**
- Script de **validação/lint** + geração de **matriz de rastreabilidade**

## Requisitos
- Python 3.10+
- (Opcional) MkDocs para visualizar o site

## Como visualizar o site
```bash
pip install mkdocs-material
mkdocs serve
```

## Como validar e gerar a matriz
```bash
python tools/doclint.py --root docs --system sgn --write-matrix
```

## Convenções (resumo)
- Telas: `TELA_*`
- Componentes: `INP_*`, `BTN_*`, `LBL_*`, etc.
- Requisitos: `RF-###`
- Regras: `RN-###`
- Fluxos: `UC-###-*`
- Mensagens: `MSG-*`

> **Regra de ouro**: Figma = visual | Docs-as-code = comportamento.

## Publicar automaticamente no GitHub Pages (sem instalação para analistas)

1) Crie/importe o repositório no GitHub e suba este conteúdo.
2) No GitHub: **Settings → Pages**
   - Em **Build and deployment**
   - **Source:** *GitHub Actions*
3) Faça push para a branch **main**.

O workflow em `.github/workflows/docs.yml` vai:
- instalar dependências
- rodar `tools/doclint.py` (quebra o build se tiver referência inválida)
- rodar `mkdocs build --strict`
- publicar automaticamente no GitHub Pages

> Observação: se sua branch principal for `master`, altere o workflow para `branches: ["master"]`.

### URL do site
A URL final será algo como:
`https://<org-ou-user>.github.io/<repo>/`

Para links absolutos, ajuste `site_url` no `mkdocs.yml`.
