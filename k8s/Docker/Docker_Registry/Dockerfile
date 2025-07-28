FROM python:3.12.6

WORKDIR /app

COPY . .

RUN pip install flask bcrypt colorama

CMD ["python", "AD_Registry.py", "8082"]
