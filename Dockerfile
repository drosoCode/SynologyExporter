FROM python:3

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY main.py main.py
RUN chmod +x main.py

CMD ["/app/main.py"]