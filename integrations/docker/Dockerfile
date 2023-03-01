# Stage 1: Setup dependencies (based on chip-build).
FROM ubuntu:22.04 as chip-build-cert
ARG TARGETPLATFORM="linux/amd64"
# COMMITHASH defines the target commit to build from. May be passed in using --build-arg.
ARG COMMITHASH=072efd5f2449df025f35c2d6d7ae3750abfcd54b
ARG MCCCOMMITHASH=d11250f86f85ceb99a246a7dc076d9e30e949bb9

# ZAP Development install, so that it runs on both x64 and arm64
# Generally this should match with the ZAP version that is used for codegen within the
# specified SHA
ARG ZAP_VERSION=v2023.02.16-nightly

# Ensure TARGETPLATFORM is set
RUN case ${TARGETPLATFORM} in \
        "linux/amd64") \
            echo "Building for linux/amd64" \
        ;; \
        "linux/arm64") \
            echo "Building for linux/arm64" \
        ;; \
        *) \
        if [ -z "$TARGETPLATFORM" ] ;\
        then \
            echo "TARGETPLATFORM not defined! Please run from buildkit (buildx)." \
        && return 1 ;\
        else \
            echo "Unsupported platform ${TARGETPLATFORM}." \
        && return 1 ;\
        fi \
        ;; \
    esac

# Below should be the same as chip-build except arm64 logic for cmake and node.

# base build and check tools and libraries layer
RUN set -x \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -fy \
    autoconf \
    automake \
    bison \
    bridge-utils \
    clang \
    clang-format \
    clang-tidy \
    curl \
    flex \
    g++ \
    git \
    gperf \
    iproute2 \
    jq \
    lcov \
    libavahi-client-dev \
    libavahi-common-dev \
    libcairo2-dev \
    libdbus-1-dev \
    libdbus-glib-1-dev \
    libgif-dev \
    libglib2.0-dev \
    libical-dev \
    libjpeg-dev \
    libdmalloc-dev \
    libmbedtls-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libnspr4-dev \
    libpango1.0-dev \
    libpixman-1-dev \
    libreadline-dev \
    libssl-dev \
    libtool \
    libudev-dev \
    libusb-1.0-0 \
    libusb-dev \
    libxml2-dev \
    make \
    net-tools \
    ninja-build \
    openjdk-8-jdk \
    pkg-config \
    python3 \
    python3-dev \
    python3-venv \
    rsync \
    shellcheck \
    strace \
    systemd \
    udev \
    unzip \
    wget \
    git-lfs \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/ \
    && git lfs install \
    && : # last line

# Cmake (Mbed OS requires >=3.19.0-rc3 version which is not available in Ubuntu 20.04 repository)
RUN case ${TARGETPLATFORM} in \
        "linux/amd64") \
            set -x \
            && (cd /tmp \
            && wget --progress=dot:giga https://github.com/Kitware/CMake/releases/download/v3.19.3/cmake-3.19.3-Linux-x86_64.sh \
            && sh cmake-3.19.3-Linux-x86_64.sh --exclude-subdir --prefix=/usr/local \
            && rm -rf cmake-3.19.3-Linux-x86_64.sh) \
            && exec bash \
            ;; \
        "linux/arm64") \
            set -x \
            && (cd /tmp \
            && wget --progress=dot:giga https://github.com/Kitware/CMake/releases/download/v3.19.3/cmake-3.19.3-Linux-aarch64.sh \
            && sh cmake-3.19.3-Linux-aarch64.sh --exclude-subdir --prefix=/usr/local \
            && rm -rf cmake-3.19.3-Linux-aarch64.sh) \
            && exec bash \
            ;; \
        *) \
        test -n "$TARGETPLATFORM" \
        echo "Unsupported platform ${TARGETPLATFORM}" \
    ;; \
    esac

# Python 3 and PIP
RUN set -x \
    && DEBIAN_FRONTEND=noninteractive  apt-get update \
    && DEBIAN_FRONTEND=noninteractive  apt-get install -y libgirepository1.0-dev \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common \
    && add-apt-repository universe \
    && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3 get-pip.py \
    && rm -rf /var/lib/apt/lists/ \
    && : # last line

RUN set -x \
    && pip3 install attrs coloredlogs PyGithub pygit future portpicker mobly click cxxfilt ghapi pandas tabulate \
    && : # last line

# build and install gn
RUN set -x \
    && git clone https://gn.googlesource.com/gn \
    && cd gn \
    && python3 build/gen.py \
    && ninja -C out \
    && cp out/gn /usr/local/bin \
    && cd .. \
    && rm -rf gn \
    && : # last line

# Install bloat comparison tools
#RUN set -x \
#    && git clone https://github.com/google/bloaty.git \
#    && mkdir -p bloaty/build \
#    && cd bloaty/build \
#    && cmake ../ \
#    && make -j8 \
#    && make install \
#    && cd ../.. \
#    && rm -rf bloaty \
#    && : # last line

