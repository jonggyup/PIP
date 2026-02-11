#!/bin/bash
lscpu -p=CPU,NODE,SOCKET,CORE | grep -v '^#' | awk -F, '{print $3 " " $4 " " $1}' | sort -r -n -k1,1 -k2,2 | awk 'BEGIN{prev_core=-1; first=1} {if($2!=prev_core){if(first){first=0}else{printf ", "} printf "%d", $3; prev_core=$2}else{printf ",%d", $3}} END{print ""}'

