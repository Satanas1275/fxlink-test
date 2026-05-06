import sys
import time
import struct

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erreur: pyusb n'est pas installe.")
    sys.exit(1)

CASIO_VID = 0x07cf
BYTES_PER_FRAME = 1024  # 128*64/8

def find_calculator():
    devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
    for dev in devices:
        for cfg in dev:
            for intf in cfg:
                if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
                    return dev, intf
    return None, None

def build_fxlink_header(payload_size):
    app = b'fxlink' + b'\x00' * 10
    typ = b'image'  + b'\x00' * 11
    return struct.pack('<III16s16s',
                       0x00000100,
                       payload_size,
                       0,
                       app,
                       typ)

def stream_video(bin_path):
    # Lire le header du fichier
    with open(bin_path, 'rb') as f:
        magic = f.read(4)
        if magic != b'FXBV':
            print("Erreur: fichier .bin invalide")
            return False
        fps      = struct.unpack('<I', f.read(4))[0]
        n_frames = struct.unpack('<I', f.read(4))[0]
        width    = struct.unpack('<H', f.read(2))[0]
        height   = struct.unpack('<H', f.read(2))[0]

    print(f"Fichier  : {bin_path}")
    print(f"Frames   : {n_frames} @ {fps} fps")
    print(f"Résolution: {width}x{height}")
    print(f"Durée    : {n_frames / fps:.1f}s")

    # Trouver la calculatrice
    dev, _ = find_calculator()
    if dev is None:
        print("Calculatrice non trouvee.")
        return False
    print(f"Calculatrice: {dev.idVendor:04x}:{dev.idProduct:04x}")

    try:
        dev.set_configuration()
    except:
        pass

    cfg = dev.get_active_configuration()
    intf_num = None
    ep_out   = None

    for intf in cfg:
        if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
            intf_num = intf.bInterfaceNumber
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    ep_out = ep
                    break
            break

    if intf_num is None or ep_out is None:
        print("Interface fxlink non trouvee")
        return False

    try:
        if dev.is_kernel_driver_active(intf_num):
            dev.detach_kernel_driver(intf_num)
    except:
        pass

    usb.util.claim_interface(dev, intf_num)

    frame_interval = 1.0 / fps
    bytes_per_frame = (width * height) // 8

    # Header fxlink image (width, height, format=1)
    img_header = struct.pack('<III', width, height, 1)
    payload_size = len(img_header) + bytes_per_frame
    fxlink_hdr = build_fxlink_header(payload_size)

    print(f"\nStreaming... (Ctrl+C pour arreter)")

    try:
        with open(bin_path, 'rb') as f:
            f.seek(16)  # sauter le header fichier

            frame_idx  = 0
            start_time = time.time()

            while frame_idx < n_frames:
                frame_data = f.read(bytes_per_frame)
                if len(frame_data) < bytes_per_frame:
                    break

                # Envoyer header + payload en un seul write
                ep_out.write(fxlink_hdr + img_header + frame_data)

                frame_idx += 1

                # Timing: attendre le bon moment pour la prochaine frame
                next_time = start_time + frame_idx * frame_interval
                wait = next_time - time.time()
                if wait > 0:
                    time.sleep(wait)

                if frame_idx % 100 == 0:
                    elapsed = time.time() - start_time
                    real_fps = frame_idx / elapsed
                    print(f"  Frame {frame_idx}/{n_frames} | {real_fps:.1f} fps réels | {elapsed:.1f}s")

    except KeyboardInterrupt:
        print("\nArreté.")
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            usb.util.release_interface(dev, intf_num)
        except:
            pass

    print("Stream terminé.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 stream_video.py <fichier.bin>")
        sys.exit(1)

    stream_video(sys.argv[1])
