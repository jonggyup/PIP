% kcbenchrate(1) | User Commands

NAME
====

kcbenchrate - Linux kernel compile benchmark, rate edition (EXPERIMENTAL)

SYNOPSIS
========

| **kcbenchrate** \[**options**]

DESCRIPTION
===========

Kcbenchrate compiles a Linux kernel on each CPU core in parallel to test a
system's performance or stability.

Note: The number of compile jobs ('-j') and workers ('-w') that delivers the
best result depends on the machine being tested. See the section "ON THE DEFAULT
NUMBER OF JOBS AND WORKERS" below for details.

To get comparable results from different machines you need to use the exact
same operating system on all of them. There are multiple reasons for this
recommendation, but one of the main reasons is: the Linux version compiled
by default depends on the operating system's default compiler and both
heavily influence the result.

If you choose to ignore this recommendation at least make sure to hard code the
Linux version to compile ('-s 5.4'), as for example compiling 5.7 will take
longer than 5.4 or 4.19 and thus lead to results one cannot compare. Also, make
sure the compiler used on the systems you want to compare is from similar, as
for example gcc10 will try harder to optimize the code than gcc8 or gcc9 and
thus take more time for its work.

Kcbenchrate is accompanied by kcbench. Both are quite similar, but work slightly
different:

 * Kcbench tries to build one kernel as fast as possible. This approach is
   called 'speed run' and let's make start multiple jobs in parallel
   by using 'make -j #'. That way kcbench will use multiple CPU cores most of
   the time, except during those few phases where the Linux kernel build process
   is single threaded and thus utilizes just one CPU core. That for example is
   the case when vmlinux is linked.

 * Kcbenchrate tries to keep all CPU cores busy constantly by starting workers
   on all of them, where each builds one kernel with just one job ('make -j
   1'). This approach is called 'rate run'. It takes a lot longer to generate a
   result than kcbench and also needs a lot more storage space -- but will keep
   the CPU cores busy all the time.


Options
-------

**-b**, **--bypass**

:   After starting a worker wait just a tenths of a second before launching the
    next to start all the workers a lot faster than usually. This can he useful
    to create a lot of load quickly, but the benchmark result might be slightly
    inaccurate due to caching effects.


**-h**, **--help**

:   Show usage.


**-i**, **--iterations** _int_

:   Determines the number of kernels that each worker will compile before the
    end result it printed. Default: 2

**-j**, **--jobs** _int_

:   Number of jobs to use when compiling a kernel('make -j #').

    The default is '_1_'.


**-m**, **--modconfig**

:   Instead of using a config generated with 'defconfig' use one built by
    'allmodconfig' and compile modules as well. Takes a lot longer to compile,
    which is more suitable for machines with a lot of fast CPU cores.


**-k**, **--kconfig** _file_

:   Instead of using a config generated with 'defconfig' or 'allmodconfig' use
    _file_ as a base and complete it with 'olddefconfig'.
    This option overrides a possible **-m**/**--modconfig**.


**-o**, **--outputdir** _dir_

:   Use _path_ to compile Linux. Passes 'O=_dir_/kcbench-worker/' to make when
    calling it to compile a kernel. Without this, kcbenchrate will use a
    temporary directory.


**-s**, **--src** _path_|_version_

:   Look for sources in _path_, ~/.cache/kcbench/linux-_version_ or
    /usr/share/kcbench/linux-_version_. If not found try to download _version_
    automatically unless '--no-download' was specified.


**-v**, **--verbose**

:   Increase verbose level; option can be given multiple times.


**-w**, **--workers** _int_

:   Number of workers to use. Default: Number of CPUs. The optimal setting will
    depend on the particual machine. See ON THE DEFAULT NUMBER OF WORKERS for
    details.


**-V**, **--version**

:   Output program version.



**--cc _exec_**

:   Use _exec_ as target compiler.


**--cross-compile _arch_**

:   EXPERIMENTAL: Cross compile the Linux kernel. Cross compilers for this
    task are packaged in some Linux distribution. There are also pre-compiled
    compilers available on the internet, for example here:
    https://mirrors.edge.kernel.org/pub/tools/crosstool/

    Values of _arch_ that kcbench/kcbenchrate understand: arm arm64 aarch64
    riscv riscv64 powerpc powerpc64 x86_64

    Building for archs not directly supported by kcbench/kcbenchrate should
    work, too: just export ARCH= and CROSS_COMPILE= just like you would when
    normally cross compiling a Linux kernel. Do not use '--cross-compile' in
    that case.

    Be aware there is a bigger risk running into compile errors (see below) when
    cross compiling.

    Keep in mind that unless you provide a build configuration using
    '--kconfig', kcbench/kcbenchrate configure the compiled Linux kernel with
    the make target 'defconfig' (or 'allmodconfig', if you specify '-m'). That
    .config might be unusual for the architecture in question, but good enough
    for benchmarking purposes.


**--crosscomp-scheme _scheme_**

:   On Linux distributions that are known to ship cross compilers kcbench/
    kcbenchrate  will assume you want to use those. This parameter allows to
    specify one of the various different naming schemes in cases this automatic
    detection fails or work you want kcbench/kcbenchrate to find them using a
    'generic' scheme that should work with compilers from various sources, which
    is the default on unknown distributions.

    Valid values of _scheme_: debian fedora generic redhat ubuntu


**--hostcc _exec_**

:   Use _exec_ as host compiler.


**--infinite**

:   Run endlessly to create system load.


**--llvm**

:   Set LLVM=1 to use clang as compiler and LLVM utilities as GNU binutils
    substitute.


**--add-make-args _string_**

:   Pass additional flags found in _string_ to `make` when creating the config
    or building the kernel. This option is meant for experts that want to try
    unusual things, like specifying a special linker
    (`--add-make-args 'LD=ld.lld'`).

    Use with caution!


**--no-download**

:   Never download Linux kernel sources from the web automatically.


**--savefailedlogs _path_**

:   Save log of failed compile runs to _path_.



ON THE DEFAULT NUMBER OF JOBS AND WORKERS
=========================================

The optimal number of workers (-w) in most cases will be identical to the
number of CPU cores in the tested machine, that's why this is the default.
But some systems might be a bit faster if they are oversubscribed a little with
additional workers or a higher number ob jobs per worker. Others might be
quicker if you only utilize the real CPU cores and let the cores idle which are
only available due to SMT (Simultaneous Multi-Threading, also called
Hyper-threading/HT by Intel).

For details and some results that show unexpected effects see the kcbench man
page's section 'ON THE DEFAULT NUMBER OF JOBS'.

Ideally kcbenchrate would do what kcbench does and try a few settings to narrow
down the optimal setting. As this would take quite a while this exercise is
left to the user. Impatient users should consider finding the optimal number of
jobs with kcbench and then try to start kernbenchrate with as many workers, as
it might be a good setting for it as well. You can also try to experiment with
the number of jobs used per worker (-j), maybe some machines perform best if
you start worker on every second core, but use 2 jobs per worker.


ON FAILED RUNS DUE TO COMPILATION ERRORS
========================================

The compilation is unlikely to fail, as long as you are using a settled GCC
version to natively compile the source of a current Linux kernel for popular
architectures like ARM, ARM64/Aarch64, or x86_64. For other cases there is a
bigger risk that compilation will fail due to factors outside that
kcbench/kcbenchrate cannot control. They nevertheless try to catch a few common
problems and warn, but they can not catch them all, as there are to many
factors involved:

 * Brand new compiler generations are sometimes stricter than their predecessors
and thus might fail to compile even the latest Linux kernel version. You might
need to use a pre-release version of the next Linux kernel release to make it
work or simply need to wait until the compiler or kernel developers solve the
problem.

 * Distributions enable different compiler features that might have an impact on
the kernel compilation. For example GCC9 was capable of compiling Linux 4.19 on
many distributions, but started to fail on Ubuntu 19.10 due to a GCC feature the
distribution enabled. Try compiling a newer Linux kernel version in such a case.

 * Cross compilation increases the risk of running into compile problems in
general, as there are many compilers and architectures out there. That for
example is why compiling the Linux kernel for an unpopular architecture is more
likely to fail due to bugs in the compiler or the Linux kernel sources that
nobody had noticed before when the compiler or kernel was released. This is even
more likely to happen if you start kcbench/kcbenchrate with '-m/--allmodconfig'
to build a more complex kernel.


HINTS
=====

Running benchmarks to compare the results fairly can be tricky. Here are a few
of the aspects you should keep mind when trying to do so:

 * Do not compare results from two different architectures (like ARM64 and
x86_64): kcbench/kcbenchrate compile different code in that case, as they will
compile a native kernel on each of those architectures. This can be avoided by
cross compiling for a third architecture that is not related to any of the
architectures compared (say RISC-V when comparing ARM64 and x86_64).

 * Unless you want to benchmark compiler effects, do not compare results from
different compiler generations. For example to not compare results from GCC7 and
GCC9, as the later optimizes harder and thus will take more time. Newer compiler
generations often are also stricter, which is why they often uncover bugs in the
Linux kernel source that need to be fixed for compiling to succeed -- which is
why the Linux version kcbenchrate compiles by default depends on the compiler.

 * Compiling a Linux kernel scales very well and thus can utilize processors
quite well. But be aware that some parts of the Linux compile process will only
use one thread (and thus one CPU core), for example when linking vmlinuz; the
other cores idle meanwhile. The effect on the result will grow with the
number of CPU cores.

 If you want to work against that consider using '-m' to build an allmodconfig
configuration with modules; comping a newer, more complex Linux kernel version
can also help. But the best way to avoid this effect is by running kcbenchrate.

 * Kcbench/kcbenchrate by default set CCACHE_DISABLE=1 when calling 'make' to
avoid interference from ccache.


EXAMPLES
========

To let kcbenchrate decide everything automatically simply run:

:      $ kcbenchrate


RESULTS
=======

By default the line you are looking for is this:

   4 workers completed 8 kernels so far (avrg: 1100.75 s/run) with a rate of 13.08 kernels/hour.

On this quad-core processor four workers each compiled two kernels. On average,
it took each worker 1100.77 seconds to compile one kernel image. With a speed
like this the machine can compile 13.08 kernels per hour (3600/1100.75*4).


MISSING FEATURES
================

* kcbenchrate lacks something similar to 'kcbench --detailedresults'

* kcbenchrate takes the results verbatim and does not validate them for
  saneness. Thus, if for example there is some hiccup in the system that heavily
  slows down one worker temporary kcbenchrate will neither notice nor tell you.


SEE ALSO
========
**kcbench(1)**, **time(1)**


AUTHOR
======
Thorsten Leemhuis <linux [AT] leemhuis [DOT] info>
