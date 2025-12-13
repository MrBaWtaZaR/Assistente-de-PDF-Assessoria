
import flet as ft
import os
import time
import threading
from backend.pdf_processor import PdfProcessor

def main(page: ft.Page):
    page.title = "Editor de Catálogo PDF v2.0"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 10
    page.window_width = 900 # Mais largo para o grid
    page.window_height = 800
    
    # Variáveis de Estado
    pdf_path = ft.Ref[str]()
    logo_path = ft.Ref[str]()
    output_temp_path = ft.Ref[str]()
    
    # Configs V2
    markup_value = ft.Ref[ft.TextField]()
    catalog_name_input = ft.Ref[ft.TextField]()
    chk_add_cover = ft.Ref[ft.Checkbox]()
    chk_add_intro = ft.Ref[ft.Checkbox]()
    
    # Lista de páginas para excluir (índices)
    pages_to_delete = set()
    
    processor = PdfProcessor()
    
    # Elementos UI
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[],
        expand=True
    )
    
    grid_pages = ft.GridView(
        expand=True,
        max_extent=160,
        child_aspect_ratio=0.7,
        spacing=10,
        run_spacing=10,
    )

    # --- Funções Lógicas ---

    def toggle_page_delete(e, page_idx):
        if e.control.value:
            pages_to_delete.add(page_idx)
        else:
            pages_to_delete.discard(page_idx)
        update_status_text()

    def update_status_text():
        lbl_page_count.value = f"Páginas Selecionadas para Remoção: {len(pages_to_delete)}"
        lbl_page_count.update()

    def load_pdf_pages(path):
        grid_pages.controls.clear()
        grid_pages.controls.append(ft.Text("Carregando miniaturas...", size=16))
        grid_pages.update()
        
        # Gerar thumbs em thread para não travar
        def _load():
            thumbs = processor.get_thumbnails(path)
            grid_pages.controls.clear()
            
            for i, thumb in enumerate(thumbs):
                # Container da Página
                # Checkbox de "Deletar"
                chk = ft.Checkbox(label=f"Pág {i+1}", on_change=lambda e, idx=i: toggle_page_delete(e, idx), fill_color="red")
                
                img = ft.Image(src=thumb, fit=ft.ImageFit.CONTAIN, border_radius=5)
                
                # Card visual
                card = ft.Container(
                    content=ft.Column([
                        ft.Container(img, expand=True), # Imagem ocupa espaço
                        ft.Container(chk, bgcolor="#ffeeee", padding=5, border_radius=5) # Footer com checkbox
                    ], spacing=2),
                    padding=5,
                    bgcolor="white",
                    border=ft.border.all(1, "#eeeeee"),
                    border_radius=8,
                    shadow=ft.BoxShadow(blur_radius=5, color="#10000000")
                )
                grid_pages.controls.append(card)
            
            grid_pages.update()
            # Mudar para aba de páginas se estiver na 0
            tabs.selected_index = 0
            tabs.update()
            
        t = threading.Thread(target=_load, daemon=True)
        t.start()

    def on_pdf_picked(e):
        if e.files:
            path = e.files[0].path
            pdf_path.current = path
            txt_pdf_name.value = os.path.basename(path)
            txt_pdf_name.update()
            # Resetar
            pages_to_delete.clear()
            load_pdf_pages(path)
            btn_next_1.disabled = False
            btn_next_1.update()

    def process_click(e):
        if not pdf_path.current: return

        try:
            markup = float(markup_value.current.value.replace(",", "."))
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Preço inválido"))
            page.snack_bar.open = True
            page.update()
            return
            
        # UI travada
        btn_process.disabled = True
        btn_process.text = "PROCESSANDO (V2)..."
        pb_prod.visible = True
        pb_prod.value = 0
        page.update()
        
        # Paths
        import tempfile
        filename = f"v2_processed_{int(time.time())}.pdf"
        out_path = os.path.join(tempfile.gettempdir(), filename)
        
        def _run():
            def cb(p):
                pb_prod.value = p
                pb_prod.update()
                
            success, msg = processor.process_catalog_v2(
                input_path=pdf_path.current,
                output_path=out_path,
                price_markup=markup,
                logo_path=logo_path.current,
                pages_to_exclude=list(pages_to_delete),
                add_cover=chk_add_cover.current.value,
                add_intro=chk_add_intro.current.value,
                catalog_name=catalog_name_input.current.value,
                progress_callback=cb
            )
            
            pb_prod.value = 1.0
            pb_prod.update()
            
            # Resultado UI
            btn_process.disabled = False
            btn_process.text = "PROCESSAR NOVAMENTE"
            pb_prod.visible = False
            
            if success:
                output_temp_path.current = out_path
                col_result.visible = True
                txt_result_msg.value = msg
            else:
                col_result.visible = False
                page.dialog = ft.AlertDialog(title=ft.Text("Erro"), content=ft.Text(msg))
                page.dialog.open = True
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    # --- Componentes UI ---
    
    # Tab 1: Seleção
    txt_pdf_name = ft.Text("Selecione um PDF...")
    lbl_page_count = ft.Text("Páginas Selecionadas para Remoção: 0", color="red")
    btn_next_1 = ft.ElevatedButton("Próximo: Personalizar >", on_click=lambda _: setattr(tabs, 'selected_index', 1) or tabs.update(), disabled=True)
    
    picker_pdf = ft.FilePicker(on_result=on_pdf_picked)
    page.overlay.append(picker_pdf)
    
    tab1_content = ft.Column([
        ft.Row([
            ft.ElevatedButton("Carregar PDF", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: picker_pdf.pick_files(allow_multiple=False, allowed_extensions=["pdf"])),
            txt_pdf_name,
            ft.Container(expand=True),
            lbl_page_count,
            btn_next_1
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        ft.Container(grid_pages, expand=True, bgcolor="#f9f9f9", padding=10, border_radius=10)
    ], expand=True)

    # Tab 2: Config V2
    picker_logo = ft.FilePicker(on_result=lambda e: [setattr(logo_path, 'current', e.files[0].path), setattr(img_logo.src, e.files[0].path), img_logo.update()] if e.files else None)
    page.overlay.append(picker_logo)
    
    img_logo = ft.Image(width=100, height=100, fit=ft.ImageFit.CONTAIN, src="")
    catalog_name_input = ft.Ref[ft.TextField]()
    chk_add_cover = ft.Ref[ft.Checkbox]()
    chk_add_intro = ft.Ref[ft.Checkbox]()
    
    tab2_content = ft.Container(
        content=ft.Column([
            ft.Text("Identidade Visual", size=20, weight="bold"),
            ft.Row([
                ft.ElevatedButton("Upload Logo", icon=ft.Icons.IMAGE, on_click=lambda _: picker_logo.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg"])),
                img_logo
            ]),
            ft.Divider(),
            ft.Text("Estrutura do Catálogo", size=20, weight="bold"),
            ft.Checkbox(ref=chk_add_cover, label="Criar Nova Capa (Logo Centralizada)", value=True),
            ft.Checkbox(ref=chk_add_intro, label="Criar Página de Apresentação (Nome + Data)", value=True),
            ft.TextField(ref=catalog_name_input, label="Nome do Catálogo", hint_text="Ex: Coleção Verão 2025"),
            ft.Container(height=20),
            ft.ElevatedButton("Próximo: Preços e Finalizar >", on_click=lambda _: setattr(tabs, 'selected_index', 2) or tabs.update())
        ], scroll=ft.ScrollMode.AUTO),
        padding=20
    )

    # Tab 3: Processar
    pb_prod = ft.ProgressBar(width=400, visible=False)
    col_result = ft.Column([
        ft.Text("Sucesso!", color="green", size=20, weight="bold"),
        ft.Text("", ref=ft.Ref[ft.Text](), color="green"), # msg placeholder
        ft.Row([
            ft.ElevatedButton("Visualizar", on_click=lambda _: os.startfile(output_temp_path.current)),
            ft.ElevatedButton("Salvar Como...", on_click=lambda _: picker_save.save_file(file_name="novo_catalogo.pdf"))
        ])
    ], visible=False)
    txt_result_msg = col_result.controls[1]
    
    picker_save = ft.FilePicker(on_result=lambda e: [import_shutil(output_temp_path.current, e.path), page.snack_bar.open_true()] if e.path else None)
    # Helper auxiliar pra lambda acima nao ficar complexa demais, mas deixarei simples
    def save_final(e):
        if e.path:
            import shutil
            shutil.copy2(output_temp_path.current, e.path)
            page.snack_bar = ft.SnackBar(ft.Text("Salvo!"))
            page.snack_bar.open = True
            page.update()
    picker_save.on_result = save_final
    page.overlay.append(picker_save)

    btn_process = ft.ElevatedButton("PROCESSAR CATÁLOGO V2", on_click=process_click, bgcolor="blue", color="white", height=50, width=300)

    tab3_content = ft.Container(
        content=ft.Column([
            ft.Text("Ajuste de Preços", size=20, weight="bold"),
            ft.TextField(ref=markup_value, prefix_text="R$ ", value="20.00", label="Valor a Adicionar", width=200),
            ft.Divider(),
            ft.Text("Resumo", size=20, weight="bold"),
            ft.Text("O sistema irá: 1. Remover páginas selecionadas. 2. Inserir Capas (se marcado). 3. Atualizar preços e logos."),
            ft.Container(height=30),
            pb_prod,
            btn_process,
            col_result
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20
    )

    # Montando Tabs
    tabs.tabs = [
        ft.Tab(text="1. Páginas", content=tab1_content),
        ft.Tab(text="2. Personalização", content=tab2_content),
        ft.Tab(text="3. Finalizar", content=tab3_content),
    ]

    # Rodapé com Créditos
    footer_credits = ft.Container(
        content=ft.Row(
            [
                ft.Text("Desenvolvido por Victor William", size=12, color="grey"),
                ft.Text(" | ", size=12, color="grey"),
                ft.Text("GitHub", size=12, color="blue", spans=[ft.TextSpan("", url="https://github.com/MrBaWtaZaR")])
            ],
            alignment=ft.MainAxisAlignment.CENTER
        ),
        padding=5
    )

    # Adicionando Tabs e Footer
    # Usando Column para garantir que o footer fique no fim (se tabs tiver expand, ele empurra)
    # Mas como page.add já empilha, e tabs tem expand=True... 
    # Melhor estrutura: Column([tabs, footer]) com expand.
    
    layout = ft.Column([
        tabs,
        footer_credits
    ], expand=True)

    page.add(layout)

if __name__ == "__main__":
    ft.app(target=main)
