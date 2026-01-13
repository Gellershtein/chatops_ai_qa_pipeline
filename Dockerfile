
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
LABEL cache_buster="1768288862"
RUN pip install -r requirements.txt
COPY . .
