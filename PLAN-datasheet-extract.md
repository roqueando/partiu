# PLAN — Generalize datasheet extraction

## Context

`src/partiu/pdf_extract.py` hoje é **todo calibrado para o formato TI/TL062**:

- `_extract_pins()` assume 8 colunas: pin number fixo em `cells[2]`, type em
  `cells[6]`, description em `cells[7]`.
- `_extract_parameters()` assume 10 colunas: MIN/TYP/MAX em `cells[3..5]`,
  UNIT em `cells[9]`.
- `extract()` dispara só com strings exatas "Pin Functions"+"Table" e
  "Electrical Characteristics"+"TEST CONDITIONS".
- `_extract_package()` usa regex fixo; `_detect_manufacturer()` usa lista fixa
  de 8 nomes.

Resultado: PDFs de outros fabricantes/layouts extraem 0 pins / 0 parâmetros.

### Casos reais (anexados em `datasheets/`)

| PDF | Texto extraível? | Parâmetros | Pins |
|-----|------------------|------------|------|
| `tl062.pdf` (TI) | sim | `Electrical Characteristics` (10 cols, sym+nome juntos) | `Pin Functions` (8 cols, multi-package) |
| `LM339-D.PDF` (ST) | sim | `Rating\|Symbol\|Value\|Unit` e `Characteristic\|Symbol\|[Min Typ Max]×3\|Unit` | **não** (pinout é imagem) |
| `infineon-ir2110…` | sim | `Symbol\|Definition\|Min\|Typ\|Max\|Units\|Test Conditions` (elétricas/dinâmicas) e `Symbol\|Definition\|Min\|Max\|Units` (máximas) | `Symbol\|Description` (nome+função, **sem nº de pino** — nº só no diagrama "Lead Assignments", imagem) |
| `sn74ls161a.pdf` (TI 1988) | **não** (escaneado, só header/rodapé) | — | — |

Conclusões que moldam o desenho:
1. A generalização é por **cabeçalho de tabela + heurística de conteúdo**, não
   por posição de coluna.
2. Pins: extrair nome/descrição **mesmo sem número de pino** (Infineon), e sem
   exigir a string "Pin Functions".
3. Parâmetros: suportar os 3 layouts de cabeçalho acima (Min/Typ/Max/Unit,
   Min/Typ/Max×variantes, e Value único).
4. PDFs escaneados (sem camada de texto) ficam **fora do escopo** — exigiram OCR.

## Abordagem

Reescrever `pdf_extract.py` mantendo o **schema de saída** (não muda
`db.py`/`detail.py`):

```python
{"manufacturer","package","package_size",
 "pins":[{"pin_number","name","type","description"}],
 "parameters":[{"category","symbol","name","test_conditions","min","typ","max","unit"}]}
```

Estratégia em 6 partes:

1. **Classificação de tabela por cabeçalho** — para cada tabela de cada página,
   normalizar as células do(s) cabeçalho(s) (lowercase, sem espaços) e casar com
   aliases. Decide se a tabela é *pin* ou *parameter* (ou nenhuma):
   - *pin*: contém colunas `name/pin name/signal/symbol` **e**
     `description/function/definition`, **sem** colunas numéricas
     min/typ/max/unit.
   - *parameter*: contém `min`/`typ`/`max`/`unit`/`value` (ao menos uma delas).
   - Cabeçalhos podem ocupar 1 ou 2 linhas (TL062/LM339 têm 2 linhas); usar as
     2 primeiras linhas não-dados para casar.

2. **Mapeamento por rótulo (header-driven)** — em vez de índices fixos, montar
   `{campo: índice_coluna}` a partir dos aliases do cabeçalho:
   - pins: `pin_number ← pin/pin no/no./terminal/#/lead`; `name ← name/pin
     name/signal/symbol`; `type ← type/i-o/io/dir/direction`;
     `description ← description/function/definition`.
   - parameters: `symbol ← symbol/parameter`; `name ← characteristic/rating/
     definition/description`; `test_conditions ← test condition(s)/conditions`;
     `min/typ/max ← min/typ/max`; `unit ← unit/units`.
   - **Multi-variante** (várias colunas Min/Typ/Max, TL062 e LM339): pegar o
     **primeiro** grupo Min/Typ/Max (esquerda→direita).

3. **Heurística de conteúdo (fallback sem cabeçalho reconhecível)**:
   - pin_number = coluna cujas células são majoritariamente inteiros de 1–3
     dígitos; entre as candidatas (multi-package TI), escolher a com mais
     células numéricas.
   - description = coluna de texto mais longa; name = coluna de código curto.
   - type = coluna de 1 letra (`I`/`O`/`P`/`I/O`).
   - Mantém TL062 funcionando (regressão), agora sem posição fixa.

