Linux kernel compile benchmarks kcbench and kcbenchrate
=======================================================

Kcbench and kcbenchrate are simple benchmarks scripts to measure how long it
takes to compile a Linux kernel.

Quickstart
----------

See INSTALL.md for the various ways to download and install the benchmarks. For
an ad hoc use this is all you need:

```
curl -O https://gitlab.com/knurd42/kcbench/-/raw/master/kcbench
bash kcbench
```

This will download and execute kcbench, which will do these things:

* Download and extract the sources of a suitable Linux kernel version to
  ~/.cache/kcbench/.
* Create a temporary directory like `/tmp/kcbench.xxxx`.
* Create a kernel configuration using `make O=/tmp/kcbench.xxxx defconfig`.
* Compile Linux using `make -j <number> O=/tmp/kcbench.xxxx vmlinux`; note,
  kcbench will try various values for `<number>`, as what works best depends
  on your machine.

In the end it will produce results that look like this:

```
[cttest@localhost ~]$ bash kcbench
Processor:           Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz [12 CPUs]
Cpufreq; Memory:     Unknown; 15934 MByte RAM
Linux running:       5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
Compiler used:       gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
Linux compiled:      5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
Config; Environment: defconfig; CCACHE_DISABLE="1"
Build command:       make vmlinux
Run 1 (-j 12):       92.55 seconds / 38.90 kernels/hour
Run 2 (-j 15):       91.91 seconds / 39.17 kernels/hour
Run 3 (-j 6):        113.66 seconds / 31.67 kernels/hour
Run 4 (-j 9):        101.32 seconds / 35.53 kernels/hour

```

Or this:

```
[cttest@localhost ~]$ bash kcbench
Processor:           AMD Ryzen Threadripper 3990X 64-Core Processor [128 CPUs]
Cpufreq; Memory:     Unknown; 15934 MByte RAM
Linux running:       5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
Compiler used:       gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
Linux compiled:      5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
Config; Environment: defconfig; CCACHE_DISABLE="1"
Build command:       make vmlinux
Run 1 (-j 128):      26.16 seconds / 137.61 kernels/hour
Run 2 (-j 136):      26.19 seconds / 137.46 kernels/hour
Run 3 (-j 64):       21.45 seconds / 167.83 kernels/hour
Run 4 (-j 72):       22.68 seconds / 158.73 kernels/hour
```

