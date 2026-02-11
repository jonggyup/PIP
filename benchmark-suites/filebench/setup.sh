#!/bin/bash
libtoolize
aclocal
autoheader
automake --add-missing
autoconf

./configure
make
sudo make install
