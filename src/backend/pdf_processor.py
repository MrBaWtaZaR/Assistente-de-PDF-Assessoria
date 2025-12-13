
import fitz  # PyMuPDF
import re
import os
import datetime
from typing import Optional, List, Tuple

class PdfProcessor:
    def __init__(self):
        self.price_regex = re.compile(r"R\$\s?(\d{1,3}(?:\.?\d{3})*(?:,\d{2})?)")

    def _get_page_bg_color(self, page) -> Tuple[float, float, float]:
        """Tenta descobrir a cor de fundo predominante da página."""
        try:
            # Reduzir drasticamente para pegar a média/fundo
            pix = page.get_pixmap(matrix=fitz.Matrix(0.01, 0.01), alpha=False)
            # Pegar pixel do canto (geralmente fundo)
            r, g, b = pix.pixel(0, 0)
            return (r/255.0, g/255.0, b/255.0)
        except:
            return (1.0, 1.0, 1.0) # Branco padrão

    def _get_contrast_color(self, bg: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Retorna preto ou branco dependendo da luminância do fundo."""
        lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        return (0, 0, 0) if lum > 0.5 else (1, 1, 1)

    def process_catalog(self, input_path: str, output_path: str, price_markup: float, logo_path: Optional[str] = None, progress_callback=None) -> Tuple[bool, str]:
        """
        Processa o catálogo PDF, atualizando preços e inserindo logo.
        
        Args:
            input_path: Caminho do arquivo PDF original.
            output_path: Caminho para salvar o novo PDF.
            price_markup: Valor a ser adicionado a cada preço encontrado.
            logo_path: Caminho da imagem da logo (opcional).
            progress_callback: Função func(percent) para reportar progresso (0.0 a 1.0).
            
        Returns:
            Tuple[bool, str]: (Sucesso, Mensagem)
        """
        if not os.path.exists(input_path):
            return False, f"Arquivo de entrada não encontrado: {input_path}"

        try:
            doc = fitz.open(input_path)
            total_pages = len(doc)
        except Exception as e:
            return False, f"Erro ao abrir PDF: {str(e)}"

        total_prices_updated = 0
        total_logos_inserted = 0

        for page_num, page in enumerate(doc):
            # Reportar Progresso
            if progress_callback:
                # Progresso de 0 a 0.9 (deixando 0.1 para salvar)
                progress = (page_num / total_pages) * 0.9
                progress_callback(progress)

            # 1. Atualizar Preços
            updated_count = self._update_prices_on_page(page, price_markup)
            total_prices_updated += updated_count

            # 2. Inserir Logo (se fornecida)
            if logo_path and os.path.exists(logo_path):
                inserted_count = self._insert_logo_on_page(page, logo_path)
                total_logos_inserted += inserted_count

        if progress_callback:
            progress_callback(0.95) # Salvando...

        try:
            # save args: garbage=0 (não reescrever streams não usados), deflate=False (não reprimir)
            # Para manter qualidade máxima, ideal é não mexer.
            doc.save(output_path, garbage=0, deflate=False)
            doc.close()
            return True, f"Processamento concluído! Preços atualizados: {total_prices_updated}. Logos inseridas: {total_logos_inserted}."
        except Exception as e:
            return False, f"Erro ao salvar PDF: {str(e)}"

    def get_thumbnails(self, input_path: str) -> List[str]:
        """Gera thumbnails de cada página e retorna lista de caminhos temporários."""
        thumbs = []
        try:
            doc = fitz.open(input_path)
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            # Limitar a resolução para não pesar a UI (scale 0.15)
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
            
            total_steps = len(src_doc)
            current_step = 0

            # 0. Descobrir Cor de Fundo da PRIMEIRA página real (que não será deletada)
            bg_color = (1, 1, 1) # White default
            for i in range(len(src_doc)):
                if i not in pages_to_exclude:
                    bg_color = self._get_page_bg_color(src_doc[i])
                    break
            
            text_color = self._get_contrast_color(bg_color)

            # 1. Gerar CAPA (Logo Centralizada)
            if add_cover and logo_path:
                cover_page = out_doc.new_page() 
                cover_page.draw_rect(cover_page.rect, color=None, fill=bg_color)
                
                # Inserir logo grande no centro
                w, h = cover_page.rect.width, cover_page.rect.height
                logo_w = w * 0.5
                logo_h = logo_w 
                
                logo_rect = fitz.Rect(
                    (w - logo_w)/2,
                    (h - logo_w)/2 - 50, 
                    (w + logo_w)/2,
                    (h + logo_w)/2 - 50
                )
                cover_page.insert_image(logo_rect, filename=logo_path, keep_proportion=True)
                
            # 2. Gerar INTRO (Texto)
            if add_intro:
                intro_page = out_doc.new_page()
                intro_page.draw_rect(intro_page.rect, color=None, fill=bg_color)
                
                # Setup Titulo
                font_size_title = 30
                font_size_date = 18
                margin_top = 300
                
                w = intro_page.rect.width
                
                # Centralizar Texto: Precisamos da largura da string
                # PyMuPDF insert_text não centraliza nativo.
                # Solução: text_length
                
                title_text = f"{catalog_name}"
                date_text = f"Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y')}"
                
                # Usar font helv para calcular largura
                font = fitz.Font("helv")
                
                tw_title = font.text_length(title_text, fontsize=font_size_title)
                tw_date = font.text_length(date_text, fontsize=font_size_date)
                
                x_title = (w - tw_title) / 2
                x_date = (w - tw_date) / 2
                
                intro_page.insert_text((x_title, margin_top), title_text, fontsize=font_size_title, fontname="helv", color=text_color)
                intro_page.insert_text((x_date, margin_top + 50), date_text, fontsize=font_size_date, fontname="helv", color=text_color)

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
                out_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)

            if progress_callback: progress_callback(0.95)
            # Ao salvar um doc reconstruído, deflate=True ajuda a comprimir os novos assets
            out_doc.save(output_path, garbage=4, deflate=True) 
            src_doc.close()
            out_doc.close()
            
            return True, "Processamento V2 Concluído!"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Erro Fatal: {str(e)}"

    def _parse_price(self, price_str: str) -> float:
        """Converte string 'R$ 1.234,56' para float 1234.56"""
        # Remove Símbolo e espaços
        clean_str = price_str.replace("R$", "").strip()
        # Remove pontos de milhar e troca vírgula por ponto
        clean_str = clean_str.replace(".", "").replace(",", ".")
        try:
            return float(clean_str)
        except ValueError:
            return 0.0

    def _format_price(self, value: float) -> str:
        """Converte float 1234.56 para string 'R$ 1.234,56'"""
        return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    def _update_prices_on_page(self, page, markup: float) -> int:
        count = 0
        # Busca texto na página
        text_instances = page.search_for("R$")
        
        # Como o search_for("R$") só pega o símbolo, precisamos capturar o número ao redor.
        # Uma estratégia melhor é iterar sobre blocos de texto ou usar regex em todo o texto e achar as boxes.
        
        # Estratégia Melhorada: Get text blocks, regex match content, find bbox.
        # Mas para simplicidade e precisão de layout, vamos usar 'get_text("words")' ou regex search
        
        # Vamos tentar uma abordagem híbrida: procurar o regex no texto extraído e obter as áreas.
        # O fitz tem 'search_for' que aceita texto literal. Regex direto no search_for não é suportado nativamente dessa forma simples.
        # Workaround: Extrair texto com 'blocks', achar o match no texto, e ter as bboxes é complexo se o texto for fragmentado.
        
        # Simplificação funcional: Iterar sobre todas as palavras/blocos e ver se bate com regex price.
        words = page.get_text("words") # (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        
        # Agrupar palavras pode ser necessário se "R$" estiver separado de "35,00".
        # Por enquanto agiremos em tokens que contenham tudo ou vamos reconstruir linhas.
        
        # Vamos consolidar palavras em linhas para o regex funcionar melhor.
        # Mas para substituir 'in-place', precisamos das coordenadas exatas.
        
        # Implementação Robust:
        # Procurar por "R$"
        matches = page.search_for("R$")
        for rect in matches:
            # Expandir o retângulo para a direita para tentar pegar o número
            # Assumindo leitura da esquerda pra direita.
            # Define uma área de busca à direita do cifrão.
            search_rect = fitz.Rect(rect.x0, rect.y0, rect.x1 + 100, rect.y1) # +100pts deve cobrir o preço
            
            # Extrair texto dessa área
            text_in_rect = page.get_text("text", clip=search_rect).strip()
            
            # Verificar se parece um preço completo (ex: R$ 35,00 ou apenas 35,00 se o R$ já foi achado)
            # O texto extraído do clip pode conter o R$ de novo ou não, dependendo da precisão.
            
            # Vamos usar uma regex que busca o número logo após o R$
            # Na verdade, se usarmos page.get_text("blocks"), temos o texto agrupado.
            pass

        # Abordagem Alternativa mais Segura (Text Blocks):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"]
                    if "R$" in text:
                        # Achamos um span com preço.
                        match = self.price_regex.search(text)
                        if match:
                            old_price_str = match.group(0) # "R$ 35,00"
                            val_str = match.group(1) # "35,00"
                            
                            current_val = self._parse_price(text) # Usa a string toda se for só o preço
                            if current_val == 0.0:
                                current_val = self._parse_price(val_str)

                            new_val = current_val + markup
                            new_text = self._format_price(new_val)
                            
                            # Bounding box deste span
                            bbox = fitz.Rect(s["bbox"])
                            
                            # --- Lógica Avançada de Camuflagem (Color Sampling) ---
                            # 1. Obter uma amostra da área do preço original
                            # Vamos pegar 1px de borda ao redor para ter chance de pegar o fundo
                            sample_rect = fitz.Rect(bbox.x0 - 2, bbox.y0 - 2, bbox.x1 + 2, bbox.y1 + 2)
                            
                            # Gerar pixmap dessa pequena área
                            # alpha=False para ignorar transparência (queremos a cor final)
                            try:
                                pix = page.get_pixmap(clip=sample_rect, alpha=False)
                                # Pegar a cor do pixel top-left (0,0) que deve ser fundo
                                # Se o bbox estiver muito justo, 0,0 pode ser texto. Vamos tentar (-1, -1) relativo?
                                # O pixmap é local. (0,0) é o canto do sample_rect.
                                r, g, b = pix.pixel(0, 0)
                                bg_color = (r/255.0, g/255.0, b/255.0)
                            except:
                                # Fallback para branco se falhar
                                bg_color = (1, 1, 1)

                            # Redact (Apagar original) com a cor descoberta
                            page.draw_rect(bbox, color=None, fill=bg_color) 
                            
                            # Escrever novo valor
                            # Usar fonte Helvetica (padrão sans-serif) e cor preta (ou tentar detectar cor do texto?)
                            # Assumiremos preto para contraste.
                            
                            # Centralizar melhor?
                            # Se o texto novo for menor que o rect, centralizar no X.
                            # Mas 'insert_text' é por posição inicial.
                            
                            page.insert_text(
                                (bbox.x0, bbox.y1 - 2), 
                                new_text, 
                                fontsize=s["size"], 
                                fontname="helv", 
                                color=(0,0,0)
                            )
                            count += 1
        return count

    def _insert_logo_on_page(self, page, logo_path: str) -> int:
        count = 0
        img_list = page.get_images()
        
        # Para evitar colocar logo na própria logo (se rodar 2x) ou em ícones pequenos
        # Podemos filtrar por tamanho mínimo.
        
        for img in img_list:
            xref = img[0]
            # Obter retângulo(s) onde essa imagem aparece
            rects = page.get_image_rects(xref)
            
            for rect in rects:
                # --- Correção de Sangria (Bleed) ---
                # As imagens podem ser maiores que a página. Precisamos da interseção.
                page_rect = page.cropbox # Área visível da página
                visible_rect = rect & page_rect # Interseção
                
                # Se a interseção for vazia ou inválida, pular
                if visible_rect.is_empty or visible_rect.width < 100 or visible_rect.height < 100:
                    continue

                aspect_ratio = visible_rect.width / visible_rect.height
                if aspect_ratio > 3 or aspect_ratio < 0.3: 
                    continue
                
                # Definir tamanho da logo baseado na área VISÍVEL
                logo_scale = 0.15
                logo_w = visible_rect.width * logo_scale
                logo_h = logo_w 
                
                # Margem de segurança AUMENTADA
                padding = 20 # Era 10, aumentei para garantir
                
                # Calcular posição: Canto inferior esquerdo da área VISÍVEL
                dest_rect = fitz.Rect(
                    visible_rect.x0 + padding,
                    visible_rect.y1 - logo_h - padding,
                    visible_rect.x0 + logo_w + padding,
                    visible_rect.y1 - padding
                )
                
                # Inserir Logo
                # overlay=True põe por cima. keep_proportion garante que não distorça.
                try:
                   page.insert_image(dest_rect, filename=logo_path, keep_proportion=True, overlay=True)
                   count += 1
                except:
                   pass # Ignora erros de inserção pontuais
                
        return count

if __name__ == "__main__":
    # Teste rápido manual
    print("Módulo de Processamento PDF carregado.")