4. **Regras de emissão relaxadas**:
   - Não descartar a linha por falta de pin_number: emitir `name`+`description`
     (+`type`) sempre; `pin_number` só quando houver dígito na coluna escolhida.
   - Parâmetros: se houver coluna única `Value` (tabela de máximas/recomendadas),
     mapeá-la para `max` (máximas) ou `typ` (recomendadas), conforme o título da
     seção; `category` inferida do título ("Absolute Maximum Ratings",
     "Recommended Operating Conditions", "Electrical Characteristics", "DC/AC
     Characteristics", "Performance Characteristics", …).
   - Sym+nome juntos na mesma célula (TL062) continuam passando por
     `_split_symbol()`; quando há coluna `symbol` separada, usar direto.

5. **Disparo/varredura** — remover strings exatas; varrer todas as páginas,
   classificar cada tabela e extrair das que casarem. Deduplicar pins por
   `(name, description)` e parâmetros por `(name, test_conditions)` (evita
   repetição de cabeçalho em tabelas que continuam em páginas seguintes).

6. **Manufacturer e package (best-effort, podem ficar vazios)**:
   - Manufacturer: expandir `MANUFACTURERS` (Infineon, onsemi, Diodes, Renesas,
     ROHM, Toshiba, Fairchild, Maxim, Murata, Bourns, KEMET, TDK, Samsung,
     Panasonic, etc.) **+** fallback genérico: `© YYYY <Nome>` e domínio
     (`www.infineon.com`, `www.st.com`, …) no texto.
   - Package/size: varrer o texto por tokens conhecidos (SOIC, SOP, TSSOP,
     SOT-23, QFN, DFN, DIP, PDIP, TO-220, TO-247, LCCC, QFP, BGA, …) e padrões
     "`<N> Lead <pacote>`"; capturar dimensões `X mm × Y mm` quando presentes.

## Arquivos a modificar

- `src/partiu/pdf_extract.py` — reescrita principal (helpers de normalização,
  aliases de cabeçalho, classificador, mapeamento, emissores, `extract()`).
- `README.md` — atualizar a nota "tuned to the Texas Instruments datasheet
  format" para refletir extração genérica + limitação de PDFs escaneados.

## Reuse

- `_clean()`, `_digit()`, `_split_symbol()`, `_detect_manufacturer()` já existem
  em `pdf_extract.py` — manter/adaptar.
- `pdfplumber` (`extract_tables()`, `extract_text()`) — dependência já presente.
- `db.replace_pins/replace_parameters`, `gui/views/detail.py::extract_datasheet`
  — inalterados (schema idêntico).

## Limitação declarada (fora do escopo)

- PDFs **escaneados/imagem** (ex.: `sn74ls161a.pdf`) e números de pino que só
  existem em **diagramas gráficos** (pinouts de `LM339-D`, `infineon-ir2110`)
  não são extraíveis sem OCR/modelo — fora do escopo por decisão do usuário.

## Steps

- [ ] 1. Reescrever helpers de normalização + `HEADER_ALIASES` (pin e parameter).
- [ ] 2. Implementar classificador de tabela (pin vs parameter) usando as 2
      primeiras linhas como cabeçalho.
- [ ] 3. Implementar mapeamento header→coluna com fallback por conteúdo
      (pin_number = coluna mais numérica; multi-variante = primeiro grupo).
- [ ] 4. Reescrever emissores de pins/parameters com regras relaxadas + dedupe.
- [ ] 5. Generalizar `_detect_manufacturer` (lista expandida + padrão ©/domínio)
      e `_extract_package` (tokens + dimensões).
- [ ] 6. Reescrever `extract()` para varrer todas as páginas e classificar.
- [ ] 7. Atualizar nota no `README.md`.
- [ ] 8. Verificação manual com os 4 PDFs (abaixo).

## Verification

Script de conferência (sem abrir a GUI):
```bash
.venv/bin/python -c "from partiu import pdf_extract as p; import json; \
print(json.dumps(p.extract('datasheets/LM339-D.PDF'), indent=2)[:2000])"
```
Esperado por arquivo:

- `tl062.pdf` — ≥ 16 pins (com nº) e ~19 parâmetros (regressão, sem perda).
- `LM339-D.PDF` — parâmetros das seções "Maximum Ratings" + "Electrical
  Characteristics" (+ "Performance"); pins vazios (pinout é imagem).
- `infineon-ir2110…` — parâmetros (máximas + elétricas/dinâmicas) e pins com
  nome+descrição (VDD, HIN, HO, …) sem nº de pino.
- `sn74ls161a.pdf` — vazio/insignificante (escaneado); apenas não deve lançar
  exceção.

End-to-end: `poetry run partiu` → Detalhes de uma parte → Anexar datasheet →
"Extract from datasheet" → conferir pins/parâmetros e que os valores seguem
editáveis.

## Perguntas resolvidas

1. PDFs de exemplo: `datasheets/` ✓
2. Prioridade: pins + parâmetros; manufacturer/package best-effort ✓
3. Sem modelo offline de ML; heurística "extrai o que der" ✓
