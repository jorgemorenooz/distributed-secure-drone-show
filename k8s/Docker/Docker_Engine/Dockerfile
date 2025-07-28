FROM python:3.12.6

WORKDIR /app

COPY . .

RUN pip install kafka-python cryptography colorama requests bcrypt flask flask-cors watchdog

CMD ["python", "AD_Engine.py", "8081", "5", "kafka:9092"]