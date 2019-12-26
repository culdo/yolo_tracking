import json
import requests
import time
from util.yolo_frame import YoloFrame, YoloObj


class ObjectTrack:

    def __init__(self, json_url, ns, state_q, is_update=True, **kwargs):
        self.kwargs = kwargs
        self.prev_frame = YoloFrame(None)
        self.curr_frame = None
        # buff_time = time.time()
        self.iter_IOU = None
        self.iter_idx = None
        self.ns = ns
        self.state_q = state_q
        self.is_update = is_update

        self.handle_yolo_result(json_url)

    def handle_yolo_result(self, json_url):
        r = requests.get(json_url, stream=True)
        is_append = False
        predict_json = ""

        for c_bin in r.iter_lines(chunk_size=512):
            if c_bin:
                c = c_bin.decode("ascii")
                if c == "{":
                    is_append = True
                elif c == "}, ":
                    predict_json += "}"
                    self._update_frame(predict_json)

                    is_append = False
                    predict_json = ""

                if is_append:
                    predict_json += c

    def _update_frame(self, predict_json):
        predict_result = json.loads(predict_json)
        self.curr_frame = YoloFrame(predict_result, **self.kwargs)
        print("\n[Frame]")
        if self.is_update:
            self.object_track_iou()
        self.ns.curr_frame = self.curr_frame

    def object_track_iou(self, is_5m=None,
                         is_open=None, is_indoor=False, is_outdoor=False):
        """
        keys: ["class_id", "name", "relative_coordinates":{"center_x", "center_y", "width",
         "height"}, "confidence"]
        """
        orginal_len = len(self.curr_frame.objects)

        # print("fps: %d" % (1/(time.time() - buff_time)))
        # buff_time = time.time()
        # print(curr_frame)
        if self.prev_frame.__dict__:
            # First iterate prev_frame and then curr_obj
            # because we want to save(append) the previous object which is not found
            for prev_i, prev_obj in enumerate(self.prev_frame.objects):
                prev_obj.max_IOU = 0
                self.iter_IOU = 0
                self.iter_idx = None
                # we use original_len to prevent to iterate the appended one
                for i, obj in enumerate(self.curr_frame.objects):
                    if prev_obj.class_id == obj.class_id and i < orginal_len:
                        present_IOU = YoloObj.calcIOU(prev_obj.relative_coordinates, obj.relative_coordinates)
                        # Update IOU and save(append) the object which is not found

                        if present_IOU > self.iter_IOU and present_IOU > obj.max_IOU:
                            self.iter_IOU = present_IOU
                            self.iter_idx = i

                if self.iter_idx is not None:
                    best_obj = self.curr_frame.objects[self.iter_idx]
                    # if best_obj.name == "person":
                    #     print("UID updated person.uid = %d" % best_obj.uid)
                    if best_obj.best_prev_idx is not None:
                        self.prev_frame.objects[best_obj.best_prev_idx].max_IOU = 0
                    prev_obj.max_IOU = self.iter_IOU
                    best_obj.max_IOU = self.iter_IOU
                    best_obj.best_prev_idx = prev_i

                    best_obj.state = prev_obj.state

            for prev_obj in self.prev_frame.objects:
                # if the previous object is not found in current frame,
                # we save the object used to first add the buff_times then append to curr_frame
                if prev_obj.max_IOU == 0:
                    if prev_obj.buff_times < YoloObj.max_buff_times:
                        prev_obj.buff_times += 1
                        self.curr_frame.objects.append(prev_obj)
                        # if prev_obj.name == "person":
                        # print("Appended %s.uid: %s" % (prev_obj.name, prev_obj.uid))

            is_stay_5m = False
            global is_stay_5m
            for i, obj in enumerate(self.curr_frame.objects):
                if i < orginal_len:
                    if obj.max_IOU == 0:
                        obj.state.new_state()
                        # if curr_obj.name == "person":
                        print("New %s uid: %s" % (obj.name, obj.state.uid))
                    else:
                        obj.state.stay_time = time.time() - obj.state.spawn_time

                # Count objects
                if obj.name not in self.curr_frame.objects_count:
                    self.curr_frame.objects_count[obj.name] = 1
                else:
                    self.curr_frame.objects_count[obj.name] += 1

                # Cast stay time
                if obj.state.stay_time > obj.state.notify_time and self.state_q is not None:
                    self.state_q.put(obj.state)
                    obj.state.notify_time += 60

                # Open door
                if obj.state.stay_time > 300:
                    is_stay_5m = True

            # indoor condition
            if is_indoor:
                if is_stay_5m:
                    is_5m.value = 1
                else:
                    is_5m.value = 0

            # outdoor condition
            if is_outdoor:
                if self.curr_frame.objects_count["person"] > 0 and is_5m.value == 1:
                    is_open.value = 1
                else:
                    is_open.value = 0

        self.prev_frame.__dict__.update(self.curr_frame.__dict__)

        # try:
        #     q.put_nowait(curr_frame)
        # except queue.Full:
        #     q.get()
        # if q is not None:
        #     q.put(curr_frame)


if __name__ == "__main__":
    # For test
    # ObjectTrack()
    pass
