% kcbench(1) | User Commands

NAME
====

kcbench - Linux kernel compile benchmark, speed edition

SYNOPSIS
========

| **kcbench** \[**options**]

DESCRIPTION
===========

Kcbench tries to compile a Linux kernel really quickly to test a system's
performance or stability.

Note: The number of compile jobs ('-j') that delivers the best result depends
on the machine being tested. See the section "ON THE DEFAULT NUMBER OF JOBS"
below for details.

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

Kcbench is accompanied by kcbenchrate. Both are quite similar, but work slightly
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

:   Omit the initial kernel compile to fill caches; saves time, but the first
    result might be slightly lower than the following ones.


**-d**, **--detailedresults**

:   Print more detailed results.


**-h**, **--help**

:   Show usage.


**-i**, **--iterations** _int_

:   Determines the number of kernels that kcbench will compile sequentially with
    different values of jobs ('-j'). Default: 2


**-j**, **--jobs** _int_(,_int_, _int_, ...)

:   Number of jobs to use when compiling a kernel('make -j #').

    This option can be given multiple times (-j 2 -j 4 -j 8) or '_int_' can be a
    list (-j "2 4 8"). The default depends on the number of cores in the system
    and if its processor uses SMT. Run '--help' to query the default on the
    particular machine.

    Important note: kcbench on machines with SMTs will do runs which do not
    utilize all available CPU cores; this might look odd, but there are reasons
    for this behavior. See "ON THE DEFAULT NUMBER OF JOBS" below for details.


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
    calling it to compile a kernel. Without this, kcbench will use a temporary
    directory.


**-s**, **--src** _path_|_version_

:   Look for sources in _path_, ~/.cache/kcbench/linux-_version_ or
    /usr/share/kcbench/linux-_version_. If not found try to download _version_
    automatically unless '--no-download' was specified.


**-v**, **--verbose**

:   Increase verbose level; option can be given multiple times.



**-V**, **--version**

:   Output program version.



**--cc _exec_**

:   Use _exec_ as target compiler.


**--cross-compile _arch_**

:   EXPERIMENTAL: Cross compile the Linux kernel. Cross compilers for this
    task are packaged in some Linux distribution. There are also pre-compiled
    compilers available on the internet, for example here:
    https://mirrors.edge.kernel.org/pub/tools/crosstool/

    Values of _arch_ that kcbench understand: arm arm64 aarch64 riscv riscv64
    powerpc powerpc64 x86_64

    Building for archs not directly supported by kcbench should work, too: just
    export ARCH= and CROSS_COMPILE= just like you would when normally cross
    compiling a Linux kernel. Do not use '--cross-compile' in that case.

    Be aware there is a bigger risk running into compile errors (see below) when
    cross compiling.

    Keep in mind that unless you provide a build configuration using
    '--kconfig', kcbench configure the compiled Linux kernel with the make
    target 'defconfig' (or 'allmodconfig', if you specify '-m'). That .config
    might be unusual for the architecture in question, but good enough for
    benchmarking purposes.


**--crosscomp-scheme _scheme_**

:   On Linux distributions that are known to ship cross compilers kcbench
    will assume you want to use those. This parameter allows to specify one of
    the various different naming schemes in cases this automatic detection fails
    or work you want kcbench/kcbenchrate to find them using a 'generic' scheme
    that should work with compilers from various sources, which is the default
    on unknown distributions.

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



ON THE DEFAULT NUMBER OF JOBS
=============================

The optimal number of compile jobs (-j) to get the best result depends on the
machine being benched. On most systems you will achieve the best result if the
number of jobs matches the number of CPU cores. That for example is the case on
this 4 core Intel processor without SMT:

    [cttest@localhost ~]$ bash kcbench -s 5.3 -i 1
    Processor:            Intel(R) Core(TM) i5-4570 CPU @ 3.20GHz [4 CPUs]
    Cpufreq; Memory:      Unknown; 15934 MByte RAM
    Compiler used:        gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
    Linux compiled:       5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
    Config; Environment:  defconfig; CCACHE_DISABLE="1"
    Build command:        make vmlinux
    Run 1 (-j 4):         250.03 seconds / 14.40 kernels/hour
    Run 2 (-j 6):         255.88 seconds / 14.07 kernels/hour


The run with 6 jobs was slower here. That kcbench tries that setting by default
looks like a waste of time here, but is wise, as other machines deliver the best
result when they are oversubscribed a little. That for example is the case on
this 6 core/12 threads processor, which achieved its best result with 15 jobs:

    [cttest@localhost ~]$ bash kcbench -s 5.3 -i 1
    Processor:            Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz [12 CPUs]
    Cpufreq; Memory:      Unknown; 15934 MByte RAM
    Linux running:        5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
    Compiler used:        gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
    Linux compiled:       5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
    Config; Environment:  defconfig; CCACHE_DISABLE="1"
    Build command:        make vmlinux
    Run 1 (-j 12):        92.55 seconds / 38.90 kernels/hour
    Run 2 (-j 15):        91.91 seconds / 39.17 kernels/hour
    Run 3 (-j 6):         113.66 seconds / 31.67 kernels/hour
    Run 4 (-j 9):         101.32 seconds / 35.53 kernels/hour

