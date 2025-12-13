
import fitz  # PyMuPDF
import re
import os
import datetime
from typing import Optional, List, Tuple

class PdfProcessor:
    def __init__(self):
        # Regex aprimorado para múltiplos formatos de preço:
        # - R$ 14,00 (formato brasileiro padrão)
        # - R$ 14.00 (formato com ponto decimal)
        # - R$14,00 (sem espaço)
        # - R$ 1.234,56 (com separador de milhar)
        # - R$ 1,234.56 (formato americano)
        self.price_regex = re.compile(
            r"R\$\s*(\d{1,3}(?:[\.,]?\d{3})*(?:[\.,]\d{1,2})?)",
            re.IGNORECASE
        )
        
        # Regex alternativo para preços sem símbolo R$ mas com contexto
        self.price_number_regex = re.compile(
            r"(\d{1,3}(?:[\.,]?\d{3})*[\.,]\d{2})"
        )

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
        """
        Converte string de preço para float, detectando automaticamente o formato.
        Suporta:
        - R$ 1.234,56 (BR padrão)
        - R$ 1,234.56 (US)
        - R$ 14.00 ou R$ 14,00 (simples)
        """
        # Remove Símbolo R$ e espaços
        clean_str = price_str.replace("R$", "").replace("r$", "").strip()
        
        # Se não tiver nenhum separador, retorna direto
        if '.' not in clean_str and ',' not in clean_str:
            try:
                return float(clean_str)
            except ValueError:
                return 0.0
        
        # Detectar formato baseado na posição dos separadores
        last_dot = clean_str.rfind('.')
        last_comma = clean_str.rfind(',')
        
        # Se só tem um tipo de separador
        if last_dot == -1:
            # Só tem vírgula - vírgula é decimal
            clean_str = clean_str.replace(",", ".")
        elif last_comma == -1:
            # Só tem ponto
            # Se tem mais de um ponto, os primeiros são separador de milhar
            if clean_str.count('.') > 1:
                parts = clean_str.rsplit('.', 1)
                clean_str = parts[0].replace('.', '') + '.' + parts[1]
            # Se tem só um ponto e está nos últimos 3 chars, é decimal
            # Caso contrário é separador de milhar
            elif len(clean_str) - last_dot <= 3:
                pass  # Ponto já é decimal
            else:
                clean_str = clean_str.replace('.', '')  # Remove separador de milhar
        else:
            # Tem ambos - o que vem por último é o decimal
            if last_comma > last_dot:
                # Vírgula é decimal: 1.234,56
                clean_str = clean_str.replace(".", "").replace(",", ".")
            else:
                # Ponto é decimal: 1,234.56
                clean_str = clean_str.replace(",", "")
        
        try:
            return float(clean_str)
        except ValueError:
            return 0.0

    def _format_price(self, value: float) -> str:
        """Converte float 1234.56 para string 'R$ 1.234,56'"""
        return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    def _update_prices_on_page(self, page, markup: float) -> int:
        """
        Atualiza preços na página com detecção aprimorada.
        Suporta múltiplos formatos e preserva formatação visual.
        """
        count = 0
        processed_rects = []  # Para evitar processar a mesma área duas vezes
        
        # DEBUG: Log do texto extraído
        full_text = page.get_text("text")
        print(f"[DEBUG] Página - texto total: {len(full_text)} chars")
        if "R$" in full_text or "r$" in full_text.lower():
            print(f"[DEBUG] Contém R$!")
            # Mostrar linhas com preços
            for line in full_text.split('\n'):
                if 'R$' in line or 'r$' in line.lower():
                    print(f"[DEBUG] Linha com preço: '{line.strip()}'")
        else:
            print(f"[DEBUG] NÃO contém R$ no texto!")
            print(f"[DEBUG] Preview: {full_text[:500]}")
        
        # ============================================
        # ESTRATÉGIA 1: Buscar em spans (texto junto)
        # ============================================
        blocks = page.get_text("dict")["blocks"]
        print(f"[DEBUG] Total de blocos: {len(blocks)}")
        
        for b in blocks:
            if "lines" not in b: 
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"]
                    text_lower = text.lower()
                    
                    # Verificar se contém indicador de preço
                    if "r$" in text_lower or self._looks_like_price(text):
                        print(f"[DEBUG] Span com preço: '{text}'")
                        match = self.price_regex.search(text)
                        if match:
                            print(f"[DEBUG] Regex match: '{match.group(0)}'")
                            result = self._process_price_match(page, s, match, markup, processed_rects)
                            if result:
                                count += 1
                                print(f"[DEBUG] Preço processado com sucesso!")
                        else:
                            print(f"[DEBUG] Regex NÃO casou com: '{text}'")
        
        # ============================================
        # ESTRATÉGIA 2: Buscar palavras adjacentes
        # (quando R$ está separado do número)
        # ============================================
        words = page.get_text("words")  # (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        
        for i, word in enumerate(words):
            word_text = word[4].strip().lower()
            
            # Se é "R$" ou "r$" sozinho
            if word_text in ["r$", "r$:", "r$."]:
                # Procurar próxima palavra na mesma linha
                if i + 1 < len(words):
                    next_word = words[i + 1]
                    
                    # Verificar se está na mesma linha (y similar)
                    if abs(word[1] - next_word[1]) < 10:  # Tolerância de 10pts
                        number_match = self.price_number_regex.search(next_word[4])
                        if number_match:
                            # Criar um span artificial combinando ambos
                            combined_rect = fitz.Rect(
                                word[0],      # x0 do R$
                                min(word[1], next_word[1]),  # y menor
                                next_word[2], # x1 do número
                                max(word[3], next_word[3])   # y maior
                            )
                            
                            # Verificar se já foi processado
                            if self._rect_already_processed(combined_rect, processed_rects):
                                continue
                            
                            # Extrair informações de estilo da área
                            original_text = f"R$ {next_word[4]}"
                            current_val = self._parse_price(original_text)
                            
                            if current_val > 0:
                                new_val = current_val + markup
                                new_text = self._format_price(new_val)
                                
                                # Obter cor de fundo e texto
                                bg_color = self._sample_background_color(page, combined_rect)
                                text_color = self._detect_text_color(page, combined_rect)
                                font_size = self._estimate_font_size(combined_rect)
                                
                                # Cobrir área original
                                page.draw_rect(combined_rect, color=None, fill=bg_color)
                                
                                # Inserir novo texto
                                page.insert_text(
                                    (combined_rect.x0, combined_rect.y1 - 2),
                                    new_text,
                                    fontsize=font_size,
                                    fontname="helv",
                                    color=text_color
                                )
                                
                                processed_rects.append(combined_rect)
                                count += 1
        
        # ============================================
        # ESTRATÉGIA 3: Buscar linhas completas
        # (fallback para layouts complexos)
        # ============================================
        lines = page.get_text("text").split('\n')
        for line in lines:
            if 'r$' in line.lower():
                all_matches = list(self.price_regex.finditer(line))
                for match in all_matches:
                    # Tentar localizar via search_for
                    full_price = match.group(0)
                    rects = page.search_for(full_price)
                    
                    for rect in rects:
                        if self._rect_already_processed(rect, processed_rects):
                            continue
                        
                        current_val = self._parse_price(full_price)
                        if current_val > 0:
                            new_val = current_val + markup
                            new_text = self._format_price(new_val)
                            
                            bg_color = self._sample_background_color(page, rect)
                            text_color = self._detect_text_color(page, rect)
                            font_size = self._estimate_font_size(rect)
                            
                            page.draw_rect(rect, color=None, fill=bg_color)
                            page.insert_text(
                                (rect.x0, rect.y1 - 2),
                                new_text,
                                fontsize=font_size,
                                fontname="helv",
                                color=text_color
                            )
                            
                            processed_rects.append(rect)
                            count += 1
        
        # ============================================
        # ESTRATÉGIA 4: Busca direta por "R$" e expansão
        # (para PDFs onde o texto está fragmentado)
        # ============================================
        # Buscar todas as ocorrências de "R$" diretamente
        rs_rects = page.search_for("R$")
        print(f"[DEBUG] Encontrado {len(rs_rects)} ocorrências de 'R$' via search_for")
        
        for rs_rect in rs_rects:
            if self._rect_already_processed(rs_rect, processed_rects, tolerance=20):
                continue
            
            # Expandir a área para a direita para capturar o número
            # Típico: R$ + espaço + número (até 8 chars como "1.234,56")
            expanded_rect = fitz.Rect(
                rs_rect.x0,
                rs_rect.y0 - 2,
                rs_rect.x0 + 150,  # Expandir 150pt para direita
                rs_rect.y1 + 2
            )
            
            # Extrair texto dessa área expandida
            text_in_area = page.get_text("text", clip=expanded_rect).strip()
            print(f"[DEBUG] Área expandida: '{text_in_area}'")
            
            if text_in_area:
                # Tentar encontrar preço no texto
                match = self.price_regex.search(text_in_area)
                if match:
                    full_price = match.group(0)
                    current_val = self._parse_price(full_price)
                    
                    print(f"[DEBUG] Preço encontrado: '{full_price}' = {current_val}")
                    
                    if current_val > 0:
                        new_val = current_val + markup
                        new_text = self._format_price(new_val)
                        
                        # Procurar o rect exato do preço completo
                        price_rects = page.search_for(full_price)
                        
                        for price_rect in price_rects:
                            if self._rect_already_processed(price_rect, processed_rects):
                                continue
                            
                            bg_color = self._sample_background_color(page, price_rect)
                            text_color = self._detect_text_color(page, price_rect)
                            font_size = self._estimate_font_size(price_rect)
                            
                            page.draw_rect(price_rect, color=None, fill=bg_color)
                            page.insert_text(
                                (price_rect.x0, price_rect.y1 - 2),
                                new_text,
                                fontsize=font_size,
                                fontname="helv",
                                color=text_color
                            )
                            
                            processed_rects.append(price_rect)
                            count += 1
                            print(f"[DEBUG] Preço atualizado via Estratégia 4!")
        
        print(f"[DEBUG] Total de preços atualizados: {count}")
        return count
    
    def _looks_like_price(self, text: str) -> bool:
        """Verifica se o texto parece um preço mesmo sem R$"""
        # Padrões comuns de preço
        return bool(self.price_number_regex.search(text))
    
    def _process_price_match(self, page, span, match, markup, processed_rects) -> bool:
        """Processa um match de preço encontrado em um span"""
        bbox = fitz.Rect(span["bbox"])
        
        # Verificar se já foi processado
        if self._rect_already_processed(bbox, processed_rects):
            return False
        
        old_price_str = match.group(0)
        val_str = match.group(1)
        
        current_val = self._parse_price(old_price_str)
        if current_val == 0.0:
            current_val = self._parse_price(val_str)
        
        if current_val <= 0:
            return False
        
        new_val = current_val + markup
        new_text = self._format_price(new_val)
        
        # Obter cores
        bg_color = self._sample_background_color(page, bbox)
        
        # Usar cor original do span se disponível
        text_color = self._extract_span_color(span)
        
        # Cobrir área original
        page.draw_rect(bbox, color=None, fill=bg_color)
        
        # Inserir novo texto mantendo estilo original
        page.insert_text(
            (bbox.x0, bbox.y1 - 2),
            new_text,
            fontsize=span["size"],
            fontname="helv",
            color=text_color
        )
        
        processed_rects.append(bbox)
        return True
    
    def _rect_already_processed(self, new_rect, processed_rects, tolerance=5) -> bool:
        """Verifica se um retângulo já foi processado (com tolerância)"""
        for rect in processed_rects:
            if (abs(rect.x0 - new_rect.x0) < tolerance and
                abs(rect.y0 - new_rect.y0) < tolerance and
                abs(rect.x1 - new_rect.x1) < tolerance and
                abs(rect.y1 - new_rect.y1) < tolerance):
                return True
        return False
    
    def _sample_background_color(self, page, rect) -> Tuple[float, float, float]:
        """Amostra a cor de fundo de uma área"""
        try:
            # Expandir ligeiramente para pegar o fundo
            sample_rect = fitz.Rect(rect.x0 - 5, rect.y0 - 5, rect.x1 + 5, rect.y1 + 5)
            pix = page.get_pixmap(clip=sample_rect, alpha=False)
            
            # Pegar pixel do canto (geralmente é fundo)
            r, g, b = pix.pixel(0, 0)
            return (r/255.0, g/255.0, b/255.0)
        except:
            return (1, 1, 1)  # Branco padrão
    
    def _detect_text_color(self, page, rect) -> Tuple[float, float, float]:
        """Tenta detectar a cor do texto na área"""
        try:
            pix = page.get_pixmap(clip=rect, alpha=False)
            
            # Coletar cores que parecem ser texto (diferente do fundo)
            bg_r, bg_g, bg_b = pix.pixel(0, 0)
            
            # Procurar por pixels que diferem significativamente do fundo
            for y in range(pix.height):
                for x in range(pix.width):
                    r, g, b = pix.pixel(x, y)
                    # Se a diferença for significativa, provavelmente é texto
                    diff = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
                    if diff > 100:
                        return (r/255.0, g/255.0, b/255.0)
            
            # Se não encontrou, usar cor contrastante
            bg_lum = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b
            return (0, 0, 0) if bg_lum > 128 else (1, 1, 1)
        except:
            return (0, 0, 0)  # Preto padrão
    
    def _extract_span_color(self, span) -> Tuple[float, float, float]:
        """Extrai a cor do span se disponível"""
        try:
            if "color" in span:
                color = span["color"]
                if isinstance(color, int):
                    # Cor em formato inteiro (RGB packed)
                    r = (color >> 16) & 0xFF
                    g = (color >> 8) & 0xFF
                    b = color & 0xFF
                    return (r/255.0, g/255.0, b/255.0)
                elif isinstance(color, (list, tuple)):
                    return tuple(c/255.0 if c > 1 else c for c in color[:3])
        except:
            pass
        return (0, 0, 0)  # Preto padrão
    
    def _estimate_font_size(self, rect) -> float:
        """Estima o tamanho da fonte baseado na altura do retângulo"""
        height = rect.height
        # Fonte geralmente é ~70-80% da altura do retângulo
        return max(8, min(72, height * 0.75))

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
