#!/bin/bash

URL="https://localhost/"

while true; do
    echo "High load (spike)..."
    wrk -t16 -c500 -d5s --timeout 2s $URL

    sleep 2

    echo "Medium load..."
    wrk -t8 -c100 -d3s --timeout 2s $URL

    sleep 1

    echo "Low load..."
    wrk -t4 -c20 -d4s --timeout 2s $URL

    sleep 2
done