You'll notice attempts that tried to utilize only the real cores (-j 6) and
oversubscribe them a little (-j 9), which looks like a waste of time. But on
some machines with SMT capable processors those will deliver the best results,
like on this AMD Threadripper processor with 64 core/128 threads:

    $ kcbench
    [cttest@localhost ~]$ bash kcbench -s 5.3 -i 1
    Processor:            AMD Ryzen Threadripper 3990X 64-Core Processor [128 CPUs]
    Cpufreq; Memory:      Unknown; 15934 MByte RAM
    Linux running:        5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
    Compiler used:        gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
    Linux compiled:       5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
    Config; Environment:  defconfig; CCACHE_DISABLE="1"
    Build command:        make vmlinux
    Run 1 (-j 128):       26.16 seconds / 137.61 kernels/hour
    Run 2 (-j 136):       26.19 seconds / 137.46 kernels/hour
    Run 3 (-j 64):        21.45 seconds / 167.83 kernels/hour
    Run 4 (-j 72):        22.68 seconds / 158.73 kernels/hour

This is even more visible when compiling an allmodconfig configuration:

    [cttest@localhost ~]$ bash kcbench -s 5.3 -i 1 -m
    Processor:            AMD Ryzen Threadripper 3990X 64-Core Processor [128 CPUs]
    Cpufreq; Memory:      Unknown; 63736 MByte RAM
    Linux running:        5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
    Compiler used:        gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
    Linux compiled:       5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
    Config; Environment:  defconfig; CCACHE_DISABLE="1"
    Build command:        make vmlinux
    Run 1 (-j 128):       260.43 seconds / 13.82 kernels/hour
    Run 2 (-j 136):       262.67 seconds / 13.71 kernels/hour
    Run 3 (-j 64):        215.54 seconds / 16.70 kernels/hour
    Run 4 (-j 72):        215.97 seconds / 16.67 kernels/hour

This can happen if the SMT implementation is bad or something else becomes a
bottleneck. A few tests on above machine indicated the memory interface was the
limiting factor. An AMD Epyc from the same processor generation did not show
this effect and delivered its best results when the number of jobs matched the
number of CPUs:

    [cttest@localhost ~]$ bash kcbench -s 5.3 -i 1 -m
    Processor:            AMD EPYC 7742 64-Core Processor [256 CPUs]
    Cpufreq; Memory:      Unknown; 63736 MByte RAM
    Linux running:        5.6.0-0.rc2.git0.1.vanilla.knurd.2.fc31.x86_64
    Compiler used:        gcc (GCC) 9.2.1 20190827 (Red Hat 9.2.1-1)
    Linux compiled:       5.3.0 [/home/cttest/.cache/kcbench/linux-5.3/]
    Config; Environment:  defconfig; CCACHE_DISABLE="1"
    Build command:        make vmlinux
    Run 1 (-j 256):       128.24 seconds / 28.07 kernels/hour
    Run 2 (-j 268):       128.87 seconds / 27.94 kernels/hour
    Run 3 (-j 128):       141.83 seconds / 25.38 kernels/hour
    Run 4 (-j 140):       137.46 seconds / 26.19 kernels/hour

This table will tell you now many jobs kcbench will use by default:

     #                             Cores: Default # of jobs
     #                             1 CPU: 1 2
     #           2 CPUs (    no SMT    ): 2 3
     #           2 CPUs (2 threads/core): 2 3 1
     #           4 CPUs (    no SMT    ): 4 6
     #           4 CPUs (2 threads/core): 4 6 2
     #           6 CPUs (    no SMT    ): 6 9
     #           6 CPUs (2 threads/core): 6 9 3
     #           8 CPUs (    no SMT    ): 8 11
     #           8 CPUs (2 threads/core): 8 11 4 6
     #          12 CPUs (    no SMT    ): 12 16
     #          12 CPUs (2 threads/core): 12 16 6 9
     #          16 CPUs (    no SMT    ): 16 20
     #          16 CPUs (2 threads/core): 16 20 8 11
     #          20 CPUs (    no SMT    ): 20 25
     #          20 CPUs (2 threads/core): 20 25 10 14
     #          24 CPUs (    no SMT    ): 24 29
     #          24 CPUs (2 threads/core): 24 29 12 16
     #          28 CPUs (    no SMT    ): 28 34
     #          28 CPUs (2 threads/core): 28 34 14 18
     #          32 CPUs (    no SMT    ): 32 38
     #          32 CPUs (2 threads/core): 32 38 16 20
     #          32 CPUs (4 threads/core): 32 38 8 11
     #          48 CPUs (    no SMT    ): 48 55
     #          48 CPUs (2 threads/core): 48 55 24 29
     #          48 CPUs (4 threads/core): 48 55 12 16
     #          64 CPUs (    no SMT    ): 64 72
     #          64 CPUs (2 threads/core): 64 72 32 38
     #          64 CPUs (4 threads/core): 64 72 16 20
     #         128 CPUs (    no SMT    ): 128 140
     #         128 CPUs (2 threads/core): 128 140 64 72
     #         128 CPUs (4 threads/core): 128 140 32 38
     #         256 CPUs (    no SMT    ): 256 272
     #         256 CPUs (2 threads/core): 256 272 128 140
     #         256 CPUs (4 threads/core): 256 272 64 72

