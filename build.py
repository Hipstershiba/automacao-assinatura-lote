#!/usr/bin/env python3
"""
Script de build para gerar executável único com PyInstaller (modo --onedir).

Uso:
    python build.py

O executável é gerado em ./dist/ — modo onedir (mais rápido que onefile).

Requisitos:
    pip install -r requirements.txt
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / 'dist'
BUILD_DIR = BASE_DIR / 'build'

# Dependências ocultas que o PyInstaller nem sempre detecta automaticamente
HIDDEN_IMPORTS = [
    'selenium',
    'selenium.webdriver.edge.webdriver',
    'selenium.webdriver.edge.options',
    'selenium.webdriver.edge.service',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.cell',
    'openpyxl.worksheet',
    'yaml',
    'requests',
    'src.servidor_mock',
    'src.dimensa_mock',
    'src.dimensa_client',
    'src.contrato',
    'src.gerador_relatorio',
    'certifi',
    'charset_normalizer',
]

# Dados adicionais necessários em tempo de execução (src/ + config)
DATAS = [
    (str(BASE_DIR / 'config.yaml.example'), '.'),
    (str(BASE_DIR / 'src'), 'src'),
]


def build():
    """Gera executável único para o app completo (app.py + src.assinatura)."""
    print('=' * 60)
    print('  Build: assinatura-lote (app.py + módulos)')
    print('=' * 60)

    # Limpa builds anteriores
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)

    output_name = 'assinatura-lote'

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onedir',                          # modo diretório (rápido de abrir)
        '--name', output_name,
        '--distpath', str(DIST_DIR),
        '--workpath', str(BUILD_DIR),
        '--specpath', str(BUILD_DIR),
        '--noconfirm',
        '--clean',
    ]

    for imp in HIDDEN_IMPORTS:
        cmd.append(f'--hidden-import={imp}')

    for src, dst in DATAS:
        cmd.append(f'--add-data={src}:{dst}')

    cmd.append(str(BASE_DIR / 'app.py'))

    print(f'Executando PyInstaller...')
    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode == 0:
        print()
        print('✓ Build concluído com sucesso!')
        if sys.platform == 'win32':
            print(f'  Executável: {DIST_DIR / output_name / f"{output_name}.exe"}')
        else:
            print(f'  Executável: {DIST_DIR / output_name / output_name}')
    else:
        print(f'✗ Build falhou com código {result.returncode}')

    return result.returncode


if __name__ == '__main__':
    sys.exit(build())