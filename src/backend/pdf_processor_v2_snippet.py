
import fitz  # PyMuPDF
import re
import os
import datetime
from typing import Optional, List, Tuple
from PIL import Image

class PdfProcessor:
    def __init__(self):
        self.price_regex = re.compile(r"R\$\s?(\d{1,3}(?:\.?\d{3})*(?:,\d{2})?)")

    def get_thumbnails(self, input_path: str) -> List[str]:
        """Gera thumbnails de cada página e retorna lista de caminhos temporários."""
        thumbs = []
        try:
            doc = fitz.open(input_path)
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            # Limitar a resolução para não pesar a UI (scale 0.2 ~ 150-200px width)
            mat = fitz.Matrix(0.15, 0.15)
            
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                thumb_path = os.path.join(temp_dir, f"thumb_{os.path.basename(input_path)}_{i}.jpg")
                pix.save(thumb_path)
                thumbs.append(thumb_path)
            doc.close()
        except Exception as e:
            print(f"Erro ao gerar thumbnails: {e}")
        return thumbs

    def process_catalog_v2(self, 
                           input_path: str, 
                           output_path: str, 
                           price_markup: float, 
                           logo_path: Optional[str], 
                           pages_to_exclude: List[int],
                           add_cover: bool,
                           add_intro: bool,
                           catalog_name: str,
                           progress_callback=None) -> Tuple[bool, str]:
        """
        Processamento V2: Reconstrói o PDF.
        """
        if not os.path.exists(input_path):
            return False, f"Arquivo não encontrado: {input_path}"

        try:
            src_doc = fitz.open(input_path)
            out_doc = fitz.open() # Novo PDF vazio
            
            total_steps = len(src_doc) + (1 if add_cover else 0) + (1 if add_intro else 0)
            current_step = 0

            # 1. Gerar CAPA (Logo Centralizada)
            if add_cover and logo_path:
                cover_page = out_doc.new_page() # A4 padrão
                # Inserir logo grande no centro
                w, h = cover_page.rect.width, cover_page.rect.height
                logo_w = w * 0.5
                logo_h = logo_w # Assumindo quadrado, ou ajusta
                
                logo_rect = fitz.Rect(
                    (w - logo_w)/2,
                    (h - logo_w)/2 - 50, # Um pouco pra cima do centro visual
                    (w + logo_w)/2,
                    (h + logo_w)/2 - 50
                )
                cover_page.insert_image(logo_rect, filename=logo_path, keep_proportion=True)
                
            # 2. Gerar INTRO (Texto)
            if add_intro:
                intro_page = out_doc.new_page()
                # Texto
                text_writer = fitz.TextWriter(intro_page.rect)
                
                # Título
                font_size_title = 24
                # Posição aproximada centro X
                text_writer.append((50, 200), f"Catálogo: {catalog_name}", fontsize=font_size_title, fontname="helv")
                
                # Data
                dt_str = datetime.datetime.now().strftime("%d/%m/%Y")
                text_writer.append((50, 250), f"Gerado em: {dt_str}", fontsize=18, fontname="helv")
                
                text_writer.write_text(intro_page)

            # 3. Processar páginas originais
            for page_num, page in enumerate(src_doc):
                current_step += 1
                if progress_callback: progress_callback(current_step / total_steps * 0.9)

                if page_num in pages_to_exclude:
                    continue # Pula página deletada
                
                # Processar Preço e Logo Visualmente na página ORIGINAL
                self._update_prices_on_page(page, price_markup)
                if logo_path:
                    self._insert_logo_on_page(page, logo_path)
                
                # Inserir essa página processada no novo doc
                # insert_pdf copia a página. 
                # OBS: Ao modificar a página em memória do src_doc, o insert_pdf carrega ela modificada?
                # Sim, se usarmos o mesmo fitz object.
                out_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)

            # Salvar
            if progress_callback: progress_callback(0.95)
            out_doc.save(output_path, garbage=4, deflate=True) # Deflate True é melhor para docs "Textuais" criados do zero
            src_doc.close()
            out_doc.close()
            
            return True, "Processamento V2 Concluído!"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Erro Fatal: {str(e)}"

    # --- Manter métodos auxiliares (_parse_price, _format_price, _update_prices_on_page, _insert_logo_on_page) ---
    # Copiando apenas a estrutura, vou usar replace_file_content para INJETAR esses métodos novos na classe existente
    # mantendo os antigos (_update_prices_on_page e _insert_logo_on_page) que já funcionam bem.

    def _parse_price(self, price_str: str) -> float:
        # ... (Mantido)
        pass
