import os, numpy as np
from PIL import Image
import onnxruntime as ort

M = os.path.expanduser("~/sviams/models")
det = ort.InferenceSession(f"{M}/plate_det.onnx", providers=["CPUExecutionProvider"])
rea = ort.InferenceSession(f"{M}/plate_reader.onnx", providers=["CPUExecutionProvider"])
CH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
MARGIN = 0.12

def _detect(im):
    w, h = im.size; r = min(640 / w, 640 / h)
    nw, nh = round(w * r), round(h * r)
    px, py = (640 - nw) // 2, (640 - nh) // 2
    cv = Image.new('RGB', (640, 640), (114, 114, 114))
    cv.paste(im.resize((nw, nh), Image.BILINEAR), (px, py))
    x = np.asarray(cv, np.float32).transpose(2, 0, 1)[None] / 255.
    o = det.run(None, {det.get_inputs()[0].name: x})[0][0]
    i = o[4].argmax()
    if o[4, i] < 0.25: return None
    cx, cy, bw, bh = o[:4, i]
    return (cx - px) / r, (cy - py) / r, bw / r, bh / r

def _read(im):
    im = im.convert('L').resize((128, 64), Image.BILINEAR)
    x = ((np.asarray(im, np.float32) / 255. - .5) / .5)[None, None]
    p = rea.run(None, {'x': x})[0][0].argmax(-1)
    s, prev = [], 0
    for k in p:
        if k != prev and k != 0: s.append(CH[k - 1])
        prev = k
    return ''.join(s)

def recognize(im):
    im = im.convert('RGB'); W, H = im.size
    b = _detect(im)
    if b is None: return ''
    cx, cy, bw, bh = b
    m = MARGIN
    box = (max(0, cx - bw/2*(1+m)), max(0, cy - bh/2*(1+m)),
           min(W, cx + bw/2*(1+m)), min(H, cy + bh/2*(1+m)))
    return _read(im.crop(tuple(int(v) for v in box)))
