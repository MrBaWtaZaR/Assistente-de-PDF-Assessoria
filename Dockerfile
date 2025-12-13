FROM python:3.10-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário com ID 1000 (obrigatório para Hugging Face Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Criar diretórios com permissões
RUN mkdir -p /app/uploads /app/assets && chown -R user:user /app

# Copiar código com ownership correto
COPY --chown=user:user . .

# Garantir permissões
RUN chmod -R 777 /app/uploads /app/assets

# Mudar para usuário não-root
USER user

EXPOSE 7860

# VARIÁVEIS DE AMBIENTE CRÍTICAS PARA FLET WEB
ENV FLET_SERVER_PORT=7860
ENV FLET_FORCE_WEB_VIEW=true
ENV PYTHONPATH=/app/src
ENV HOME=/home/user
ENV FLET_UPLOAD_DIR=/app/uploads
ENV FLET_SECRET_KEY=my-secret-key-for-uploads

CMD ["python", "src/frontend/main_web.py"]
