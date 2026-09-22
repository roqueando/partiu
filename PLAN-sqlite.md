# Plan: Partiu sem InvenTree — SQLite puro + tkinter

## Contexto

O protótipo atual empacota o **servidor InvenTree inteiro** (Django + ~200 pacotes + WeasyPrint/Pango) só para usar CRUD de 3 entidades. Isso tornou o app pesado (318 MB), o empacotamento complexo e o startup lento.

**Decisão:** remover 100% do InvenTree. Manter o **mesmo GUI tkinter** (Parts, Stock Items, Stock Locations + busca + export), trocando a camada de dados por **SQLite puro (stdlib `sqlite3`)**. Objetivo: **track básico de componentes**, app leve (~35 MB), zero dependências externas, empacotamento trivial.

## Arquitetura alvo

```
Partiu (tkinter, single process)
├── gui/            (reutilizado, quase idêntico)
│   ├── app.py      (janela + navegação + export)
│   ├── widgets.py  (tabela, busca, form)
│   └── views/      (parts, stock, locations)
├── db.py           (NOVO — schema + CRUD via sqlite3)
├── paths.py        (dir de dados do usuário, sem platformdirs)
├── config.py       (só UserSettings JSON)
└── main.py         (abre o banco + GUI, sem servidor)
```

Remove: `server.py`, `inventree_client.py`, `vendor/inventree/`, waitress/Django/inventree, libs nativas.

## Schema (track básico de componentes)

```sql
part_category (
  id, name, parent_id → part_category (SET NULL)
)
part (
  id, name NOT NULL, ipn, description,
  category_id → part_category (SET NULL),
  units, active INTEGER DEFAULT 1, created_at
)
stock_location (
  id, name NOT NULL, description,
  parent_id → stock_location (SET NULL)
)
stock_item (
  id, part_id → part (CASCADE), quantity REAL DEFAULT 0,
  location_id → stock_location (SET NULL),
  serial, batch, status TEXT DEFAULT 'OK', created_at
)
```

Status como texto simples: `OK`, `Attention needed`, `Damaged`, `Destroyed`, `Rejected`, `Lost`, `Quarantined`, `Returned`.

## O que muda por arquivo

| Arquivo | Ação |
|---|---|
| `src/partiu/db.py` | **CRIAR** — classe `Database` (connect, init schema, CRUD) expondo os MESMOS métodos que o client antigo: `list_parts/search`, `create/update/delete_part`, `list_part_categories`, `list_stock_items`, `list_stock_locations`, `create/update/delete_stock_item`, `create/update/delete_stock_location` |
| `src/partiu/paths.py` | **SIMPLIFICAR** — helper de data-dir puro (macOS/Windows/Linux) via `Path.home()`; remover `get_inventree_backend_dir` |
| `src/partiu/config.py` | **SIMPLIFICAR** — manter só `UserSettings`; remover geração de `config.yaml` e `DEFAULT_ADMIN_*` |
| `src/partiu/main.py` | **SIMPLIFICAR** — sem `server.*`; abre `Database`, cria `PartiuApp(db=...)` |
| `src/partiu/gui/app.py` | **AJUSTAR** — `client`→`db`; export agora exporta `partiu.db` |
| `src/partiu/gui/views/base.py` | **AJUSTAR** — `self.client`→`self.db` |
| `src/partiu/gui/views/parts.py` | **AJUSTAR** — mapear `category_name`, `in_stock` via JOIN/SUM |
| `src/partiu/gui/views/stock.py` | **AJUSTAR** — `part_name`/`location_name` via JOIN, `status_text` = status |
| `src/partiu/gui/views/locations.py` | **AJUSTAR** — `pathstring` calculado, `items`/`sublocations` via COUNT |
| `pyproject.toml` | **SIMPLIFICAR** — remover deps runtime (só stdlib); manter `pyinstaller` no grupo dev |
| `build/partiu.spec` | **SIMPLIFICAR** — sem `collect_all`, sem `Tree`, sem native libs |
| `src/partiu/server.py` | **DELETAR** |
| `src/partiu/inventree_client.py` | **DELETAR** |
| `vendor/inventree/` | **DELETAR** |
| `build/collect_native_libs.py` + `build/native_libs/` | **DELETAR** |

## Reuso (o que NÃO muda)

- `gui/widgets.py` — `DataTable`, `SearchBar`, `FormDialog` (intocados).
- Estrutura e visual das 3 views (colunas, formulários, botões) — só trocam a fonte de dados.
- `run.py` (entry point do PyInstaller) — continua apontando para `partiu.main:main`.

## Passos

1. Criar `db.py` com schema + CRUD (retornando dicts com as mesmas chaves que as views esperam).
2. Simplificar `paths.py`, `config.py`, `main.py`.
3. Trocar `client`→`db` nas views e ajustar mapeamentos de colunas.
4. Remover `server.py`, `inventree_client.py`, `vendor/inventree`, libs nativas, e limpar `pyproject.toml`.
5. Rodar `PYTHONPATH=src .venv/bin/python -m partiu` e testar CRUD + busca + export.
6. Simplificar `build/partiu.spec` e gerar o `.app` leve (verificar ~35 MB e que abre).

## Verificação

- **CRUD**: criar/editar/excluir Part, Stock Item e Location pelo GUI; busca filtra.
- **Persistência**: fechar e reabrir o app → dados continuam.
- **Export**: botão "Export database…" copia `partiu.db` para o destino.
- **Empacotamento**: `pyinstaller build/partiu.spec` → `dist/Partiu.app` abre sem Python instalado, sem libs nativas e com tamanho ~35 MB.

## Resultado esperado

| | Antes (InvenTree) | Depois (SQLite puro) |
|---|---|---|
| Tamanho do app | ~318 MB | **~35 MB** |
| Dependências runtime | ~200 | **0 (stdlib)** |
| Empacotamento | complexo | **trivial** |
| Startup | lento (migrate/checks) | **instantâneo** |
| Features | BOM/ordens/etc. | só track básico (escopo atual) |
