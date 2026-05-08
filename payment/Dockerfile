FROM python:3.11-slim

ENV TZ=Europe/Tallinn

WORKDIR /app

COPY ./payment/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "python ${PYTHONFILE}"]