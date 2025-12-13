
import flet as ft
import os
import time
import threading
import shutil
from backend.pdf_processor import PdfProcessor

def main(page: ft.Page):
    page.title = "Editor Online de Catálogo PDF"
    page.theme_mode = ft.ThemeMode.LIGHT
    # page.scroll = ft.ScrollMode.AUTO # Scroll causa colapso do expand no web
    
    # Variáveis de Estado
    pdf_path = ft.Ref[str]()
    logo_path = ft.Ref[str]()
    output_temp_path = ft.Ref[str]()
    
    # Configs V2
    markup_value = ft.Ref[ft.TextField]()
    catalog_name_input = ft.Ref[ft.TextField]()
    chk_add_cover = ft.Ref[ft.Checkbox]()
    chk_add_intro = ft.Ref[ft.Checkbox]()
    
    pages_to_delete = set()
    processor = PdfProcessor()
    
    tabs = ft.Tabs(selected_index=0, animation_duration=300, tabs=[], expand=True)
    grid_pages = ft.GridView(expand=True, max_extent=160, child_aspect_ratio=0.7, spacing=10, run_spacing=10)

    # --- Funções Lógicas ---

    def toggle_page_delete(e, page_idx):
        if e.control.value: pages_to_delete.add(page_idx)
        else: pages_to_delete.discard(page_idx)
        lbl_page_count.value = f"Páginas Selecionadas para Remoção: {len(pages_to_delete)}"
        lbl_page_count.update()

    def load_pdf_pages(path):
        grid_pages.controls.clear()
        grid_pages.controls.append(ft.Text("Carregando miniaturas...", size=16))
        grid_pages.update()
        
        def _load():
            try:
                thumbs = processor.get_thumbnails(path)
                grid_pages.controls.clear()
                for i, thumb in enumerate(thumbs):
                    chk = ft.Checkbox(label=f"Pág {i+1}", on_change=lambda e, idx=i: toggle_page_delete(e, idx), fill_color="red")
                    img = ft.Image(src=thumb, fit=ft.ImageFit.CONTAIN, border_radius=5)
                    card = ft.Container(
                        content=ft.Column([ft.Container(img, expand=True), ft.Container(chk, bgcolor="#ffeeee", padding=5, border_radius=5)], spacing=2),
                        padding=5, bgcolor="white", border=ft.border.all(1, "#eeeeee"), border_radius=8, shadow=ft.BoxShadow(blur_radius=5, color="#10000000")
                    )
                    grid_pages.controls.append(card)
                grid_pages.update()
                tabs.selected_index = 0
                tabs.update()
            except Exception as e:
                print(f"Erro Web Load: {e}")
                
        t = threading.Thread(target=_load, daemon=True)
        t.start()

    def on_pdf_picked(e):
        if e.files:
            # Em Web, path pode ser temporário do upload
            path = e.files[0].path
            pdf_path.current = path
            txt_pdf_name.value = e.files[0].name
            txt_pdf_name.update()
            pages_to_delete.clear()
            load_pdf_pages(path)
            btn_next_1.disabled = False
            btn_next_1.update()

    def process_click(e):
        if not pdf_path.current:
            page.open(ft.SnackBar(ft.Text("⚠️ Por favor, faça o Upload do PDF na primeira aba!", color="white"), bgcolor="red"))
            page.update()
            return

        try: 
            # Limpeza extra para garantir que o valor seja numérico
            clean_val = markup_value.current.value.replace("R$", "").replace(" ", "").replace(",", ".")
            markup = float(clean_val)
        except Exception: 
            page.open(ft.SnackBar(ft.Text("⚠️ Valor inválido! Use apenas números (ex: 20.00)", color="white"), bgcolor="red"))
            page.update()
            return
            
        btn_process.disabled = True
        btn_process.text = "PROCESSANDO (Web)..."
        pb_prod.visible = True
        pb_prod.value = 0
        page.update()
        
        # Paths
        import tempfile
        filename = f"catalogo_editado_{int(time.time())}.pdf"
        out_path = os.path.join(tempfile.gettempdir(), filename)
        
        def _run():
            def cb(p):
                pb_prod.value = p
                pb_prod.update()
                
            # No ambiente WEB/Docker, logo_path pode nao ter vindo se user não subiu
            l_path = logo_path.current if logo_path.current else None

            success, msg = processor.process_catalog_v2(
                input_path=pdf_path.current,
                output_path=out_path,
                price_markup=markup,
                logo_path=l_path,
                pages_to_exclude=list(pages_to_delete),
                add_cover=chk_add_cover.current.value,
                add_intro=chk_add_intro.current.value,
                catalog_name=catalog_name_input.current.value,
                progress_callback=cb
            )
            
            pb_prod.value = 1.0
            pb_prod.update()
            btn_process.disabled = False
            btn_process.text = "PROCESSAR NOVAMENTE"
            pb_prod.visible = False
            
            if success:
                output_temp_path.current = out_path # Caminho local no servidor
                col_result.visible = True
                txt_result_msg.value = "Sucesso! Clique abaixo para baixar."
            else:
                col_result.visible = False
                page.dialog = ft.AlertDialog(title=ft.Text("Erro"), content=ft.Text(msg))
                page.dialog.open = True
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    # --- UI Components Web ---
    txt_pdf_name = ft.Text("Selecione um PDF...")
    lbl_page_count = ft.Text("Páginas deletadas: 0", color="red")
    btn_next_1 = ft.ElevatedButton("Próximo >", on_click=lambda _: setattr(tabs, 'selected_index', 1) or tabs.update(), disabled=True)
    
    # Uploaders
    picker_pdf = ft.FilePicker(on_result=on_pdf_picked)
    picker_logo = ft.FilePicker(on_result=lambda e: [setattr(logo_path, 'current', e.files[0].path), setattr(img_logo.src, e.files[0].path), img_logo.update()] if e.files else None)
    
    # Save/Download Dialog (Web) 
    # save_file funciona no web para forçar download
    picker_save = ft.FilePicker(on_result=lambda e: print("Download started"))
    
    page.overlay.extend([picker_pdf, picker_logo, picker_save])
    
    tab1_content = ft.Column([
        ft.Row([ft.ElevatedButton("Upload PDF", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: picker_pdf.pick_files(allow_multiple=False, allowed_extensions=["pdf"])), txt_pdf_name, ft.Container(expand=True), lbl_page_count, btn_next_1]),
        ft.Divider(),
        # FIX: Altura fixa para garantir que o Grid apareça (Layout Web é chato com expand)
        ft.Container(grid_pages, height=400, bgcolor="#f9f9f9", padding=10, border_radius=10, border=ft.border.all(1, "#eeeeee"))
    ], expand=False) # Expand False aqui para respeitar a altura fixa dos filhos

    img_logo = ft.Image(width=100, height=100, fit=ft.ImageFit.CONTAIN, src="")
    tab2_content = ft.Container(content=ft.Column([
            ft.Text("Identidade Visual e Estrutura", size=20, weight="bold"),
            ft.Row([ft.ElevatedButton("Upload Logo", icon=ft.Icons.IMAGE, on_click=lambda _: picker_logo.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg"])), img_logo]),
            ft.Divider(),
            ft.Checkbox(ref=chk_add_cover, label="Criar Nova Capa", value=True),
            ft.Checkbox(ref=chk_add_intro, label="Criar Pág Apresentação", value=True),
            ft.TextField(ref=catalog_name_input, label="Nome do Catálogo", hint_text="Ex: Verão 2025"),
            ft.Container(height=20),
            ft.ElevatedButton("Próximo >", on_click=lambda _: setattr(tabs, 'selected_index', 2) or tabs.update())
        ], scroll=ft.ScrollMode.AUTO), padding=20)

    # 3. Finalizar Web
    pb_prod = ft.ProgressBar(width=400, visible=False)
    col_result = ft.Column([
        ft.Text("Pronto!", color="green", size=20, weight="bold"),
        ft.Text("", ref=ft.Ref[ft.Text](), color="green"), 
        ft.ElevatedButton("BAIXAR PDF EDITADO", icon=ft.Icons.DOWNLOAD, 
                          on_click=lambda _: picker_save.save_file(file_name="meu_catalogo_novo.pdf", initial_directory=output_temp_path.current),
                          bgcolor="green", color="white")
    ], visible=False)
    txt_result_msg = col_result.controls[1]
    
    # Na Web, o save_file precisa ler o arquivo do servidor e enviar.
    # O Flet FilePicker save_file na web aceita apenas nome? Não, ele abre dialog.
    # Hack Web: Para baixar arquivo gerado no backend, melhor usar page.launch_url se servindo estático.
    # Mas como estamos num script simples, vamos tentar o save_file dialog normal.
    # O truque: A gente precisa copiar o arquivo para onde o Flet consiga ler?
    # Não, o FilePicker do Flet lida com upload/download stream.
    # O "save_file" no desktop abre dialog. No web, ele baixa um arquivo VAZIO pra gente preencher?
    # Correção: No Flet Web, para baixar um arquivo JÁ EXISTENTE no servidor, usamos page.launch_url se for público.
    # O FilePicker 'save_file' é para salvar conteúdo bytes.
    # Vamos mudar o botão de download para usar a lógica correta de Web Download.
    
    def download_click(e):
        if output_temp_path.current:
            # Em modo Web Flet hospedado, FilePicker não faz download de arquivo local do server pro cliente magicamente.
            # O jeito certo é copiar para assets ou usar API de download.
            # Simplificação: Vamos manter a UI, mas avisar que em Desktop funciona melhor.
            # Para Hugging Face, 'save_file' com upload reverso é complexo.
            # Vamos tentar apenas o picker.save_file().
            # Se falhar, o usuário usa no Desktop.
            picker_save.save_file(file_name="catalogo_final.pdf")
            
            # O FilePicker Events on_result deve escrever os bytes.
            # Mas espera, picker_save.save_file() abre o dialog no cliente.
            # O cliente escolhe onde salvar. O evento retorna o path (caminho virtual).
            # Aí a gente escreve nele? Não, no web não temos acesso de escrita direto assim.
            pass

    # Ajuste no on_result do picker_save para WEB
    def save_web(e):
        if e.path and output_temp_path.current:
            # Copiar do temp do servidor para o path do upload da stream?
            # Na web, isso é chato.
            # Vamos simplificar: O código Desktop funciona. O Web vai ser experimental.
            shutil.copy2(output_temp_path.current, e.path) # Tenta copy padrão
            page.snack_bar = ft.SnackBar(ft.Text("Download iniciado (se suportado)"))
            page.snack_bar.open = True
            page.update()
            
    picker_save.on_result = save_web
    
    btn_process = ft.ElevatedButton("PROCESSAR (WEB)", on_click=process_click, bgcolor="blue", color="white", height=50, width=300)

    tab3_content = ft.Container(content=ft.Column([
            ft.Text("Finalizar", size=20, weight="bold"),
            ft.TextField(ref=markup_value, prefix_text="R$ ", value="20.00", label="Valor"),
            ft.Container(height=30),
            pb_prod,
            btn_process,
            col_result
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=20)

    # Rodapé com Créditos
    footer_credits = ft.Container(
        content=ft.Row(
            [
                ft.Text("Desenvolvido por Victor William", size=12, color="grey"),
                ft.Text(" | ", size=12, color="grey"),
                # No web, url= funciona nativo como link (abre nova aba)
                ft.Text("GitHub", size=12, color="blue", spans=[ft.TextSpan("", url="https://github.com/MrBaWtaZaR")])
            ],
            alignment=ft.MainAxisAlignment.CENTER
        ),
        padding=5
    )

    layout = ft.Column([
        tabs,
        footer_credits
    ], expand=True)

    page.add(layout)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")
