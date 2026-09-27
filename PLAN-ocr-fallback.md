# PLAN — OCR fallback para extração de datasheet

## Context

A extração heurística (`src/partiu/pdf_extract.py`) cobre bem PDFs com camada de
texto, mas falha em:

- PDFs **escaneados** (ex.: `datasheets/sn74ls161a.pdf` — só header/rodapé têm texto).
- **Números de pino** que existem apenas em **diagramas gráficos** (ex.:
  `infineon-ir2110` "Lead Assignments", pinout do `LM339-D`).

Objetivo: adicionar **OCR local como fallback** — quando a heurística não achar
nada (ou a página não tiver texto), renderizar a página e extrair com um modelo
de OCR **pequeno e offline**, reaproveitando a mesma camada semântica de
classificação/extração já existente. Nada de cloud.

## Fatos levantados (relevantes para a decisão)

- Python do projeto: **3.14.7** (`pyproject` permite `>=3.11,<3.16`).
- `pypdfium2 5.13.0` já está instalado (dependência do pdfplumber) → **renderizar
  página para PNG já é possível** sem dependência nova.
- `onnxruntime`: suporta Python 3.14 a partir da **1.24** (atual 1.28.0). ✓
- `rapidocr-onnxruntime` 1.4.4 **não** instala no 3.14 (`requires_python <3.13`).
  O pacote unificado **`rapidocr` (v3.x, Apache-2.0)** suporta `>=3.8,<4` e roda
  os modelos **PP-OCRv4/v5/v6 em ONNX via onnxruntime** (CPU). É a opção certa.
- `rapidocr` baixa os modelos **on-demand** na primeira execução (URLs do
  ModelScope, com SHA256 pinado em `default_models.yaml`) → para ser offline é
  preciso **pré-baixar det+rec+cls (.onnx) + dicts** e apontar para paths locais.

## Abordagem

### Motor de OCR escolhido

`rapidocr` (unificado) + `onnxruntime`, modelos **PP-OCRv4 mobile**
(~15–30 MB total, ~200 ms–1 s/página em CPU).

Por que não:
- **Tesseract**: binário externo + dados de idioma, acurácia pior em diagramas
  densos e empacotar no Nuitka é mais frágil.
- **PaddleOCR/EasyOCR**: trazem PaddlePaddle/torch → binário +400 MB.
- **LLM/VLM local**: overkill para OCR puro (e o diagrama de pinos exige visão,
  não texto).

### Fluxo fallback

```
1. Heurística atual (text layer) roda primeiro — caminho rápido, determinístico.
2. Decide se precisa de OCR:
   - página com ~0 chars de texto e conteúdo renderizável, OU
   - resultado heurístico vazio (pins=[] e params=[]), OU
   - pins=[] mas existe seção de pinout/diagrama.
3. Renderiza as páginas necessárias com pypdfium2 (200–300 DPI, escala para
   textos pequenos).
4. OCR (rapidocr/onnxruntime) → linhas de texto + bounding boxes + confiança.
5. Reconstrói "tabelas" agrupando palavras por linha (y) e coluna (gaps de x),
   e reusa `_scan_headers` + emissores atuais → mesmo dict de saída.
6. Diagrama gráfico de pinos (opcional, fase 2): parser geométrico que casa
   rótulos numéricos com rótulos de nome próximos (por distância/posição).
```

O contrato de saída continua idêntico → `detail.py`/`db.py` inalterados (fora o
ponto de chamada do fallback).

## Arquivos a modificar

- `src/partiu/ocr_extract.py` — **novo**: renderização (pypdfium2), wrapper
  rapidocr, reconstrução de tabelas a partir de boxes, orquestração do fallback.
- `src/partiu/pdf_extract.py` — expor internos reutilizáveis (`_scan_headers`,
  `_header_rows`, `_extract_pins`, `_extract_parameters`, `_section_title`) para
  o módulo OCR (hoje são privados; sem mudança de comportamento).
