FROM python:3.11

RUN apt-get update && apt-get install --yes graphviz=10.0.1

COPY requirements.txt requirements.txt

COPY app.py app.py

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir --upgrade -r requirements.txt

ENTRYPOINT ["solara", "run", "app.py", "--host=0.0.0.0", "--port=80"]
