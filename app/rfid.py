from mfrc522 import MFRC522

_reader = MFRC522()

def read_uid():
    """Returns the tag UID as hex text (e.g. 'A1B2C3D4'), or None if no tag is present."""
    status, _ = _reader.MFRC522_Request(_reader.PICC_REQIDL)
    if status != _reader.MI_OK:
        return None
    status, uid = _reader.MFRC522_Anticoll()
    if status != _reader.MI_OK:
        return None
    return "".join(f"{b:02X}" for b in uid[:4])

if __name__ == "__main__":
    import time
    print("Tap a tag (Ctrl+C to stop)")
    last = None
    while True:
        uid = read_uid()
        if uid and uid != last:
            print("UID:", uid)
        last = uid
        time.sleep(0.2)