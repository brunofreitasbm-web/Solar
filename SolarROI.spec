# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata, collect_submodules

project_dir = Path.cwd()

# Coleta de dados estáticos e metadados de pacotes
datas = []
datas += collect_data_files("streamlit")
datas += copy_metadata("streamlit")
datas += collect_data_files("plotly")
datas += collect_data_files("altair")
datas += collect_data_files("pydeck")
datas += collect_data_files("reportlab")
datas += copy_metadata("reportlab")
datas += collect_data_files("pdfplumber")

# Arquivos do projeto necessários em tempo de execução
datas += [
    ("app.py", "."),
    ("paginas", "paginas"),
    ("solar", "solar"),
    ("assets", "assets"),
    (".streamlit", ".streamlit"),
]

# Inclui banco inicial se existir
db_template = project_dir / "data" / "solar.db"
if db_template.exists():
    datas.append((str(db_template), "data"))

# Submódulos ocultos
hiddenimports = []
hiddenimports += collect_submodules("solar")
hiddenimports += collect_submodules("paginas")
hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("reportlab")
hiddenimports += collect_submodules("pdfplumber")
hiddenimports += [
    "anthropic",
    "openpyxl",
    "numpy_financial",
    "cv2",
    "dotenv",
    "sqlite3",
    "multiprocessing",
]

block_cipher = None

a = Analysis(
    ["run_app.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "playwright"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SolarROI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "assets" / "icone.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SolarROI",
)
