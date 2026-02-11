#!/bin/bash
ffmpeg -re -i https://storage.googleapis.com/docs.livepeer.live/bbb_sunflower_1080p_30fps_normal.cgop.flv \
  -c:v libx264 -preset slow -crf 20 \
  -vf "scale=1920:1080" \
  -c:a aac -b:a 128k \
  -f flv ./output.mp4
