# Plan: Gavetas / locais físicos etiquetados para estoque

## Context

O usuário tem **gaveteiros** (armários) e **gavetas** físicas para guardar
componentes. Precisa de um sistema para:

1. **Etiquetar** as gavetas (identificação no app — sem impressão, por ora).
2. **Atribuir** itens de estoque a uma gaveta etiquetada.
3. **Buscar pelo nome** do componente e descobrir **em qual(is) gaveta(s)** ele
   está, para achá-lo fisicamente rápido.

## Decisions (confirmadas com o usuário)

1. **Sem impressão** — etiqueta é só um rótulo/texto no app. Convenção de
   código: gaveteiro = letra (`A`), gaveta = número (`1`), etiqueta resultante
   **`A1`**.
2. **2 níveis** são suficientes: **Gaveteiro → Gaveta** (já suportado por
   `stock_location.parent_id`).
3. **Estoque dividido**: uma mesma peça pode estar em várias gavetas. A busca
   lista **todas as gavetas com a quantidade em cada uma**.

## Abordagem

Reusar 100% o modelo existente — **sem nova tabela, sem migração de schema**:

- `stock_location` (id, name, description, parent_id): gaveteiro = local sem pai
  (ex.: `A`); gaveta = local com pai (ex.: `1`, pai `A`).
- `stock_item.location_id`: já atribui estoque a uma localização (a gaveta).

### Rótulo compacto (etiqueta)

Novo campo derivado **`label`** = concatenação dos `name` na cadeia raiz→folha:
- Gaveta `1` sob gaveteiro `A` → **`A1`**.
- Gaveteiro `A` → `A`.

`pathstring` ("A / 1") continua existindo para leitura longa; `label` ("A1") é o
que aparece na busca/atribuição.

### Mudanças

1. **`db.list_parts()`** passa a agregar, por peça, as gavetas com quantidade:
   `locations: [{label: "A1", quantity: 5}, ...]` (soma por `(part_id, location_id)`).
2. **`PartsView`**: nova coluna **"Locations"** renderizada como `A1 ×5, B2 ×2`.
   A busca por nome já existente então retorna a peça com suas gavetas.
3. **`StockView`**: o combobox de local passa a listar **só gavetas** (locais com
   pai), exibindo o `label` ("A1"); a coluna de local também mostra "A1".
4. **`LocationsView`**: nova coluna **"Label"** ("A1") para conferir as etiquetas.

## Files to modify

| Arquivo | Mudança |
|---|---|
| `src/partiu/db.py` | helper `_location_label()`; `label` em `list_stock_locations()`; `location_label` em `list_stock_items()`; agregação `locations` em `list_parts()` |
| `src/partiu/gui/views/parts.py` | coluna "Locations" + formatação no `fetch()` |
| `src/partiu/gui/views/stock.py` | combobox (só gavetas, por `label`) + coluna `location_label` |
| `src/partiu/gui/views/locations.py` | coluna "Label" |
| `README.md` | documentar convenção de nomenclatura (letra + número) e o fluxo |

## Reuse

- `db._location_path()` / `db.list_stock_locations()` — já calculam a cadeia
  pai→filho (base para derivar `label`).
- `db._fmt_qty()` — formatação de quantidade.
- `DataTable`, `SearchBar`, `CrudView`, `FieldSpec` em `gui/widgets.py` e
  `gui/views/base.py`.

## Steps

- [ ] 1. `db.py`: adicionar `_location_label(locations, pk)` (concatena `name` raiz→folha).
- [ ] 2. `db.py`: `list_stock_locations()` retorna `label` (junto de `pathstring`).
- [ ] 3. `db.py`: `list_stock_items()` retorna `location_label` (via mapa de locais) além de `location_name`.
- [ ] 4. `db.py`: `list_parts()` agrega `locations` por peça (SUM por gaveta), com `label` + `quantity`.
- [ ] 5. `parts.py`: coluna `("locations", "Locations", ...)` e `fetch()` formata "A1 ×5".
- [ ] 6. `stock.py`: combobox filtra gavetas (parent não-nulo) e usa `label`; coluna usa `location_label`.
- [ ] 7. `locations.py`: adicionar coluna `("label", "Label", ...)`.
- [ ] 8. `README.md`: documentar convenção (gaveteiro = letra, gaveta = número) e como buscar.

## Verification

- [ ] Criar gaveteiro `A` e gavetas `1`, `2`; criar uma peça e dois stock items
      da mesma peça: um em `A1` (qtd 3) e outro em `B2` (qtd 2).
- [ ] Buscar o nome da peça em **Parts** → a coluna Locations mostra `A1 ×3, B2 ×2`.
- [ ] Em **Stock Items**, o combobox de local mostra `A1`/`B2` (não "1"/"2"), e a
      coluna Location mostra `A1`.
- [ ] Em **Stock Locations**, a coluna Label mostra `A1`.
- [ ] Confirmar que não houve migração de schema (banco existente continua válido).
