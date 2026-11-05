# -*- mode: python ; coding: utf-8 -*-
import os

# 使用 SPECPATH（spec 文件所在目录）拼出绝对路径，
# 避免从其他工作目录执行打包时 icon/datas 相对路径失效导致图标丢失
ICON_PATH = os.path.join(SPECPATH, "resources", "icon.ico")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(ICON_PATH, 'resources/')],
    hiddenimports=['pandas', 'openpyxl', 'chardet', 'PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='资金数据清洗工具',
    icon=ICON_PATH,
    debug=False,
    strip=True,
    upx=True,
    console=False,
    windowed=True,
)
