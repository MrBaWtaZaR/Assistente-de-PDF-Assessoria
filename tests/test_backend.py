
import fitz
import os
import sys
from PIL import Image

sys.path.append(os.path.join(os.getcwd(), 'src'))
from backend.pdf_processor import PdfProcessor

def create_sample_resources():
    # 1. Criar imagem logo
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save('tests/logo_test.png')
    
    # 2. Criar PDF com texto de preço e uma imagem placeholder
    doc = fitz.open()
    page = doc.new_page()
    
    # Texto
    page.insert_text((50, 50), "Produto Exemplo: R$ 10,00", fontsize=12)
    page.insert_text((50, 80), "Outro Preço: R$ 1.234,56", fontsize=12)
    
    # Imagem
    page.insert_image(fitz.Rect(100, 200, 300, 400), filename='tests/logo_test.png')
    
    doc.save('tests/sample.pdf')
    doc.close()

def test_processor():
    create_sample_resources()
    
    processor = PdfProcessor()
    input_pdf = 'tests/sample.pdf'
    output_pdf = 'tests/sample_processed.pdf'
    logo = 'tests/logo_test.png'
    markup = 5.00
    
    print("Iniciando processamento...")
    success, msg = processor.process_catalog(input_pdf, output_pdf, markup, logo)
    
    if not success:
        print(f"FAIL: {msg}")
        return

    print(f"SUCCESS: {msg}")
    
    # Verificar Resultados
    doc = fitz.open(output_pdf)
    page = doc[0]
    text = page.get_text()
    
    # Check Price 1: 10 + 5 = 15.00
    if "R$ 15,00" in text:
        print("PASS: Preço 1 atualizado corretamente.")
    else:
        print(f"FAIL: Preço 1 não encontrado. Texto extraído: {text}")

    # Check Price 2: 1234.56 + 5 = 1239.56
    if "R$ 1.239,56" in text:
        print("PASS: Preço 2 atualizado corretamente.")
    else:
        print(f"FAIL: Preço 2 não encontrado.")
        
    # Check Logo Count
    # Original tinha 1 imagem. Agora deve ter 2 (Original + Logo inserida sobre ela)
    # PyMuPDF 'get_images' lista references. Se inserimos a mesma imagem, pode reutilizar ref?
    # Mas insert_image normalmente cria nova ref ou usa stream.
    
    imgs = page.get_images()
    print(f"Imagens encontradas na página: {len(imgs)}")
    if len(imgs) >= 2:
        print("PASS: Logo inserida (contagem de imagens aumentou).")
    else:
        print("FAIL: Contagem de imagens não aumentou.")
        
    doc.close()

if __name__ == "__main__":
    test_processor()
