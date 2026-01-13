# Visão geral de arquitetura de documentação

## Princípios
1. **Figma é visual** (layout, composição, hierarquia).
2. **Docs-as-code é comportamento** (validações, regras, fluxos, critérios).
3. IDs são **estáveis** e garantem rastreabilidade (TELA_*, INP_*, RF-###, RN-###, UC-###, MSG-*).
4. O repositório deve rodar **lint** em CI para impedir referências quebradas.

## Estrutura
- `20-systems/<sistema>/21-screens`: telas
- `22-components`: componentes
- `23-requirements`: requisitos
- `24-rules`: regras de negócio
- `25-flows`: fluxos/casos de uso
- `27-traceability`: matriz gerada automaticamente