# NodeJS: install a newer version than what apt-get would read
# This installs the latest LTS version of nodejs
RUN case ${TARGETPLATFORM} in \
        "linux/amd64") \
            set -x \
            && mkdir node_js \
            && cd node_js \
            && wget https://nodejs.org/dist/v12.22.12/node-v12.22.12-linux-x64.tar.xz \
            && tar xfvJ node-v12.22.12-linux-x64.tar.xz \
            && mv node-v12.22.12-linux-x64 /opt/ \
            && ln -s /opt/node-v12.22.12-linux-x64 /opt/node \
            && ln -s /opt/node/bin/* /usr/bin \
            && cd .. \
            && rm -rf node_js \
            ;; \
        "linux/arm64")\
            set -x \
            && mkdir node_js \
            && cd node_js \
            && wget https://nodejs.org/dist/v12.22.12/node-v12.22.12-linux-arm64.tar.xz \
            && tar xfvJ node-v12.22.12-linux-arm64.tar.xz \
            && mv node-v12.22.12-linux-arm64 /opt/ \
            && ln -s /opt/node-v12.22.12-linux-arm64 /opt/node \
            && ln -s /opt/node/bin/* /usr/bin \
            && cd .. \
            && rm -rf node_js \
            ;; \
        *) ;; \
    esac

RUN set -x \
    && mkdir -p /opt/zap-${ZAP_VERSION} \
    && git clone https://github.com/project-chip/zap.git /opt/zap-${ZAP_VERSION} \
    && cd /opt/zap-${ZAP_VERSION} \
    && git checkout ${ZAP_VERSION} \
    && npm config set user 0 \
    && npm ci
ENV ZAP_DEVELOPMENT_PATH=/opt/zap-${ZAP_VERSION}

# Stage 1.5: Bootstrap Matter.
RUN mkdir /home/ggc_user
RUN mkdir /home/ggc_user/connectedhomeip
RUN git clone https://github.com/project-chip/connectedhomeip.git /home/ggc_user/connectedhomeip
WORKDIR /home/ggc_user/connectedhomeip/
RUN git checkout ${COMMITHASH}
RUN ./scripts/checkout_submodules.py --shallow --platform linux
RUN scripts/build/gn_bootstrap.sh
SHELL ["/bin/bash", "-c"]
RUN set -x && \
    source scripts/activate.sh \
    && gn gen out/debug --args='chip_mdns="platform" chip_inet_config_enable_ipv4=false' \
    && ninja -C out/debug

from chip-build-cert as chip-build-cert-bins

SHELL ["/bin/bash", "-c"]

# Records Matter SDK commit hash to include in the image.
RUN git rev-parse HEAD > /home/ggc_user/.sdk-sha-version

RUN source scripts/activate.sh && scripts/build_python.sh -m platform -d true -i no

# Set Up Matter Cloud Controller.
RUN mkdir /home/ggc_user/mattercloudcontroller
ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
RUN git clone https://github.com/oidebrett/mattercloudcontroller.git /home/ggc_user/mattercloudcontroller
#ARG MCCCOMMITHASH=d69694783bbfff4222f0c3d9312a539f3ab48c3a
WORKDIR /home/ggc_user/mattercloudcontroller/
RUN git rev-parse HEAD > /home/ggc_user/.matter-sha-version
RUN git checkout ${MCCCOMMITHASH}
#RUN git checkout main 


# Stage 3: Copy relevant cert bins to a minimal image to reduce size.
# After this we are using a different image so we need to copy things from the previous stage image
FROM ubuntu:22.04
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update -y
RUN apt-get install -y libssl-dev libdbus-1-dev libglib2.0-dev libavahi-client-dev avahi-utils iproute2 libcairo2-dev libgirepository1.0-dev python3-pip

# First we will make a new user that will run greengrass (and own the connectedhomeip dir)
## Setup user
ARG USERNAME=ggc_user
ARG GROUPNAME=ggc_group
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    #
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

## Rename tempuser user to ggc_user and create home folder
RUN usermod -l $USERNAME -d /home/$USERNAME -m $USERNAME
RUN groupmod --new-name $GROUPNAME $USERNAME

# [Optional] Set the default user. Omit if you want to keep the default as root.
#USER $USERNAME

WORKDIR /home/$USERNAME/
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/.sdk-sha-version .sdk-sha-version

# Stage 3.1 Setup the Matter Python environment
#COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/connectedhomeip connectedhomeip

#Below is the right fine-grained copys that we need - we will make a note for now
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/connectedhomeip/credentials connectedhomeip/credentials
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/connectedhomeip/out connectedhomeip/out
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/connectedhomeip/scripts connectedhomeip/scripts
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/connectedhomeip/.environment connectedhomeip/.environment

RUN pip install --no-cache-dir connectedhomeip/out/python_lib/controller/python/chip*.whl

# Stage 4: Set Up Matter Cloud Controller.
#COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/mattercloudcontroller/scripts/thing mattercloudcontroller/scripts/thing
COPY --from=chip-build-cert-bins --chown=$USERNAME:$GROUPNAME /home/ggc_user/mattercloudcontroller mattercloudcontroller 

#Stage 5: Set up the Greengrass v2 environment

## Clean apt cache
RUN apt-get clean && apt-get autoremove && rm -rf /var/lib/apt/lists/*

## Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  jq unzip && \
  apt-get clean && apt-get autoremove && rm -rf /var/lib/apt/lists/*

## Install greengrassv2 dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  default-jdk-headless sudo python3 tar unzip wget procps \
  ca-certificates curl gnupg lsb-release && \
  apt-get clean && apt-get autoremove && rm -rf /var/lib/apt/lists/*

## Set up the entrypoint
RUN chmod +x /home/ggc_user/mattercloudcontroller/scripts/thing/install-gg-thing.sh
ENTRYPOINT ["/home/ggc_user/mattercloudcontroller/scripts/thing/install-gg-thing.sh"]

## Setup user
WORKDIR /home/ggc_user
USER ggc_user:ggc_group

