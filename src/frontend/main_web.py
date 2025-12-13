import flet as ft
import os
import time
import threading
import shutil
from backend.pdf_processor import PdfProcessor

# Diretórios - Usa variável de ambiente ou fallback
UPLOAD_DIR = os.environ.get("FLET_UPLOAD_DIR", "/app/uploads")
ASSETS_DIR = os.environ.get("FLET_ASSETS_DIR", "/app/assets")

# Fallback para Windows local
if not os.path.exists("/app"):
    BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR = os.path.join(BASE, "uploads")
    ASSETS_DIR = os.path.join(BASE, "assets")

def main(page: ft.Page):
    print(f"[INIT] UPLOAD_DIR={UPLOAD_DIR}")
    print(f"[INIT] ASSETS_DIR={ASSETS_DIR}")
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    page.title = "Editor de Catálogo PDF"
    page.theme_mode = ft.ThemeMode.LIGHT

    # Estado
    pdf_path_ref = {"value": None}
    logo_path_ref = {"value": None}
    output_url_ref = {"value": None}
    
    markup_value = ft.Ref[ft.TextField]()
    catalog_name_input = ft.Ref[ft.TextField]()
    chk_add_cover = ft.Ref[ft.Checkbox]()
    chk_add_intro = ft.Ref[ft.Checkbox]()
    
    pages_to_delete = set()
    processor = PdfProcessor()
    
    # UI
    tabs = ft.Tabs(selected_index=0, animation_duration=300, tabs=[], expand=True)
    grid_pages = ft.GridView(expand=True, max_extent=160, child_aspect_ratio=0.7, spacing=10, run_spacing=10)
    pb_upload = ft.ProgressRing(width=20, height=20, visible=False)
    pb_prod = ft.ProgressBar(width=400, visible=False)
    txt_pdf = ft.Text("Nenhum arquivo")
    lbl_page_count = ft.Text("Remover: 0", color="red")
    btn_next = ft.ElevatedButton("Próximo >", disabled=True)
    img_logo = ft.Image(width=80, height=80, fit=ft.ImageFit.CONTAIN)

    def toggle_delete(e, idx):
        if e.control.value:
            pages_to_delete.add(idx)
        else:
            pages_to_delete.discard(idx)
        lbl_page_count.value = f"Remover: {len(pages_to_delete)}"
        lbl_page_count.update()

    def load_pages(filepath):
        grid_pages.controls.clear()
        grid_pages.controls.append(ft.Text("Carregando..."))
        page.update()
        
        def _load():
            try:
                actual_path = filepath  # Copia para variável local
                print(f"[LOAD] Abrindo {actual_path}")
                
                # Verificar se arquivo existe
                if not os.path.exists(actual_path):
                    # Listar o que tem na pasta
                    files = os.listdir(UPLOAD_DIR) if os.path.exists(UPLOAD_DIR) else []
                    print(f"[LOAD] Arquivo não encontrado. Conteúdo de {UPLOAD_DIR}: {files}")
                    if files:
                        # Usar o arquivo mais recente
                        actual_path = os.path.join(UPLOAD_DIR, sorted(files)[-1])
                        print(f"[LOAD] Usando: {actual_path}")
                    else:
                        raise Exception(f"Pasta vazia: {UPLOAD_DIR}")
                
                thumbs = processor.get_thumbnails(actual_path)
                if not thumbs:
                    raise Exception("Falha ao gerar miniaturas")

                print(f"[LOAD] {len(thumbs)} páginas geradas")
                
                web_thumbs = []
                for i, t in enumerate(thumbs):
                    fname = f"t_{int(time.time())}_{i}.png"
                    dst = os.path.join(ASSETS_DIR, fname)
                    shutil.copy2(t, dst)
                    web_thumbs.append(f"/{fname}")

                grid_pages.controls.clear()
                for i, url in enumerate(web_thumbs):
                    chk = ft.Checkbox(label=f"P{i+1}", on_change=lambda e, x=i: toggle_delete(e, x), fill_color="red")
                    img = ft.Image(src=url, fit=ft.ImageFit.CONTAIN, border_radius=5)
                    card = ft.Container(
                        content=ft.Column([ft.Container(img, expand=True), chk], spacing=2),
                        padding=5, bgcolor="white", border=ft.border.all(1, "#ddd"), border_radius=8
                    )
                    grid_pages.controls.append(card)
                grid_pages.update()
                btn_next.disabled = False
                btn_next.update()
                print("[LOAD] OK")

            except Exception as e:
                print(f"[ERROR] {e}")
                grid_pages.controls.clear()
                grid_pages.controls.append(ft.Text(str(e), color="red"))
                grid_pages.update()
                
        threading.Thread(target=_load, daemon=True).start()

    # UPLOAD - Usando API correta do Flet
    def on_pdf_pick(e: ft.FilePickerResultEvent):
        if e.files:
            f = e.files[0]
            txt_pdf.value = f"Enviando {f.name}..."
            pb_upload.visible = True
            page.update()
            
            try:
                # Gerar URL de upload usando Flet
                upload_url = page.get_upload_url(f.name, 600)
                print(f"[UPLOAD] URL gerada: {upload_url}")
                
                upload_list = [
                    ft.FilePickerUploadFile(f.name, upload_url=upload_url)
                ]
                picker_pdf.upload(upload_list)
            except Exception as ex:
                print(f"[UPLOAD ERROR] {ex}")
                txt_pdf.value = f"Erro: {ex}"
                txt_pdf.color = "red"
                pb_upload.visible = False
                page.update()

    def on_pdf_upload(e: ft.FilePickerUploadEvent):
        print(f"[UPLOAD] Progress: {e.progress}, Error: {e.error}")
        
        if e.error:
            txt_pdf.value = f"Erro: {e.error}"
            txt_pdf.color = "red"
            pb_upload.visible = False
            page.update()
            return
            
        if e.progress == 1.0:
            filepath = os.path.join(UPLOAD_DIR, e.file_name)
            pdf_path_ref["value"] = filepath
            
            print(f"[UPLOAD] Completo: {filepath}")
            
            txt_pdf.value = f"OK: {e.file_name}"
            txt_pdf.color = "green"
            pb_upload.visible = False
            page.update()
            
            pages_to_delete.clear()
            load_pages(filepath)
        else:
            txt_pdf.value = f"Enviando... {int(e.progress * 100)}%"
            txt_pdf.update()

    def on_logo_pick(e: ft.FilePickerResultEvent):
        if e.files:
            f = e.files[0]
            try:
                upload_url = page.get_upload_url(f.name, 600)
                upload_list = [ft.FilePickerUploadFile(f.name, upload_url=upload_url)]
                picker_logo.upload(upload_list)
            except Exception as ex:
                print(f"[LOGO ERROR] {ex}")

    def on_logo_upload(e: ft.FilePickerUploadEvent):
        if e.progress == 1.0:
            filepath = os.path.join(UPLOAD_DIR, e.file_name)
            logo_path_ref["value"] = filepath
            
            preview = f"logo_{int(time.time())}.png"
            dst = os.path.join(ASSETS_DIR, preview)
            if os.path.exists(filepath):
                shutil.copy2(filepath, dst)
                img_logo.src = f"/{preview}"
                img_logo.update()
            page.open(ft.SnackBar(ft.Text("Logo OK")))
            page.update()

    def process(e):
        if not pdf_path_ref["value"]:
            page.open(ft.SnackBar(ft.Text("Envie um PDF"), bgcolor="red"))
            return
            
        try:
            val = markup_value.current.value.replace("R$", "").replace(" ", "").replace(",", ".")
            markup = float(val)
        except:
            page.open(ft.SnackBar(ft.Text("Valor inválido"), bgcolor="red"))
            return
        
        btn_proc.disabled = True
        btn_proc.text = "Processando..."
        pb_prod.visible = True
        page.update()
        
        fname = f"catalogo_{int(time.time())}.pdf"
        out = os.path.join(ASSETS_DIR, fname)
        
        def _run():
            ok, msg = processor.process_catalog_v2(
                input_path=pdf_path_ref["value"],
                output_path=out,
                price_markup=markup,
                logo_path=logo_path_ref["value"],
                pages_to_exclude=list(pages_to_delete),
                add_cover=chk_add_cover.current.value,
                add_intro=chk_add_intro.current.value,
                catalog_name=catalog_name_input.current.value,
                progress_callback=None
            )
            
            pb_prod.visible = False
            btn_proc.disabled = False
            btn_proc.text = "PROCESSAR"
            
            if ok:
                output_url_ref["value"] = f"/{fname}"
                col_result.visible = True
                page.open(ft.SnackBar(ft.Text("Pronto!"), bgcolor="green"))
            else:
                page.open(ft.AlertDialog(title=ft.Text("Erro"), content=ft.Text(msg)))
            page.update()

        threading.Thread(target=_run, daemon=True).start()

    # FilePickers
    picker_pdf = ft.FilePicker(on_result=on_pdf_pick, on_upload=on_pdf_upload)
    picker_logo = ft.FilePicker(on_result=on_logo_pick, on_upload=on_logo_upload)
    page.overlay.extend([picker_pdf, picker_logo])
    
    btn_next.on_click = lambda _: setattr(tabs, 'selected_index', 1) or tabs.update()
    
    # Tab 1
    tab1 = ft.Column([
        ft.Row([
            ft.ElevatedButton("Enviar PDF", icon=ft.Icons.UPLOAD, on_click=lambda _: picker_pdf.pick_files(allowed_extensions=["pdf"])),
            txt_pdf, pb_upload
        ]),
        ft.Row([ft.Container(expand=True), lbl_page_count, btn_next]),
        ft.Divider(),
        ft.Container(grid_pages, height=400, bgcolor="#f5f5f5", padding=10, border_radius=10)
    ])

    # Tab 2
    tab2 = ft.Container(ft.Column([
        ft.Text("Configuração", size=20, weight="bold"),
        ft.Row([ft.ElevatedButton("Logo", icon=ft.Icons.IMAGE, on_click=lambda _: picker_logo.pick_files(allowed_extensions=["png","jpg"])), img_logo]),
        ft.Divider(),
        ft.Checkbox(ref=chk_add_cover, label="Capa Nova", value=True),
        ft.Checkbox(ref=chk_add_intro, label="Página Intro", value=True),
        ft.TextField(ref=catalog_name_input, label="Nome", hint_text="Catálogo 2025"),
        ft.ElevatedButton("Próximo >", on_click=lambda _: setattr(tabs, 'selected_index', 2) or tabs.update())
    ], scroll=ft.ScrollMode.AUTO), padding=20)

    # Tab 3 - Resultado com opções de compartilhamento
    def get_download_url():
        """Retorna URL do PDF"""
        return output_url_ref["value"]  # Ex: /catalogo_123.pdf
    
    def get_full_download_url():
        """URL completa para compartilhar"""
        if output_url_ref["value"]:
            return f"https://victorbrown-assistentepdf.hf.space{output_url_ref['value']}"
        return None
    
    def download_pdf(_):
        url = get_download_url()
        if url:
            page.launch_url(url)
    
    def copy_link(_):
        full_url = get_full_download_url()
        if full_url:
            page.set_clipboard(full_url)
            page.open(ft.SnackBar(ft.Text("Link copiado! Cole no WhatsApp"), bgcolor="green"))
            page.update()
    
    def share_whatsapp(_):
        full_url = get_full_download_url()
        if full_url:
            whatsapp_url = f"https://api.whatsapp.com/send?text=Confira%20meu%20cat%C3%A1logo:%20{full_url}"
            page.launch_url(whatsapp_url)
    
    col_result = ft.Column([
        ft.Text("✅ Catálogo Pronto!", color="green", size=22, weight="bold"),
        ft.Container(height=10),
        ft.ElevatedButton("📥 BAIXAR PDF AGORA", icon=ft.Icons.DOWNLOAD, 
            on_click=download_pdf, 
            bgcolor="green", color="white", height=50, width=280),
        ft.Container(height=10),
        ft.Row([
            ft.ElevatedButton("📋 Copiar Link", icon=ft.Icons.COPY, on_click=copy_link, bgcolor="blue", color="white"),
            ft.ElevatedButton("📱 WhatsApp", icon=ft.Icons.SHARE, on_click=share_whatsapp, bgcolor="#25D366", color="white"),
        ], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=10),
        ft.Text("⚠️ BAIXE AGORA! Links expiram quando o servidor reinicia.", size=12, color="orange", weight="bold"),
    ], visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    btn_proc = ft.ElevatedButton("PROCESSAR", on_click=process, bgcolor="blue", color="white", height=50, width=300)
    
    tab3 = ft.Container(ft.Column([
        ft.Text("Finalizar", size=20, weight="bold"),
        ft.TextField(ref=markup_value, prefix_text="R$ ", value="20.00", label="Markup"),
        ft.Container(height=20),
        pb_prod, btn_proc, col_result
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=20)

    footer = ft.Container(ft.Row([
        ft.Text("Desenvolvido por Victor William", size=12, color="grey"),
        ft.Text(" | ", size=12, color="grey"),
        ft.Text("GitHub", size=12, color="blue", spans=[ft.TextSpan("", url="https://github.com/MrBaWtaZaR")])
    ], alignment=ft.MainAxisAlignment.CENTER), padding=5)

    tabs.tabs = [
        ft.Tab(text="1. Arquivo", content=tab1),
        ft.Tab(text="2. Config", content=tab2),
        ft.Tab(text="3. Processar", content=tab3)
    ]
    
    page.add(ft.Column([tabs, footer], expand=True))
    page.update()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0",
           upload_dir=UPLOAD_DIR, assets_dir=ASSETS_DIR)

