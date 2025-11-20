# -*- mode: python ; coding: utf-8 -*-
import os

template_data = []
for root, _, files in os.walk('templates'):
    for f in files:
        full_path = os.path.join(root, f)
        rel_dir = os.path.relpath(root, 'templates')
        target_dir = os.path.join('templates', rel_dir) if rel_dir != '.' else 'templates'
        template_data.append((full_path, target_dir))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=template_data
    + [
        ('icone.ico', '.'),
        ('__logo_cache.png', '.'),
        ('dados_clientes.xlsx', '.'),
        ('dados_financeiro.xlsx', '.'),
        ('dados_orcamentos.xlsx', '.'),
        ('dados_servicos.xlsx', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='app',
)
