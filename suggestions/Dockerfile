FROM python:3.11

ENV TZ=Europe/Tallinn

WORKDIR /app

COPY ./suggestions/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# hot reload applications
CMD python utils/other/hotreload.py "suggestions/src/app.py"