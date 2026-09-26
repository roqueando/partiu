# Plan: Lupa (lente circular) na foto do componente

## Context

Na janela de detalhes de um componente, a foto é mostrada só como thumbnail
240×240 (`ttk.Label`) sem ampliação. O usuário quer uma **lupa** para inspecionar
a foto: um botão **"Zoom"** que abre a foto com uma **lente circular** seguindo o
mouse, ampliando a região sob o cursor até **100% (1:1, pixel real)**.

## Decisions (confirmadas)

1. **Lente circular** que segue o mouse (tipo lupa real) — não zoom da imagem inteira.
2. Gatilho: um **botão "Zoom"** (sem duplo-clique).
3. Zoom máximo **travado em 100%**: a lente mostra a região em **1:1** (1 pixel da
   foto = 1 pixel da tela), nunca upscale interpolado.

## Estado atual (verificado em `src/partiu/gui/views/detail.py`)

- `_load_photo()` abre a foto, aplica `thumbnail((240,240))` e exibe via
  `ImageTk.PhotoImage` num `ttk.Label` (`self.photo_label`). **Não guarda** o path
  nem a imagem full-res.
- Path da foto: `self.db.get_attachment(self.part_pk, "photo")` +
  `self.db.attachment_path(att["pk"])`.
- `from PIL import Image, ImageTk` já importado (acrescentar `ImageDraw` p/ máscara).

## Abordagem

1. Novo módulo `src/partiu/gui/photo_viewer.py` com `PhotoViewer(tk.Toplevel)`:
   - Recebe a imagem full-res (PIL `Image`) e um título; `transient(parent)`.
   - `tk.Canvas` mostra a foto **fit-to-window** (escalada para caber, centralizada).
   - **Lente**: no evento `<Motion>`, calcula a coordenada da imagem sob o cursor,
     faz `crop` de uma região quadrada (ex.: 160×160) da imagem full-res, aplica
     **máscara circular** (`ImageDraw` + alpha) e desenha o resultado dentro de um
     círculo na posição do cursor (1:1, sem resize). `<Leave>` esconde a lente.
   - Throttle: só redesenha se o cursor moveu ≥ 2 px (evita lag).
   - Bordas: recorta/clampa a região dentro dos limites da imagem.
2. Em `detail.py`:
   - `_load_photo()` passa a guardar `self._photo_path` (Path) quando há foto (e
     `None` quando não há).
   - Botão **"Zoom"** ao lado de "Add / change photo", desabilitado sem foto
     (atualizado no `_load_photo`), comando `self._open_zoom()`.
   - `_open_zoom()` abre `Image.open(self._photo_path)` full-res e cria o
     `PhotoViewer(self, image, title=f"{name} — photo")`.

## Files to modify

| Arquivo | Mudança |
|---|---|
| `src/partiu/gui/photo_viewer.py` | (novo) `PhotoViewer` com fit-to-window + lente circular 1:1 |
| `src/partiu/gui/views/detail.py` | guardar `_photo_path` + botão "Zoom" + `_open_zoom()` |

## Reuse

- `PIL.Image`, `PIL.ImageDraw`, `PIL.ImageTk` (Pillow já é dependência).
- `self.db.get_attachment(...)` / `self.db.attachment_path(...)` — já usados.
- Padrão de janela `tk.Toplevel` + `transient` (como `PartDetailView`/`FormDialog`).

## Steps

- [ ] 1. Criar `photo_viewer.py`: `PhotoViewer` com canvas, fit-to-window e lente circular 1:1 (crop + máscara + `<Motion>`/`<Leave>`).
- [ ] 2. `detail.py`: guardar `self._photo_path` no `_load_photo()`.
- [ ] 3. `detail.py`: adicionar botão "Zoom" (habilitado só com foto) + `_open_zoom()`.

## Verification

- [ ] Componente **com foto**: "Zoom" habilitado → abre a janela; ao mover o mouse,
      um círculo amplia a região sob o cursor em 1:1 (pixel real, sem blur).
- [ ] Componente **sem foto**: "Zoom" desabilitado.
- [ ] Trocar/remover a foto atualiza o estado do botão e o path.
- [ ] Lente não extrapola as bordas da imagem; sair da imagem esconde a lente.
