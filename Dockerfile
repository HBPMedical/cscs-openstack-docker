FROM ubuntu:latest

# $ docker build . -t crochat/cscs-pollux:latest -t crochat/cscs-pollux:1.0.6
# $ docker run --rm -it crochat/cscs-pollux:latest /bin/bash
# $ docker push crochat/cscs-pollux:latest
# $ docker push crochat/cscs-pollux:1.0.6

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
    lsb-core \
    curl \
    ruby \
    gem \
    gcc \
    g++ \
    && apt-get clean

RUN git clone https://github.com/crochat/cscs-openstack-cli /opt/openstack
RUN git clone https://github.com/crochat/vagrant-installer
RUN vagrant-installer/install_vagrant.sh -n
RUN rm -rf vagrant-installer
RUN cp $(find /root/.vagrant.d/gems -name Vagrantfile | grep vagrant-openstack-provider | head -1) /root/
COPY src/VBox.sh /usr/bin/
RUN ln -s VBox.sh /usr/bin/VBoxManage
RUN ln -s VBox.sh /usr/bin/vboxmanage

WORKDIR /code

COPY src/cscs_pollux_env.py /usr/lib/python3/dist-packages/
COPY src/openstack-cli /usr/local/bin/
COPY src/clouds* /etc/openstack/
COPY src/loadenv.sh /usr/local/bin/

CMD /usr/local/bin/loadenv.sh ; /bin/bash
