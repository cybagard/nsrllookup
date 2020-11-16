FROM python:3.9

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /tmp

RUN git clone https://github.com/cybagard/nsrlsvr .
RUN apt-get update && apt-get install -y --no-install-recommends cmake libboost-all-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
RUN P3=$(which python3) && cmake -DPYTHON_EXECUTABLE=$P3 .
RUN make && make install

COPY prepare-hash-set.sh /prepare-hash-set.sh
RUN chmod +x /prepare-hash-set.sh

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]