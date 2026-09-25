# Plan: Assinatura de código, metadados e instaladores (macOS + Windows)

## Context

O executável do Windows é detectado como vírus pelo Windows Defender. Causa
raiz típica: binário **não assinado** e o formato `--onefile` (self-extracting),
que as heurísticas de AV desconfiam. Objetivo:

1. Gerar **instaladores** com **todos os metadados** (produto, empresa, versão,
   copyright, ícone).
2. Preparar a **assinatura de código** (Windows + macOS) para quando os
   certificados existirem.
3. Empresa = **"fabryk industries"** (tudo minúsculo).

## Decisions (confirmadas)

1. **Sem certificados por enquanto** → os passos de assinatura ficam prontos
   porém **condicionados a secrets** (rodam só quando o cert for adicionado).
   Até lá: metadados + instalador (reduz, mas não elimina 100% o alerta).
2. Nome da empresa **tudo minúsculo**: `fabryk industries`.
3. Windows = **instalador NSIS `.exe`**; macOS = **DMG**. Substituem o portable/zip.
4. Ícones (PNG existentes): Windows `ms-icon-144x144.png` (144×144) → `.ico`;
   macOS `src/apple-icon.png` (192×192) → `.icns` (conversão via Pillow, já dep).
5. Bundle id macOS: `com.fabrykindustries.partiu`.

## Abordagem

### Metadados comuns
- Produto `Partiu`, empresa `fabryk industries`, versão `0.1.0` (ler de
  `pyproject.toml` no workflow), copyright `© 2026 fabryk industries`.

### Windows
1. Converter ícone: `ms-icon-144x144.png` → `partiu.ico` (multi-size, Pillow).
2. Build **`--standalone`** (sem `--onefile`, para evitar o self-extractor que
   mais dispara AV) + `--windows-create-installer` (NSIS) + flags de versão:
   `--company-name="fabryk industries" --product-name="Partiu"`
   `--file-version=$VERSION --product-version=$VERSION`
   `--file-description="Component tracker" --copyright=...`
   `--windows-icon-from-ico=partiu.ico`.
   → saída `Partiu-$VERSION-Setup.exe`.
3. Assinar `.exe` e instalador com **`signtool`** **apenas se** `WINDOWS_SIGNING_CERT`
   existir (step condicional). Sem cert: continua sem assinar.
4. NSIS: instalar via `choco install nsis` (ou auto-download do Nuitka com
   `--assume-yes-for-downloads` — confirmar na execução).

### macOS
1. Converter ícone: `src/apple-icon.png` → `partiu.icns` (Pillow).
2. Build `--standalone --macos-create-app-bundle` + `--macos-create-installer`
   (DMG) + `--macos-app-icon=partiu.icns`
   `--macos-signed-app-name=com.fabrykindustries.partiu`
   `--macos-app-version=$VERSION` + `--company-name/--copyright`.
   → saída `Partiu-$VERSION.dmg`.
3. Assinatura:
   - **Com cert** (secrets): `--macos-sign-identity` + `--macos-sign-notarization`
     + `xcrun notarytool submit` + `stapler staple`.
   - **Sem cert**: assinatura ad-hoc (comportamento atual; Gatekeeper continua
     avisando até ter Developer ID).

### Secrets no GitHub (a adicionar quando houver cert)
- Windows: `WINDOWS_SIGNING_CERT` (base64 .pfx) + `WINDOWS_SIGNING_PASSWORD`.
- macOS: `MACOS_CERTIFICATE` (base64 .p12) + `MACOS_CERTIFICATE_PASSWORD` +
  `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID`.

## Files to modify

| Arquivo | Mudança |
|---|---|
| `.github/workflows/release.yml` | reescrever steps: versão dinâmica, ícones, build standalone+instalador, assinatura condicional, novos artifacts |
| `scripts/make_icons.py` | (novo) converte PNG → `.ico`/`.icns` com Pillow |
| `README.md` | instruções de build/instalação + como habilitar assinatura depois |

## Reuse

- **Pillow** (já é dependência runtime) para gerar `.ico`/`.icns`.
- Flags do **Nuitka 4.2.2** já verificadas: `--company-name`, `--product-name`,
  `--file-version`, `--product-version`, `--file-description`, `--copyright`,
  `--windows-icon-from-ico`, `--windows-create-installer`,
  `--macos-create-installer`, `--macos-app-icon`,
  `--macos-signed-app-name`, `--macos-app-version`, `--macos-sign-identity`,
  `--macos-sign-notarization`.
- Ícones existentes: `ms-icon-144x144.png`, `src/apple-icon.png`.

## Steps

- [ ] 1. Criar `scripts/make_icons.py` (Pillow): gera `partiu.ico` (16–128px) e `partiu.icns` (16–512px).
- [ ] 2. `release.yml`: ler `version` do `pyproject.toml` para `$GITHUB_ENV`.
- [ ] 3. `release.yml` (Windows): gerar `.ico`, build `--standalone` + `--windows-create-installer` + metadados, artefato `Partiu-*-Setup.exe`.
- [ ] 4. `release.yml` (Windows): step condicional de `signtool` (só com secrets).
- [ ] 5. `release.yml` (macOS): gerar `.icns`, build app bundle + DMG + metadados, artefato `Partiu-*.dmg`.
- [ ] 6. `release.yml` (macOS): step condicional de assinatura + notarização + staple (só com secrets).
- [ ] 7. Atualizar matrix de artifacts (Setup.exe / .dmg) e o upload (release + dispatch).
- [ ] 8. `README.md`: documentar instaladores e como ativar assinatura.

## Verification

- [ ] Windows: rodar o workflow (dispatch) → baixar `Partiu-0.1.0-Setup.exe`;
      instalar e abrir; propriedades mostram "fabryk industries", versão e ícone.
- [ ] macOS: baixar o `.dmg`, montar e abrir o app (sem cert: aviso Gatekeeper esperado).
- [ ] `--standalone` (sem onefile) reduz o falso positivo no Defender (não garante sem assinatura).
- [ ] Com secrets de cert presentes no futuro: `signtool verify /pa` no exe e `spctl -a` no app passam.
