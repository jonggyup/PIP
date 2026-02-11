#!/bin/bash
cgexec -g cpu:user ./wrk3 \
  -target 'http://localhost:8080/wrk2-api/post/compose' \
  -method POST \
  -header 'Content-Type: application/x-www-form-urlencoded' \
  -body 'username=u1&user_id=1&text=hi&media_ids=[]&media_types=[]&post_type=0' \
  -duration 300s -sla-ms 500 \
  -phases '10s@30,30s@10,30s@30,10s@40,10s@5' \
  -jitter-pct 10 -think-mean-ms 12

