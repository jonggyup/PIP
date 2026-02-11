#!/bin/bash

mkdir tensorflow_model
pushd tensorflow_model
wget http://download.tensorflow.org/models/object_detection/faster_rcnn_inception_v2_coco_2018_01_28.tar.gz
tar -xzvf faster_rcnn_inception_v2_coco_2018_01_28.tar.gz

# Download SSD MobileNet v1 model
wget http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2018_01_28.tar.gz

# Extract the model
tar -xzf ssd_mobilenet_v1_coco_2018_01_28.tar.gz

# Clean up downloaded file
rm *tar*
popd
