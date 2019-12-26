#!/usr/bin/env python3
# -*-coding utf-8-*-

"""MJPEG Server for the webcam"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import time
from multiprocessing import Process, Manager, Queue

import multiprocessing

from util.obj_track import ObjectTrack
from util.draw_result import draw_box
# from util.lab_cast import cast_audio


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):

        # Get the min intra frame delay
        if self.server.maxfps == 0:
            minDelay = 0
        else:
            minDelay = 1.0 / self.server.maxfps

        # Send headers
        self.send_response(200)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--myboundary")
        self.end_headers()

        o = self.wfile

        # Send image files in a loop
        lastFrameTime = 0
        while True:

            contents = self.server.frame_ns.img

            # Wait if required so we stay under the max FPS
            if lastFrameTime != 0:
                now = time.time()
                delay = now - lastFrameTime
                if delay < minDelay:
                    time.sleep(minDelay - delay)

            buff = "Content-Length: %s \r\n" % str(len(contents))
            # logging.debug( "Serving frame %s", imageFile )
            o.write(b"--myboundary\r\n")
            o.write(b"Content-Type: image/jpeg\r\n")
            o.write(buff.encode("utf8"))
            o.write(b"\r\n")
            o.write(contents)
            o.write(b"\r\n")

            lastFrameTime = time.time()


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass


def start_track_process(frame_ns, state_q=Queue()):
    port = 8091
    indoor_url = 'http://203.64.134.236:8070'
    # img_url = "http://192.168.0.200:8080/video"
    img_url = "http://192.168.0.101:8080/stream?topic=/usb_cam_node/image_raw&type=ros_compressed"

    server = ThreadingHTTPServer(("0.0.0.0", port), RequestHandler)
    server.maxfps = 0
    print("Listening on Port " + str(port) + "...")
    server.frame_ns = frame_ns
    server.frame_ns.img = None

    frame_ns.curr_frame = None

    obj_track = Process(target=ObjectTrack, args=(indoor_url, frame_ns, state_q, False),
                        kwargs={'obj_filter': ball_filter})
    obj_track.start()

    while frame_ns.curr_frame is None:
        time.sleep(0.0001)

    track_draw = Process(target=draw_box, args=(img_url, frame_ns, frame_ns, "ORANGE"))
    track_draw.start()
    # track_draw.join()

    server.serve_forever()
    # lab_cast = Process(target=cast_audio, args=(state_q,))
    # lab_cast.start()


def ball_filter(obj):
    print(obj["name"])
    if obj["name"] == "sports ball":
        return True
    # return True


if __name__ == "__main__":
    manager = Manager()
    ns = manager.Namespace()

    start_track_process(ns, None)
