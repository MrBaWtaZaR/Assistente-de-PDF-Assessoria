
FROM python:3.10-slim

# Instalar dependências do sistema para o PyMuPDF e Flet
RUN apt-get update && apt-get install -y \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY . .

# Expor porta 7860 (Padrão Hugging Face Spaces)
EXPOSE 7860

# Configurar Flet para escutar na porta correta
ENV FLET_SERVER_PORT=7860
ENV FLET_FORCE_WEB_VIEW=true
ENV PYTHONPATH=/app/src

# Comando de inicialização
# Comando de inicialização
CMD ["python", "src/frontend/main_web.py"]
