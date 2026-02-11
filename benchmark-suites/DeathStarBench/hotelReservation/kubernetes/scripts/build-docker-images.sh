#!/bin/bash

cd $(dirname $0)/..

EXEC="docker buildx"

#USER="igorrudyk1"

USER="jonggyupark"

TAG="latest"

# ENTER THE ROOT FOLDER
cd ../
ROOT_FOLDER=$(pwd)

# Remove existing buildx instance if it exists
$EXEC rm mybuilder 2>/dev/null || true

# Create a new buildx instance
$EXEC create --name mybuilder --use

for i in hotelreservation #frontend geo profile rate recommendation reserve search user #uncomment to build multiple images
do
  IMAGE=${i}
  echo Processing image ${IMAGE}
  cd $ROOT_FOLDER
  $EXEC build -t "$USER"/"$IMAGE":"$TAG" -f Dockerfile . --platform linux/amd64 --load --push
  cd $ROOT_FOLDER

  echo
done

# Remove the buildx instance after use
$EXEC rm mybuilder

cd - >/dev/null
