FROM python:3.9

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /tmp

RUN git clone https://github.com/cybagard/nsrlsvr .
RUN apt-get update && apt-get -y install cmake libboost-all-dev
RUN cmake -DPYTHON_EXECUTABLE=`which python3` .
RUN make && make install

COPY prepare-hash-set.sh /prepare-hash-set.sh
RUN chmod +x /prepare-hash-set.sh

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]