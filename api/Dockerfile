FROM python:3.14-alpine

WORKDIR /api
COPY ./requirements.txt .

RUN pip install -r requirements.txt
COPY . /api
