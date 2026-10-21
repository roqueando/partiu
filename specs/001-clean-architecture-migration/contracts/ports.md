# Port Contracts (application ↔ adapters)

**Feature**: 001-clean-architecture-migration | **Date**: 2026-10-20

These are the interfaces the application layer depends on (declared as
`typing.Protocol` in `application/ports.py`). Adapters implement them; unit tests use
fakes. All inputs/outputs are expressed in domain terms (`data-model.md`), never in
storage or document formats.

> Method signatures below are the contract shape; exact Python annotations live in
> `application/ports.py` during implementation.

## PartRepository

| Method | Input | Output |
|--------|-------|--------|
| `list_parts(search)` | optional free text + location tokens | list of `Part` with derived `in_stock` and `locations` |
| `get_part(pk)` | part id | `Part` or `None` |
| `create_part(data)` | `Part` fields | created part id |
| `update_part(pk, data)` | part id + fields | updated part id |
| `delete_part(pk)` | part id | — (removes attachments too) |
| `import_parts(rows)` | list of rows | `{created, skipped, duplicates}` (atomic; name dedupe) |

## StockRepository

| Method | Input | Output |
|--------|-------|--------|
| `list_stock_items(search)` | optional text | list of stock items with part/location labels |
| `create/update/delete_stock_item(...)` | fields / id | id / — |
| `set_stock_items_location(pks, location_id)` | ids + location | — |
| `list_stock_locations(search)` | optional text | locations with label/path/item counts |
| `create/update/delete_stock_location(...)` | fields / id | id / — |

## RepairRepository

| Method | Input | Output |
|--------|-------|--------|
| `list_repair_projects()` | — | list of projects |
| `get/create/update/delete_repair_project(...)` | fields / id | id / — |
| `add_repair_photo(project_id, source_path)` | id + file path | photo id (copies file) |
| `list_repair_photos(project_id)` / `delete_repair_photo(pk)` | id | list / — |
| `list_repair_annotations(project_id)` | id | findings joined with linked part name/ipn |
| `replace_repair_annotations(project_id, rows)` | id + finding rows | — (atomic) |

## AttachmentStore

| Method | Input | Output |
|--------|-------|--------|
| `list_attachments(part_id)` | part id | attachments |
| `set_attachment(part_id, kind, source_path)` | id + kind + file path | attachment id (replaces same-kind) |
| `delete_attachment(pk)` | attachment id | — |
| `get_attachment(part_id, kind)` | id + kind | attachment or `None` |
| `attachment_path(pk)` | attachment id | file path or `None` |

## DatasheetExtractor

| Method | Input | Output |
|--------|-------|--------|
| `extract(path, part_name, part_ipn)` | PDF path + hints | `ExtractedDatasheet` (manufacturer, package, package_size, pins, parameters) |

`ocr_extract` exposes the same `extract` contract for scanned (no text layer) PDFs.

## PartsImporter

| Method | Input | Output |
|--------|-------|--------|
| `read(source_path)` | CSV/XLSX path | normalized rows (headers matched by name) |
| `write_template(destination)` | path | — (writes a ready-to-fill CSV) |

## SettingsStore

| Method | Input | Output |
|--------|-------|--------|
| `get(key, default)` | key | stored value |
| `set(key, value)` | key + value | — (persists) |

## CameraCapturer

| Method | Input | Output |
|--------|-------|--------|
| `list_cameras()` | — | list of `(index, label)` |
| `open(index)` / `close()` / `read_frame()` | index | frame or `None` |
| `capture_frame(index)` | index | image saved to a temp path (or `None`) |

## Boundary rules

- The application layer imports only `domain/` and these ports.
- Adapters translate their native formats (SQL rows, PDF pages, spreadsheet cells,
  cv2 frames) into the domain objects above **at the boundary**; no raw format leaks
  through a port.
- The composition root (`main.py`) is the only place that binds concrete adapters to
  these ports.
