FROM python:3.9-alpine

WORKDIR /api
COPY ./requirements.txt .

RUN pip install -r requirements.txt
COPY . /api

ENV WAIT_VERSION 2.7.3
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/${WAIT_VERSION}/wait /wait
RUN chmod +x /wait
