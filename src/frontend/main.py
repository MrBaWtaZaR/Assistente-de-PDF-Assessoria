
import flet as ft
import os
import time
import threading
from backend.pdf_processor import PdfProcessor

def main(page: ft.Page):
    page.title = "Editor de Catálogo PDF"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.window_width = 600
    page.window_height = 800
    page.window_resizable = False
    
    # Variáveis de Estado
    pdf_path = ft.Ref[str]()
    logo_path = ft.Ref[str]()
    output_temp_path = ft.Ref[str]() # Guarda onde está o arquivo processado temporário
    
    markup_value = ft.Ref[ft.TextField]()
    pb_prod = ft.ProgressBar(width=400, color="amber", bgcolor="#eeeeee", visible=False, value=0)
    txt_status = ft.Text("", visible=False)
    
    processor = PdfProcessor()

    # --- Funções Auxiliares ---
    def open_file(path):
        if os.path.exists(path):
            os.startfile(path)
        else:
            page.snack_bar = ft.SnackBar(ft.Text(f"Arquivo não encontrado: {path}"))
            page.snack_bar.open = True
            page.update()

    def save_file_result(e: ft.FilePickerResultEvent):
        if e.path:
            # Copiar do temp para o destino
            import shutil
            try:
                shutil.copy2(output_temp_path.current, e.path)
                page.snack_bar = ft.SnackBar(ft.Text(f"Salvo com sucesso em: {e.path}"))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao salvar: {str(ex)}"))
                page.snack_bar.open = True
                page.update()

    # --- Pickers ---
    file_picker_pdf = ft.FilePicker(on_result=lambda e: update_pdf(e))
    file_picker_logo = ft.FilePicker(on_result=lambda e: update_logo(e))
    save_file_dialog = ft.FilePicker(on_result=save_file_result)
    page.overlay.extend([file_picker_pdf, file_picker_logo, save_file_dialog])

    def update_pdf(e):
        if e.files:
            path = e.files[0].path
            pdf_path.current = path
            txt_pdf_name.value = os.path.basename(path)
            txt_pdf_name.color = "black"
            txt_pdf_name.update()
            check_can_process()

    def update_logo(e):
        if e.files:
            path = e.files[0].path
            logo_path.current = path
            txt_logo_name.value = os.path.basename(path)
            txt_logo_name.color = "black"
            img_logo_preview.src = path
            img_logo_preview.visible = True
            txt_logo_name.update()
            img_logo_preview.update()

    def check_can_process():
        if pdf_path.current:
            btn_process.disabled = False
            btn_process.update()

    def process_thread(input_p, output_p, markup, logo_p):
        def update_prog(val):
            pb_prod.value = val
            pb_prod.update()

        success, msg = processor.process_catalog(
            input_path=input_p,
            output_path=output_p,
            price_markup=markup,
            logo_path=logo_p,
            progress_callback=update_prog
        )
        
        # UI updates must be scheduled on main thread if complex, 
        # but simple property updates usually work or use page.run_task
        pb_prod.value = 1.0
        pb_prod.update()
        time.sleep(0.5) # Breve pausa para ver o 100%
        
        # Pós-processamento na UI
        def pos_ui(): 
            pb_prod.visible = False
            txt_status.visible = False
            btn_process.disabled = False
            btn_process.text = "PROCESSAR NOVAMENTE"
            
            if success:
                output_temp_path.current = output_p
                col_result.visible = True
                txt_result_msg.value = msg
                txt_result_msg.color = "green"
            else:
                col_result.visible = False # Oculta se falhou
                page.dialog = ft.AlertDialog(title=ft.Text("Erro"), content=ft.Text(msg))
                page.dialog.open = True
            
            page.update()
        
        # Como estamos em thread, não podemos chamar page.update() booleano inseguro às vezes?
        # Flet é thread-safe na maioria dos updates, mas para estruturar:
        pos_ui()

    def process_click(e):
        print("Botão processar clicado!")
        if not pdf_path.current: 
            print("Nenhum PDF selecionado.")
            return

        try:
            markup = float(markup_value.current.value.replace(",", "."))
        except ValueError:
            print(f"Erro ao ler valor: {markup_value.current.value}")
            page.snack_bar = ft.SnackBar(ft.Text("Valor inválido! Digite apenas números."))
            page.snack_bar.open = True
            page.update()
            return

        print(f"Iniciando thread de processamento. Markup: {markup}")

        # UI Prep
        btn_process.disabled = True
        btn_process.text = "PROCESSANDO..."
        pb_prod.visible = True
        pb_prod.value = 0
        txt_status.value = "Analisando PDF e aplicando alterações..."
        txt_status.visible = True
        col_result.visible = False
        page.update()

        # Temp Output
        import tempfile
        temp_dir = tempfile.gettempdir()
        filename = f"processed_{int(time.time())}.pdf"
        out_path = os.path.join(temp_dir, filename)

        # Start Thread
        t = threading.Thread(
            target=process_thread,
            args=(pdf_path.current, out_path, markup, logo_path.current),
            daemon=True
        )
        t.start()
        print("Thread iniciada.")

    # --- Componentes UI ---
    
    txt_pdf_name = ft.Text("Nenhum arquivo selecionado", italic=True, color="grey")
    txt_logo_name = ft.Text("Nenhuma logo selecionada", italic=True, color="grey")
    img_logo_preview = ft.Image(width=50, height=50, fit=ft.ImageFit.CONTAIN, visible=False)
    
    markup_value = ft.Ref[ft.TextField]()
    
    # Seção Resultado (Inicialmente Oculta)
    txt_result_msg = ft.Text("", weight=ft.FontWeight.BOLD)
    btn_open = ft.ElevatedButton("VISUALIZAR (ABRIR)", icon=ft.Icons.VISIBILITY, on_click=lambda _: open_file(output_temp_path.current), bgcolor="blue", color="white")
    btn_save_as = ft.ElevatedButton("SALVAR COMO...", icon=ft.Icons.SAVE, on_click=lambda _: save_file_dialog.save_file(allowed_extensions=["pdf"], file_name="catalogo_novo.pdf"), bgcolor="green", color="white")
    
    col_result = ft.Column([
        ft.Divider(),
        ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color="green", size=30), ft.Text("Sucesso!", size=20, weight=ft.FontWeight.BOLD)]),
        txt_result_msg,
        ft.Row([btn_open, btn_save_as], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
    ], visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # Header
    header = ft.Container(
        content=ft.Column([
            ft.Text("Editor de Catálogo", size=30, weight=ft.FontWeight.BOLD, color="bluegrey"),
            ft.Text("Automatize a atualização de preços e logos", size=14, color="bluegrey"),
        ]),
        padding=ft.padding.only(bottom=20)
    )

    # Inputs Container
    card_inputs = ft.Container(
        content=ft.Column([
            # PDF Section
            ft.Row([ft.Icon(ft.Icons.PICTURE_AS_PDF, color="red"), ft.Text("Arquivo de Catálogo", weight=ft.FontWeight.BOLD)]),
            ft.Row([
                ft.ElevatedButton("Selecionar PDF", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker_pdf.pick_files(allow_multiple=False, allowed_extensions=["pdf"])),
                ft.Container(content=txt_pdf_name, padding=10, expand=True)
            ]),
            
            ft.Divider(color="transparent", height=10),
            
            # Settings Section
            ft.Row([ft.Icon(ft.Icons.SETTINGS, color="blue"), ft.Text("Configurações", weight=ft.FontWeight.BOLD)]),
            ft.Text("1. Logo (Opcional)"),
            ft.Row([
                ft.ElevatedButton("Selecionar Logo", icon=ft.Icons.IMAGE, on_click=lambda _: file_picker_logo.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg"])),
                img_logo_preview,
                ft.Container(content=txt_logo_name, padding=5, expand=True)
            ]),
            
            ft.Container(height=10),
            
            ft.Text("2. Valor Adicional (R$)"),
            ft.TextField(ref=markup_value, prefix_text="R$ ", value="20.00", width=150, keyboard_type=ft.KeyboardType.NUMBER)
        ]),
        padding=20,
        bgcolor="white",
        border_radius=15,
        shadow=ft.BoxShadow(blur_radius=10, color="#1A000000")
    )

    # Process Button
    btn_process = ft.ElevatedButton(
        text="PROCESSAR CATÁLOGO",
        on_click=process_click,
        style=ft.ButtonStyle(color="white", bgcolor="blue", padding=20, shape=ft.RoundedRectangleBorder(radius=10)),
        width=400,
        disabled=True
    )

    footer = ft.Container(
        content=ft.Column([

            txt_status,
            pb_prod,
            ft.Container(height=10),
            btn_process,
            col_result
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.only(top=30),
        alignment=ft.alignment.center
    )

    page.scroll = ft.ScrollMode.AUTO
    page.add(header, card_inputs, footer)

if __name__ == "__main__":
    ft.app(target=main)
