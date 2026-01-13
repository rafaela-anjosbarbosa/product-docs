# ADR-0001: Adoção de Docs-as-Code para documentação funcional

**Data:** 2025-12-23

## Contexto
O sistema é grande e a documentação atual no EA vincula requisitos a componentes de protótipos. A prototipação no EA é morosa.

## Decisão
- Prototipação visual passa a ser feita em ferramenta dedicada (ex: Figma).
- Comportamento e rastreabilidade passam a ser mantidos como **Docs-as-Code** (YAML + Markdown).
- Um script de validação garante consistência e gera a matriz de rastreabilidade.

## Consequências
- Versionamento natural em Git.
- Maior prontidão para automações (testes, IA, geração de docs).
- Requer disciplina mínima de IDs e revisão.
