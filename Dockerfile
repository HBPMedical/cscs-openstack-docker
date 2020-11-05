FROM ubuntu:latest

# $ docker build . -t crochat/cscs-pollux:latest -t crochat/cscs-pollux:1.0.2
# $ docker run --rm -it crochat/cscs-pollux:latest /bin/bash
# $ docker push crochat/cscs-pollux:latest
# $ docker push crochat/cscs-pollux:1.0.2

RUN apt-get update --fix-missing \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    git \
    python3-nova \
    python3-glance \
    python3-swiftclient \
    python3-keystone \
    python3-neutron \
    python3-cinder \
    python3-ceilometer \
    python3-heat \
    && apt-get clean

RUN git clone https://github.com/crochat/cscs-openstack-cli /opt/openstack

WORKDIR /code

COPY src/cscs_pollux_env.py /usr/lib/python3/dist-packages/
COPY src/openstack-cli /usr/local/bin/

CMD [ "/bin/bash" ]
