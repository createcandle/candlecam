#!/bin/bash -e

echo "whoami?:"
whoami

echo
echo "users:"
cat /etc/passwd

echo
echo "in package.sh. pwd:"
pwd
echo
echo "which python3:"
which python3
echo "which pip3:"
which pip3
echo
echo "glibc version:"
ldd --version

echo
#echo "Upgrading pip:"
#pip3 install --user --upgrade pip
#python3 -m pip install --upgrade pip
#/usr/local/bin/python3.9 -m pip install --upgrade pip

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

export PYTHONIOENCODING=utf8
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH="$HOME/.local/lib:/root/.local/bin:/usr/local/lib:$LD_LIBRARY_PATH" LIBRARY_PATH="$HOME/.local/lib/" CFLAGS="-I$HOME/.local/include"

echo
echo "setting up environment variables for dockerized toolchain"
# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

if [ -z "${ADDON_ARCH}" ]; then
  TARFILE_SUFFIX=
else
  PYTHON_VERSION="$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d. -f 1-2)"
  TARFILE_SUFFIX="-${ADDON_ARCH}-v${PYTHON_VERSION}"
fi

# Clean up from previous releases
echo "removing old files"
rm -rf *.tgz *.shasum package SHA256SUMS lib

# Prep new package
echo " "
echo "creating package"
mkdir -p lib package

# This helps skip a compilation check in picamera
export READTHEDOCS=True 
export NOGUI="1"

#apt-get update -y

# installing rust doesn't work, the process is interactive:
#curl https://sh.rustup.rs -sSf | sh
#apt install cmake build-essential libssl-dev ninja-build libcap-dev libpcap-dev -y

#NOGUI=1 pip3 install picamera2
#wget http://ftp.nl.debian.org/debian/pool/main/libc/libcap2/libcap-dev_2.44-1_armhf.deb
#dpkg -i libcap-dev_2.44-1_armhf.deb
echo
echo "installing numpy"
apt update
apt install python3-numpy -y

#pip3 install py-build-cmake
#pip3 install numpy
#pip3 install python-prctl
#pip3 install --upgrade libpcap PiDNG piexif pillow simplejpeg v4l2-python3 python-prctl
#pip3 install --upgrade --no-deps picamera2

echo
echo "installing requirements (except PiDNG)"
echo
#pip3 install -r requirements.txt -t lib --no-binary :all: --prefix "" #--default-timeout=100
#pip3 install PiDNG -t lib --no-deps --no-binary :all: --prefix "" 

pip3 install -r requirements.txt -t lib --no-binary :all: --prefix "" #--default-timeout=100

echo
echo "installing PiDNG"
pip3 install PiDNG -t lib --no-deps --no-binary :all: --prefix "" -v --no-build-isolation


#echo
#echo "install picamera2"
#pip3 install -r picamera2 -t lib  --no-deps --no-binary :all: --prefix ""

# Remove local cffi so that the globally installed version doesn't clash
rm -rf ./lib/cffi*

# Put package together
cp -r lib pkg LICENSE manifest.json *.py README.md sounds css js images views package/
find package -type f -name '*.pyc' -delete
find package -type f -name '._*' -delete
find package -type d -empty -delete

# Generate checksums
echo "generating checksums"
cd package
find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
cd -

# Make the tarball
echo "creating archive"
TARFILE="candlecam-${version}${TARFILE_SUFFIX}.tgz"
tar czf ${TARFILE} package

# create shasum of final tar
echo "creating shasum of final tar archive"
shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum
