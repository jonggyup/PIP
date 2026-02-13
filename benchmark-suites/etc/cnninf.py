import os
import sys
import signal
import cv2
import tensorflow as tf
import numpy as np
import time
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.stderr = open(os.devnull, 'w')

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

def run_inference(sess, graph, frame):
    image_tensor = graph.get_tensor_by_name('image_tensor:0')
    boxes = graph.get_tensor_by_name('detection_boxes:0')
    scores = graph.get_tensor_by_name('detection_scores:0')
    classes = graph.get_tensor_by_name('detection_classes:0')
    num_detections = graph.get_tensor_by_name('num_detections:0')

    image_expanded = np.expand_dims(frame, axis=0)
    (boxes_out, scores_out, classes_out, num_out) = sess.run(
        [boxes, scores, classes, num_detections],
        feed_dict={image_tensor: image_expanded}
    )
    return boxes_out[0], scores_out[0], classes_out[0], int(num_out[0])

def process_detections(frame, boxes, scores, classes, num_detections, threshold=0.5):
    height, width, _ = frame.shape
    class_counts = defaultdict(int)
    for i in range(num_detections):
        if scores[i] > threshold:
            class_id = int(classes[i])
            class_counts[class_id] += 1
            ymin, xmin, ymax, xmax = boxes[i]
            left, right = int(xmin * width), int(xmax * width)
            top, bottom = int(ymin * height), int(ymax * height)
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            label = f"ID:{class_id} {scores[i]:.2f}"
            cv2.putText(frame, label, (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return class_counts

def run_inference_for_duration(run_duration):
    sess_heavy, graph_heavy = load_model(MODEL_HEAVY)
    sess_light, graph_light = load_model(MODEL_LIGHT)

    cap = cv2.VideoCapture('https://storage.googleapis.com/docs.livepeer.live/bbb_sunflower_1080p_30fps_normal.cgop.flv')

    inference_count = 0
    last_demand_change = time.time()
    demand_interval = 30 #changed from 30 to 10
    demand_level = 'high'
    start_time_overall = time.time()

    while not terminate:
        if run_duration != float('inf') and time.time() - start_time_overall >= run_duration:
            break

        ret, frame = cap.read()
        if not ret:
            if run_duration == float('inf'):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                break

        current_time = time.time()
        if current_time - last_demand_change >= demand_interval:
            if demand_level == 'high':
                demand_level = 'low'
            elif demand_level == 'low':
                demand_level = 'medium'
            else:
                demand_level = 'high'
            last_demand_change = current_time

        if demand_level == 'high':
            sess, graph = sess_heavy, graph_heavy
            full_frame = cv2.resize(frame, (1920, 1080))
            crops = [
                full_frame[0:540, 0:960],      # top-left
                full_frame[0:540, 960:1920],     # top-right
                full_frame[540:1080, 0:960],     # bottom-left
                full_frame[540:1080, 960:1920],  # bottom-right
                full_frame[270:810, 640:1280]    # center crop
            ]
            with ThreadPoolExecutor(max_workers=len(crops)) as executor:
                results = list(executor.map(lambda crop: run_inference(sess, graph, crop), crops))
            for crop, result in zip(crops, results):
                boxes, scores, classes, num = result
                process_detections(crop, boxes, scores, classes, num)
                inference_count += 1

        elif demand_level == 'medium':
            sess, graph = sess_heavy, graph_heavy
            resized_frame = cv2.resize(frame, (960, 540))
            center_crop = resized_frame[135:405, 320:640]
            boxes, scores, classes, num = run_inference(sess, graph, center_crop)
            process_detections(center_crop, boxes, scores, classes, num)
            inference_count += 1

        else:
            sess, graph = sess_light, graph_light
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small_frame = cv2.resize(gray_frame, (160, 120))
            small_frame = cv2.cvtColor(small_frame, cv2.COLOR_GRAY2RGB)
            boxes, scores, classes, num = run_inference(sess, graph, small_frame)
            inference_count += 1

    cap.release()
    elapsed = time.time() - start_time_overall
    print(f"Inferences: {inference_count}")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Average inferences/sec: {inference_count / elapsed:.2f}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run object detection for a specified duration.")
    parser.add_argument('--duration', required=True, help='Duration in seconds or "inf" for infinite run')
    args = parser.parse_args()

    duration = float('inf') if args.duration == 'inf' else int(args.duration)
    run_inference_for_duration(duration)

