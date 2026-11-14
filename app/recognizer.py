import random

def read_plate(image=None):
    """Fake result. Returns plate, raw model text, confidence."""
    conf = random.choice([0.95, 0.60])
    plate = "ABC123DE"
    raw = plate if conf > 0.9 else "A8C123DE"
    return {"plate": plate, "raw": raw, "confidence": conf}