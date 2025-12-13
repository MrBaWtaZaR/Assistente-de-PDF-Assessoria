
import sys
import os
import flet as ft

# Adiciona o diretório 'src' ao PATH para permitir imports corretos
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from frontend.main_v2 import main

if __name__ == "__main__":
    ft.app(target=main)
