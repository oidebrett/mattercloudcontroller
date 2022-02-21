#!/usr/bin/env bash

#
# Copyright (c) 2022 MatterCloudController Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

set -e

_normpath() {
    python -c "import os.path; print(os.path.normpath('$@'))"
}

echo_green() {
    echo -e "\033[0;32m$*\033[0m"
}

echo_blue() {
    echo -e "\033[1;34m$*\033[0m"
}

echo_bold_white() {
    echo -e "\033[1;37m$*\033[0m"
}

MATTER_ROOT=$(_normpath "$(dirname "$0")/..")
ENVIRONMENT_ROOT="$MATTER_ROOT/env"
OUTPUT_ROOT="$MATTER_ROOT/python_lib"

declare chip_version="v1.7.0"
declare force_reinstall=0
declare force_reinstall_flag=""

help() {

    echo "Usage: $file_name [ options ... ] [ -chip_version ChipVersion  ] [ -forcereinstall Value  ] "

    echo "General Options:
  -h, --help                Display this information.
Input Options:
  -c, --chip_version ChipVersion          Specify ChipVersion e.g. v1.7.0
                                                            By default it is v1.7.0 
  -f, --forcereinstall Value         Specify whether to force the reinstall of the chip wheel package 
                                                            By default it is 0 
"
}

file_name=${0##*/}

while (($#)); do
    case $1 in
        --help | -h)
            help
            exit 1
            ;;
        --chip_version | -c)
            chip_version=$2
            shift
            ;;
        --forcereinstall | -f)
            force_reinstall=$2
            shift
            ;;
        -*)
            help
            echo "Unknown Option \"$1\""
            exit 1
            ;;
    esac
    shift
done

# Print input values
echo "Input values: chip_version = $chip_version"

CHIP_WHEEL_BASE_URL="https://github.com/nrfconnect/sdk-connectedhomeip/releases/download"
CHIP_WHEEL_VERSION=$chip_version
CHIP_WHEEL_FILENAME="chip-tool-python_linux_release.zip"
CHIP_WHEEL_URL="$CHIP_WHEEL_BASE_URL/$CHIP_WHEEL_VERSION/$CHIP_WHEEL_FILENAME"

echo ""
echo_green "Using WHL package from: "
echo_blue "  $CHIP_WHEEL_URL"

if [ ! -f $OUTPUT_ROOT/$CHIP_WHEEL_FILENAME ]
then
	echo_green "Wheel library not found. Downloading to $OUTPUT_ROOT"
	# Download the latest version of library
	wget -P $OUTPUT_ROOT $CHIP_WHEEL_URL 
fi

#Unzip file 
unzip $OUTPUT_ROOT/$CHIP_WHEEL_FILENAME -d $OUTPUT_ROOT


# Activate the new environment to register the python WHL

WHEEL=$(ls "$OUTPUT_ROOT"/chip-*.whl | head -n 1)

if [ "$force_reinstall" == 1 ]; then
	force_reinstall_flag=="--force-reinstall"
fi

echo "$ENVIRONMENT_ROOT"/bin/pip install --upgrade $force_reinstall_flag --no-cache-dir "$WHEEL"

source "$ENVIRONMENT_ROOT"/bin/activate
"$ENVIRONMENT_ROOT"/bin/python -m pip install --upgrade pip
"$ENVIRONMENT_ROOT"/bin/pip install --upgrade $forcere_install_flas --no-cache-dir "$WHEEL"
"$ENVIRONMENT_ROOT"/bin/pip install awscli --upgrade 
"$ENVIRONMENT_ROOT"/bin/pip install aws-cdk-lib --upgrade


echo ""
echo_green "Compilation completed and WHL package installed in: "
echo_blue "  $ENVIRONMENT_ROOT"

echo ""
echo_green "To activate the virtual  env please run:"
echo_bold_white "  source $ENVIRONMENT_ROOT/bin/activate"
