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
    
    #upgrade version of pip
    pip3 install --upgrade pip
    
    #run yum update to update all libs 
    sudo yum update 
    sudo yum install git
    
    #install libraries to build the chip tool
    sudo yum install pkgconfig
    sudo yum install cairo cairo-devel
    sudo yum install gcc
    sudo yum install make
    sudo yum install pycairo
    sudo yum install python-devel
    sudo yum install python3-devel
    sudo yum install gobject-introspection-devel
    sudo yum install cairo-gobject-devel
    sudo yum install dbus-glib-devel
    sudo yum install dbus-devel
    sudo yum install dbus-python-devel
    sudo yum install dbus-glib-devel
    
    #Download and compile/install the openssl library from source
    mkdir /opt/openssl
    cd /opt/openssl
    wget https://www.openssl.org/source/openssl-1.1.0i.tar.gz
    tar -zxf openssl-1.1.0i.tar.gz
    cd openssl-1.1.0i
    ./config
    make
    sudo make install
    mv libcrypto.so.1.1 libssl.so.1.1 /usr/lib64/

    #install avahi for mmdns
    sudo yum install avahi-devel

    #install dbus-python
    pip install wheel
    pip install dbus-next
    pip install pydbus
    pip install dbus-python

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
