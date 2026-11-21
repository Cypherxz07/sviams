import numpy as np
from PIL import Image
import plate_engine as pe

def _to_pil(image):
    if isinstance(image, str):
        return Image.open(image)
    if isinstance(image, np.ndarray):
        if image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]
        return Image.fromarray(image[:, :, ::-1].copy())  # camera gives BGR
    return image

def read_plate(image=None):
    """Returns plate, raw model text, confidence."""
    if image is None:
        return {"plate": "", "raw": "", "confidence": 0.0}
    im = _to_pil(image).convert("RGB")
    W, H = im.size
    b = pe._detect(im)
    if b is None:
        return {"plate": "", "raw": "", "confidence": 0.0}
    cx, cy, bw, bh = b
    m = pe.MARGIN
    box = (max(0, cx - bw/2*(1+m)), max(0, cy - bh/2*(1+m)),
           min(W, cx + bw/2*(1+m)), min(H, cy + bh/2*(1+m)))
    crop = im.crop(tuple(int(v) for v in box)).convert("L").resize((128, 64), Image.BILINEAR)
    x = ((np.asarray(crop, np.float32) / 255. - .5) / .5)[None, None]
    lg = pe.rea.run(None, {"x": x})[0][0]
    e = np.exp(lg - lg.max(-1, keepdims=True))
    pr = e / e.sum(-1, keepdims=True)
    idx = pr.argmax(-1)
    s, confs, prev = [], [], 0
    for t, k in enumerate(idx):
        if k != prev and k != 0:
            s.append(pe.CH[k - 1]); confs.append(pr[t, k])
        prev = k
    raw = "".join(s)
    conf = float(min(confs)) if confs else 0.0
    return {"plate": raw, "raw": raw, "confidence": round(conf, 3)}
