../wrk -D exp -t 32 -c 4000 -d 600 -L -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://10.100.56.97:5000 -R 2000