- `src/partiu/gui/views/detail.py` — no `extract_datasheet`, tentar heurística e,
  se vazio, acionar `ocr_extract.extract(...)`; rodar em **thread** (OCR demora).
- `pyproject.toml` — adicionar `rapidocr` + `onnxruntime>=1.24` (+ `opencv-python`
  via rapidocr; avaliar `opencv-python-headless` para reduzir footprint).
- `README.md` — documentar fallback OCR, modelos locais e flags do Nuitka.
- `scripts/` — (opcional) script para **pré-baixar e fixar** os modelos OCR.

## Reuse

- `_scan_headers`, `_header_rows`, `_extract_pins`, `_extract_parameters`,
  `_section_title`, aliases e emissores em `pdf_extract.py` — a camada semântica
  não muda; o OCR só fornece "palavras+posições" no lugar do `extract_tables()`.
- `pypdfium2` (já presente) para renderizar páginas.
- `db.replace_pins/replace_parameters` e a UI de edição — inalterados.

## Bundling offline (crítico)

- Pré-baixar `ch_PP-OCRv4_det_mobile.onnx`, `ch_PP-OCRv4_rec_mobile.onnx`,
  `ch_ppocr_mobile_v2.0_cls.onnx` e dicts; **pinar versão + SHA256**
  (do `default_models.yaml` do rapidocr).
- Apontar paths locais via params do rapidocr (`Det.model_path`,
  `Rec.model_path`, `Cls.model_path`) — sem download em runtime.
- Nuitka: `--include-package=onnxruntime --include-package=rapidocr
  --include-package=cv2` + `--include-package-data` (ou copiar `models/` para
  junto do binário e resolver o path em runtime via `paths.py`).

## Steps

- [ ] 1. Adicionar deps (`rapidocr`, `onnxruntime>=1.24`) e validar instalação
      no Python 3.14.
- [ ] 2. Baixar/pinar modelos PP-OCRv4 mobile (det/rec/cls + dict) com SHA256.
- [ ] 3. Criar `ocr_extract.py`: render com pypdfium2 + wrapper rapidocr com
      paths locais.
- [ ] 4. Reconstrução de tabelas: agrupar OCR words → linhas (y) → colunas (x),
      gerando `list[list[str]]` compatível com os emissores atuais.
- [ ] 5. Orquestrar fallback e integrar no `extract_datasheet` (heurística →
      OCR se vazio), em thread para não travar a GUI.
- [ ] 6. Parser geométrico de pinout (fase 2, opcional).
- [ ] 7. Atualizar `README.md` (build Nuitka + modelos) e script de download.
- [ ] 8. Verificação com `sn74ls161a.pdf` (escaneado) e `infineon-ir2110`
      (pinout gráfico).

## Verification

- `sn74ls161a.pdf` (escaneado): após OCR, espera-se extrair pins/parâmetros das
  tabelas (antes: 0/0).
- `infineon-ir2110` (pinout gráfico): espera-se nº de pino + nome (antes: nome
  sem nº).
- Regressão: `tl062.pdf`, `LM339-D.PDF` continuam iguais (heurística não muda e
  OCR só dispara quando ela falha).
- Conferência: `poetry run partiu` → anexar PDF escaneado → "Extract from
  datasheet" → conferir que a UI não trava durante o OCR.

## Riscos / limitações

- **Tamanho do binário**: onnxruntime (~50–150 MB) + opencv (~60–100 MB) +
  modelos (~30 MB) → +150–250 MB por plataforma no build Nuitka.
- **Latência**: OCR em CPU é ~200 ms–1 s/página; datasheet de 40 páginas pode
  levar 10–40 s → rodar em background com indicador de progresso.
- **Reconstrução de tabela** a partir de boxes é a parte mais incerta (bordas de
  célula invisíveis no OCR); tabelas escaneadas complexas podem sair imperfeitas
  — segue editável.
- **opencv-python** vs **headless**: validar se rapidocr funciona com
  `opencv-python-headless` (menor e sem libs de GUI).
