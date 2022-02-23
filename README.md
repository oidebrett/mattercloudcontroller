# Matter Cloud Controller (Python)

The Matter Cloud Controller is a python based tool that allows you to commission a Matter device
(via the cloud) into the network and to communicate with it using the Zigbee Cluster Library
(ZCL) messages.

<hr>

-   [Building The Cloud Controller Tool](#building)

<hr>

<a name="building"></a>

## Building and installing

Before you can use the Matter cloud controller, you must install chip tool wheel package
from the NRFConnect SDK ConnectedHomeIp repository. The script below will do this automatically.

> To ensure compatibility, build the Matter Cloud controller and the Matter
> device from the same revision of the connectedhomeip repository.

To build and run the Matter Cloud controller:

1. Build and install the Python CHIP controller:

    ```
    scripts/build_controller.sh
    ```

    > Note: To get more details about available build configurations, run the
    > following command: `scripts/build_controller.sh --help`

<hr>

<a name="running"></a>

## Running the tool

1. Activate the Python virtual environment:

    ```
    source ./env/bin/activate
    ```
    
2. Install the NPM and Upgrade Node version if necessary (see https://www.digitalocean.com/community/tutorials/how-to-install-node-js-on-ubuntu-20-04)
    ```
    sudo apt install npm
    ```

3. Install Docker on the Raspberry Pi by following these instructions: https://brjapon.medium.com/setting-up-ubuntu-20-04-arm-64-under-raspberry-pi-4-970654d12696
    - install docker
    - install docker-compose

4. When bootstrapping CDK you may need to use flag --public-access-block-configuration if you AWS account is not permitted to make s3 public access buckets.

    ```
    --public-access-block-configuration false
    ```

5. Make changes to the docker image:

    ```
    #make a new environment
    mkdir /env 
    cd /env
    python3 -m venv .
    source /env/bin/activate
        
    #run yum update to update all libs 
    sudo yum update 
    
    #install libraries to build the chip tool
    #sudo yum groupinstall "Development Tools"
    sudo yum install gcc-c++
    sudo yum install git gcc make pkgconfig cairo cairo-devel pycairo \ 
    python-devel python3-devel gobject-introspection-devel cairo-gobject-devel \
    dbus-glib-devel dbus-devel dbus-python-devel dbus-glib-devel
    
    #install avahi for mmdns and bluez
    sudo yum install avahi-devel
    sudo yum install bluez

    #upgrade version of pip
    pip3 install --upgrade pip

    #install dbus-python
    #pip install wheel
    #pip install dbus-next
    #pip install pydbus
    pip install dbus-python
    
    #Download and install gcc 8:
    # Install required libraries
    sudo yum install libmpc-devel mpfr-devel gmp-devel

    # Gather source code
    export GCC_VERSION=9.3.0
    mkdir /opt/gcc
    cd /opt/gcc
    curl -o "gcc-${GCC_VERSION}.tar.gz" https://ftp.gnu.org/gnu/gcc/gcc-${GCC_VERSION}/gcc-${GCC_VERSION}.tar.gz
    tar xvzf "gcc-${GCC_VERSION}.tar.gz"
    rm gcc-${GCC_VERSION}.tar.gz
    cd gcc-${GCC_VERSION}

    # Configure and compile
    ./configure --with-system-zlib --disable-multilib --enable-languages=c,c++
    make -j 1

    # Install
    sudo make install
    mv /usr/lib64/libstdc++.so.6 /usr/lib64/libstdc++.so.6.old
    cp /usr/local/lib64/libstdc++.so.6 /usr/lib64/libstdc++.so.6


    #Download and compile/install the openssl library from source
    mkdir /opt/openssl
    cd /opt/openssl
    wget https://www.openssl.org/source/openssl-1.1.1.tar.gz
    tar -zxf openssl-1.1.1.tar.gz
    cd openssl-1.1.1
    ./config
    make
    sudo make install
    mv libcrypto.so.1.1 libssl.so.1.1 /usr/lib64/
    
    #download the chip tool wheel package
    mkdir /opt/chiptool/
    cd /opt/chiptool/
    wget https://github.com/nrfconnect/sdk-connectedhomeip/releases/download/v1.7.0/chip-tool-python_linux_release.zip
    unzip chip-tool-python_linux_release.zip
    
    #install the wheel package
    python3 -m pip install --force-reinstall --no-cache-dir chip-0.0-cp37-abi3-linux_x86_64.whl

    ```


4. Run the Matter Cloud controller with root privileges, which is required to
   obtain access to the Bluetooth interface:

    ```
    python3 local-chip-device-ctrl.py
    ```
