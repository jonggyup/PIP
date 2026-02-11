Running or installing kcbench & kcbenchrate
===========================================

There are various ways to run or install kcbench and kcbenchrate:


Ad hoc download and usage
-------------------------

The quickest way to get kcbench and kcbenchrate running is to download them
with a tool like curl or wget:

```
curl -O https://gitlab.com/knurd42/kcbench/-/raw/master/kcbench
chmod +x kcbench
ln -s kcbench kcbenchrate
./kcbench --help
./kcbenchrate --help
```

You'll get full functionality this way, but will lack the man pages. You
can read or download them here:

https://gitlab.com/knurd42/kcbench/-/raw/master/kcbench.man1.md
https://gitlab.com/knurd42/kcbench/-/raw/master/kcbenchrate.man1.md


Proper download and installation
--------------------------------

There are two ways to download the benchmarks properly:

* using git: `git clone https://gitlab.com/knurd42/kcbench.git`

* by downloading and extracting one of the tarballs on the projects release
page found at: https://gitlab.com/knurd42/kcbench/-/releases

In both cases you can immediately start using the benchmarks like this:

```
./kcbench
./kcbenchrate
```

To read the man pages look at the markdown source files kcbench.man1.md and
kcbenchrate.man1.md or the man pages generated from it:

```
man -l generated/kcbench.1
man -l generated/kcbenchrate.1
```

If you want you can install the kcbench and kcbenchrate as well as the man
pages and the README.md with make

```
make install
```

This will install the benchmarks to /usr/local/; add 'DESTDIR=/usr/' if you
want to install them to /usr/ instead.