These two examples already show: the optimal number of jobs used to get the
best results depends on the machine, mainly its processor. For a more detailed
explanation of this and more example results that might look unexpected see the
[man page for kcbench](https://gitlab.com/knurd42/kcbench/-/raw/master/kcbench.man1.md).
There you'll also find recommendations to why you ideally want to use the same
operating system on all machines you want to compare -- and definitely must use
same compiler and Linux version.

Difference between kcbench and kcbenchrate
------------------------------------------

Kcbench won't max out a system while kcbenchrate will.

That's because kcbench tries to compile one kernel really quick. This is called
'speed run'. It will put a lot of load on your machine's processors,
nevertheless sometimes all CPU cores except one will idle for a while. That's
because a few parts of Linux' build process are single-threaded, among them
linking the kernel image (vmlinux).

Kcbenchrate is capable of keeping all CPU cores busy by starting one worker per
CPU core that compiles one kernel with one job ('-j 1') by default. This is
called 'rate run'. Note, this mode of operation takes a lot longer to generate
results and needs way more storage space.

For more details about these two approaches see the man pages linked below.

On a proper installation, kcbenchrate is installed in parallel to kcbench; if
you downloaded kcbench directly with curl for ad hoc use as outlined above, you
need to do this to run kcbenchrate:

```
ln -s kcbench kcbenchrate
bash kcbenchrate
```

Brief look
----------

To outline the potential of kcbench briefly, here is what a 'kcbench --help'
will show:

```
Usage: kcbench [options]

Compile a Linux kernel and measures the time it takes.

Available options:
 -b, --bypass                 -- bypass cache fill run and measure immediately
 -d, --detailed-results       -- print more detailed results
 -i, --iterations <int>       -- number or iterations to run for each job value
 -j, --jobs <int> (*)         -- number of jobs to use ('make -j #')
 -m, --modconfig              -- build using 'allmodconfig vmlinux modules'
 -k, --kconfig <file>         -- use <file> as kernel config (overrides -m)
 -o, --outputdir <dir>        -- compile in <dir>/kcbench/ ('make O=#')
 -q, --quiet                  -- quiet
 -s, --src (<version>|<dir>)  -- take Linux sources from <dir>; if not found
                                 try ~/.cache/kcbench/linux-<version>/ and
                                 /usr/share/kcbench/linux-<version>/; if still
                                 not found download <version> automatically.
 -v, --verbose (*)            -- increase verboselevel

     --add-make-args <str>    -- pass <str> to make call ('make <str> vmlinux')
     --cc <exec>              -- use specified target compiler ('CC=#')
     --cross-compile <arch>   -- cross compile for <arch>; supported archs:
                                 arm, arm64, powerpc, riscv, or x86_64
     --crosscomp-scheme <str> -- naming scheme for cross compiler
     --hostcc <exec>          -- use specified host compiler ('HOSTCC=#')
     --infinite               -- run endlessly
     --llvm                   -- sets 'LLVM=1' to use clang and LLVM tools
     --no-download            -- never download anything automatically
     --savefailedlogs <dir>   -- save log from failed compilations in <dir>

 -h, --help                   -- show this text
 -V, --version                -- output program version

(*) -- option can be passed multiple times

On this machine kcbench by default will use a Linux kernel 5.7 configured by
'make defconfig'. It first will compile this version using 'make -j 4 vmlinux'
for 2 times in a row; afterwards it will repeat this with 6, 2 jobs ('make
-j #') instead, to check if a different setting delivers better results
(see manpage for reasons why).

Note: defaults might change over time. Some of them also depend on your
machines configuration (like the number of CPU cores or the compiler being
used). Thus, hardcode these values when scripting kcbench.
```

For more details about kcbench and kcbenchrate and their command line options
see their man pages, which are shipped alongside and available online in
markdown:

* [Manpage for kcbench](https://gitlab.com/knurd42/kcbench/-/raw/master/kcbench.man1.md)
* [Manpage for kcbenchrate](https://gitlab.com/knurd42/kcbench/-/raw/master/kcbenchrate.man1.md)

Both mentioned a few caveats you should be aware of when comparing results
from different systems.

Requirements
------------

Kcbench and kcbenchrate will tell you if they need any additional tools or
libraries to perform their duty. But you can also install anything upfront if
you like:

 * On Arch Linux you should be able to install everything required by running
 this command:

 ```
sudo pacman --needed -S bc binutils bison curl flex gcc git kmod libelf make openssl perl procps-ng time
```

 * On Fedora you should be able to install everything required by running
 this command:

 ```
sudo dnf install /usr/bin/{bc,bison,curl,flex,gcc,ld,lscpu,make,time,openssl,perl,pkg-config,pkill} /usr/include/{libelf.h,openssl/pkcs7.h}
```

 * On Ubuntu this should do the trick:

 ```
sudo apt install bc binutils bison curl flex gcc libelf-dev libssl-dev make openssl perl-base pkg-config procps util-linux time
```

 * On openSUSE and SUSE Enterprise Linux this should install all requirements:

 ```
sudo zypper install bc binutils bison curl flex gawk gcc libelf-dev make openssl-devel  perl-base pkgconf-pkg-config procps time util-linux
```

License
-------

Kcbench and kcbenchrate were started by Thorsten Leemhuis and are available
under the MIT license – a permissive free software license which puts only
very limited restriction on reuse.
