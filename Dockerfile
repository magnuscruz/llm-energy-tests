FROM python:3.10-slim

# Definir o diretório de trabalho
WORKDIR /app

# Copiar os ficheiros de dependências primeiro (otimiza o cache do Docker)
COPY src/requirements.txt src/requirements.txt

# Atualizar o pip e instalar as dependências
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r src/requirements.txt

# Copiar o restante código para o contentor
COPY . .

# Expor a porta standard do Cloud Run
EXPOSE 8080

# Comando para iniciar o Streamlit na porta correta apontando para o teu dashboard
CMD ["streamlit", "run", "src/build_dashboard.py", "--server.port=8080", "--server.address=0.0.0.0"]