ON FAILED RUNS DUE TO COMPILATION ERRORS
========================================

The compilation is unlikely to fail, as long as you are using a settled GCC
version to natively compile the source of a current Linux kernel for popular
architectures like ARM, ARM64/Aarch64, or x86_64. For other cases there is a
bigger risk that compilation will fail due to factors outsides of kcbench
control. They nevertheless try to catch a few common problems and warn, but
they can not catch them all, as there are to many factors involved:

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
more likely to happen if you start kcbench with '-m/--allmodconfig'
to build a more complex kernel.


HINTS
=====

Running benchmarks to compare the results fairly can be tricky. Here are a few
of the aspects you should keep mind when trying to do so:

 * Do not compare results from two different architectures (like ARM64 and
x86_64): kcbench compile different code in that case, as they will compile a
native kernel on each of those architectures. This can be avoided by cross
compiling for a third architecture that is not related to any of the
architectures compared (say RISC-V when comparing ARM64 and x86_64).

 * Unless you want to benchmark compiler effects, do not compare results from
different compiler generations. For example to not compare results from GCC7 and
GCC9, as the later optimizes harder and thus will take more time. Newer compiler
generations often are also stricter, which is why they often uncover bugs in the
Linux kernel source that need to be fixed for compiling to succeed -- which is
why the Linux version kcbench compiles by default depends on the compiler.

 * Compiling a Linux kernel scales very well and thus can utilize processors
quite well. But be aware that some parts of the Linux compile process will only
use one thread (and thus one CPU core), for example when linking vmlinuz; the
other cores idle meanwhile. The effect on the result will grow with the
number of CPU cores.

 If you want to work against that consider using '-m' to build an allmodconfig
configuration with modules; comping a newer, more complex Linux kernel version
can also help. But the best way to avoid this effect is by using kcbenchrate.

 * Kcbench by default sets CCACHE_DISABLE=1 when calling 'make' to avoid
interference from ccache.


EXAMPLES
========

To let kcbench decide everything automatically simply run:

:      $ kcbench

On a four core processor without SMT kcbench by default will compile two kernels
with 4 jobs and two with 6 jobs. You can specify a setting like this manually:
.

:      $ kcbench -s 5.4 --iterations 3 --jobs 2 --jobs 4

This will compile Linux 5.4 first three times with 2 jobs and then as often with
4 jobs.


RESULTS
=======

By default, the lines you are looking for look like this:

    Run 1 (-j 4): 230.30 sec / 15.63 kernels/hour [P:389%, 24 maj. pagefaults]

Here it took 230.30 seconds to compile the Linux kernel image. With a speed
like this the machine can compile 15.63 kernels per hour (60*60/230.30). The
results from this 4 core machine also show the CPU usage (P) was 389 percent;
24 major page faults occurred during this run – this number should be small, as
processing them takes some time and thus slows down the build. This information
is omitted, if less than 20 major page faults happen. For details how the CPU
usage is calculated and major page faults are detected see the man page for GNU
'time', which kcbench relies on for its measurements.

When running with "-d|--detailedresults" you'll get more detailed
result:

    Run 1 (-j 4): 230.30 sec / 15.63 kernels/hour [P:389%]
    Elapsed Time(E): 2:30.10 (150.10 seconds)
    Kernel time (S): 36.38 seconds
    User time (U): 259.51 seconds
    CPU usage (P): 197%
    Major page faults (F): 0
    Minor page faults (R): 9441809
    Context switches involuntarily (c): 69031
    Context switches voluntarily (w): 46955


MISSING FEATURES
================

* some math to detect the fastest setting and do one more run with it before
  sanity checking the result and printing the best one, including standard
  deviation.


SEE ALSO
========
**kcbenchrate(1)**, **time(1)**


AUTHOR
======
Thorsten Leemhuis <linux [AT] leemhuis [DOT] info>
