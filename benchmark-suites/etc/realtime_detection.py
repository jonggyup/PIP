import os
import sys
import signal

# Suppress TensorFlow logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.stderr = open(os.devnull, 'w')

import cv2
import tensorflow as tf
import numpy as np
import time
import random
import argparse

MODEL_HEAVY = 'tensorflow_model/faster_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb'
MODEL_LIGHT = 'tensorflow_model/ssd_mobilenet_v1_coco_2018_01_28/frozen_inference_graph.pb'

terminate = False

def signal_handler(sig, frame):
    global terminate
    terminate = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def load_model(model_path):
    detection_graph = tf.Graph()
    with detection_graph.as_default():
        graph_def = tf.compat.v1.GraphDef()
        with tf.io.gfile.GFile(model_path, 'rb') as f:
            graph_def.ParseFromString(f.read())
            tf.import_graph_def(graph_def, name='')
    sess = tf.compat.v1.Session(graph=detection_graph)
    return sess, detection_graph

def run_inference_for_duration(run_duration):
    sess_heavy, graph_heavy = load_model(MODEL_HEAVY)
    sess_light, graph_light = load_model(MODEL_LIGHT)

    cap = cv2.VideoCapture('https://storage.googleapis.com/docs.livepeer.live/bbb_sunflower_1080p_30fps_normal.cgop.flv')

    inference_count = 0
    last_demand_change = time.time()
    demand_interval = 5
    demand_level = random.choice(['high', 'medium', 'low'])
    start_time_overall = time.time()

    while not terminate:
        if run_duration != float('inf') and time.time() - start_time_overall >= run_duration:
            break

        ret, frame = cap.read()
        if not ret:
            break

        current_time = time.time()
        if current_time - last_demand_change >= demand_interval:
            demand_level = random.choice(['high', 'medium', 'low'])
            last_demand_change = current_time

        if demand_level == 'high':
            sess = sess_heavy
            graph = graph_heavy
            resized_frame = cv2.resize(frame, (1920, 1080))
        elif demand_level == 'medium':
            sess = sess_heavy
            graph = graph_heavy
            resized_frame = cv2.resize(frame, (1280, 720))
        else:
            sess = sess_light
            graph = graph_light
            resized_frame = cv2.resize(frame, (640, 480))

        image_tensor = graph.get_tensor_by_name('image_tensor:0')
        boxes = graph.get_tensor_by_name('detection_boxes:0')
        scores = graph.get_tensor_by_name('detection_scores:0')
        classes = graph.get_tensor_by_name('detection_classes:0')
        num_detections = graph.get_tensor_by_name('num_detections:0')

        image_expanded = np.expand_dims(resized_frame, axis=0)

        sess.run(
            [boxes, scores, classes, num_detections],
            feed_dict={image_tensor: image_expanded}
        )
        inference_count += 1

    cap.release()
    elapsed = time.time() - start_time_overall
    print(f"Inferences: {inference_count}")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Average inferences/sec: {inference_count / elapsed:.2f}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run object detection for a specified duration.")
    parser.add_argument('--duration', required=True, help='Duration to run inference in seconds or "inf"')
    args = parser.parse_args()

    if args.duration == 'inf':
        duration = float('inf')
    else:
        duration = int(args.duration)

    run_inference_for_duration(duration)

