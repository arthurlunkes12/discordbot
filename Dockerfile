# 1️⃣ Usa uma imagem oficial do Python como base
FROM python:3.12

# 2️⃣ Define o diretório de trabalho no container
WORKDIR /app

# 3️⃣ Copia os arquivos do projeto para o container
COPY . .

# 4️⃣ Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# 5️⃣ Comando para rodar o bot
CMD ["python", "botdisc.py"]
