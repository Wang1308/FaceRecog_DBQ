from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from flask import Flask
from flask import render_template , request
from flask_cors import CORS, cross_origin
import tensorflow as tf
import argparse
import facenet
import os
import sys
import math
import pickle
import align.detect_face
import numpy as np
import cv2
import collections
from sklearn.svm import SVC
import base64
tf.compat.v1.disable_eager_execution()
from database import connect_db
from datetime import datetime
import time
last_checkin_time = {}

def insert_attendance(employee_id):
    try:
        conn = connect_db()
        cur = conn.cursor()

        # Lấy tên nhân viên từ employee_id
        cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
        result = cur.fetchone()
        if not result:
            print("❌ Không tìm thấy nhân viên với ID:", employee_id)
            return
        name = result[0]

        # Kiểm tra đã chấm công trong vòng 1 phút chưa
        cur.execute("""
            SELECT * FROM attendance 
            WHERE employee_id = %s AND checkin_time > NOW() - INTERVAL '1 minute'
        """, (employee_id,))
        recent = cur.fetchone()
        if recent:
            print(f"⏳ {name} đã chấm công gần đây, chờ thêm 1 phút.")
            return

        # Chấm công
        cur.execute(
            "INSERT INTO attendance (employee_id, name, checkin_time) VALUES (%s, %s, %s)",
            (employee_id, name, datetime.now())
        )
        conn.commit()
        print(f"✅ Đã chấm công cho {name} lúc {datetime.now()}")

        cur.close()
        conn.close()
    except Exception as e:
        print("❌ Lỗi khi ghi dữ liệu chấm công:", str(e))

MINSIZE = 20
THRESHOLD = [0.6, 0.7, 0.7]
FACTOR = 0.709
IMAGE_SIZE = 182
INPUT_IMAGE_SIZE = 160
CLASSIFIER_PATH = 'Models/facemodel.pkl'
FACENET_MODEL_PATH = 'Models/20180402-114759.pb'

# Load The Custom Classifier
with open(CLASSIFIER_PATH, 'rb') as file:
    model, class_names = pickle.load(file)
print("Custom Classifier, Successfully loaded")

tf.Graph().as_default()

# Cai dat GPU neu co
gpu_options = tf.compat.v1.GPUOptions(per_process_gpu_memory_fraction=0.6)
sess = tf.compat.v1.Session(config=tf.compat.v1.ConfigProto(gpu_options=gpu_options, log_device_placement=False))


# Load the model
print('Loading feature extraction model')
facenet.load_model(FACENET_MODEL_PATH)

# Get input and output tensors
images_placeholder = tf.compat.v1.get_default_graph().get_tensor_by_name("input:0")
embeddings = tf.compat.v1.get_default_graph().get_tensor_by_name("embeddings:0")
phase_train_placeholder = tf.compat.v1.get_default_graph().get_tensor_by_name("phase_train:0")
embedding_size = embeddings.get_shape()[1]
pnet, rnet, onet = align.detect_face.create_mtcnn(sess, "src/align")



app = Flask(__name__)
CORS(app)



@app.route('/')
@cross_origin()
def index():
    return "OK!";

@app.route('/recog', methods=['POST'])
@cross_origin()
def upload_img_file():
    if request.method == 'POST':
        # base 64
        name="Unknown"
        f = request.form.get('image')
        w = int(request.form.get('w'))
        h = int(request.form.get('h'))

        decoded_string = base64.b64decode(f)
        frame = np.frombuffer(decoded_string, dtype=np.uint8)
        #frame = frame.reshape(w,h,3)
        frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)  # cv2.IMREAD_COLOR in OpenCV 3.1

        bounding_boxes, _ = align.detect_face.detect_face(frame, MINSIZE, pnet, rnet, onet, THRESHOLD, FACTOR)

        faces_found = bounding_boxes.shape[0]

        if faces_found > 0:
            det = bounding_boxes[:, 0:4]
            bb = np.zeros((faces_found, 4), dtype=np.int32)
            for i in range(faces_found):
                bb[i][0] = det[i][0]
                bb[i][1] = det[i][1]
                bb[i][2] = det[i][2]
                bb[i][3] = det[i][3]
                x1, y1, x2, y2 = bb[i]
                cropped = frame[y1:y2, x1:x2]

                #cropped = frame[bb[i][1]:bb[i][3], bb[i][0]:bb[i][2], :]
                scaled = cv2.resize(cropped, (INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE),
                                    interpolation=cv2.INTER_CUBIC)
                scaled = facenet.prewhiten(scaled)
                scaled_reshape = scaled.reshape(-1, INPUT_IMAGE_SIZE, INPUT_IMAGE_SIZE, 3)
                feed_dict = {images_placeholder: scaled_reshape, phase_train_placeholder: False}
                emb_array = sess.run(embeddings, feed_dict=feed_dict)
                predictions = model.predict_proba(emb_array)
                best_class_indices = np.argmax(predictions, axis=1)
                best_class_probabilities = predictions[
                    np.arange(len(best_class_indices)), best_class_indices]
                best_name = class_names[best_class_indices[0]]
                print("Name: {}, Probability: {}".format(best_name, best_class_probabilities))

                if best_class_probabilities[0] > 0.28:
                    name = class_names[best_class_indices[0]]
                    # --- Kiểm tra thời gian chấm công lần cuối ---
                    current_time = time.time()
                    last_time = last_checkin_time.get(name, 0)
                    if current_time - last_time >= 60:  # ít nhất 10 giây
                        try:
                            conn = connect_db()
                            cur = conn.cursor()
                            cur.execute("SELECT id FROM employees WHERE name = %s", (name,))
                            result = cur.fetchone()
                            if result:
                                employee_id = result[0]
                                insert_attendance(employee_id)
                                last_checkin_time[name] = current_time
                            cur.close()
                            conn.close()
                        except Exception as e:
                            print("Lỗi truy vấn ID nhân viên:", e)
                else:
                    name = "Unknown"


        return name;


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port='8000')

