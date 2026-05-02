# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


SPEC_DIR = Path(SPEC).resolve().parent
AWAKENING_DIR = SPEC_DIR.parent / 'external' / 'awakening_system'

a = Analysis(
    ['app\\main.py'],
    pathex=[str(SPEC_DIR), str(AWAKENING_DIR / 'scripts')],
    binaries=[],
    datas=[
        (str(SPEC_DIR / 'app'), 'app'),
        (str(AWAKENING_DIR / 'scripts'), 'external/awakening_system/scripts'),
    ],
    hiddenimports=[
        'numpy',
        'numpy._core',
        'numpy._core.multiarray',
        'numpy.core',
        'pandas',
        'pydantic',
        'MetaTrader5',
        'gold_analysis',
        'wave_analysis',
        'elliott_wave',
        'pa_wave_fusion',
        'smc_snapshot',
        'scenario_playbook',
        'institutional_render',
        'economic_calendar',
    ],
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
    [],
    exclude_binaries=True,
    name='mt5_service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    upx_exclude=[],
    name='mt5_service',
)
