#!/usr/bin/env python3
"""
screen_stream.py - Stream l'écran vers la fx-9860G (KDE Wayland)
Usage: sudo python3 screen_stream.py
"""

import sys
import time
import struct
import subprocess
import signal
import os
import tempfile

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erreur: pyusb n'est pas installe. pip install pyusb --break-system-packages")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Erreur: Pillow n'est pas installe. pip install pillow --break-system-packages")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("Erreur: numpy n'est pas installe. pip install numpy --break-system-packages")
    sys.exit(1)

CASIO_VID      = 0x07cf
TARGET_W       = 128
TARGET_H       = 64
FPS            = 20
FRAME_INTERVAL = 1.0 / FPS

# ─── USB ──────────────────────────────────────────────────────────────────────

def find_calculator():
    devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
    for dev in devices:
        for cfg in dev:
            for intf in cfg:
                if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
                    return dev, intf
    return None, None

def setup_usb():
    dev, _ = find_calculator()
    if dev is None:
        print("Calculatrice non trouvee.")
        return None, None, None

    print(f"Calculatrice: {dev.idVendor:04x}:{dev.idProduct:04x}")

    try:
        dev.set_configuration()
    except:
        pass

    cfg      = dev.get_active_configuration()
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
        return None, None, None

    try:
        if dev.is_kernel_driver_active(intf_num):
            dev.detach_kernel_driver(intf_num)
    except:
        pass

    usb.util.claim_interface(dev, intf_num)
    return dev, intf_num, ep_out

def build_packet(pixel_data):
    img_header = struct.pack('<III', TARGET_W, TARGET_H, 1)
    payload    = img_header + pixel_data
    app        = b'fxlink' + b'\x00' * 10
    typ        = b'image'  + b'\x00' * 11
    fxlink_hdr = struct.pack('<III16s16s',
                             0x00000100,
                             len(payload),
                             0,
                             app,
                             typ)
    return fxlink_hdr + payload

def frame_to_1bpp(img):
    gray   = img.convert('L')
    arr    = np.array(gray)
    binary = (arr < 128).astype(np.uint8)
    packed = np.packbits(binary, axis=1, bitorder='big')
    return packed.tobytes()

# ─── CAPTURE ──────────────────────────────────────────────────────────────────

# Fichier tmp réutilisé à chaque frame
TMP_SCREENSHOT = tempfile.mktemp(suffix='.png', prefix='fxlink_')

def capture_screen():
    """Capture l'écran principal via spectacle"""
    subprocess.run(
        ['spectacle', '-b', '-n', '-o', TMP_SCREENSHOT],
        capture_output=True  # silence les warnings tesseract
    )
    img = Image.open(TMP_SCREENSHOT)
    img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    return img

def capture_region(x, y, w, h):
    """Capture une région via spectacle"""
    subprocess.run(
        ['spectacle', '-b', '-n', '-r',
         f'{x},{y},{w},{h}',
         '-o', TMP_SCREENSHOT],
        capture_output=True
    )
    img = Image.open(TMP_SCREENSHOT)
    img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    return img

# ─── FENETRE VIRTUELLE ────────────────────────────────────────────────────────

virtual_proc   = None
virtual_region = {'x': 0, 'y': 0, 'w': 512, 'h': 256}

def open_virtual_window():
    global virtual_proc
    script = '''
import tkinter as tk
root = tk.Tk()
root.title("fx-9860G Virtual Screen")
root.geometry("512x256+100+100")
root.resizable(False, False)
canvas = tk.Canvas(root, width=512, height=256, bg="white")
canvas.pack()
canvas.create_text(256, 128,
    text="Fenetre virtuelle fx-9860G\\n128x64 @ 20fps\\n\\nTout ce qui est ici\\nsera affiche sur la calto",
    justify="center", font=("Monospace", 11))
root.mainloop()
'''
    virtual_proc = subprocess.Popen([sys.executable, '-c', script])
    time.sleep(2)

    print("\nFenetre virtuelle ouverte.")
    print("Entre les coordonnees X,Y du coin superieur gauche de la fenetre")
    print("(tu peux la trouver avec: xdotool search --name 'fx-9860G' getwindowgeometry)")
    print("Appuie juste sur Entree pour garder 100,100 par defaut")

    try:
        val = input("  X,Y (defaut: 100,100): ").strip()
        if val:
            x, y = val.split(',')
            virtual_region['x'] = int(x.strip())
            virtual_region['y'] = int(y.strip())
        else:
            virtual_region['x'] = 100
            virtual_region['y'] = 100
    except:
        virtual_region['x'] = 100
        virtual_region['y'] = 100

    virtual_region['w'] = 512
    virtual_region['h'] = 256
    print(f"Region: {virtual_region}")

# ─── MENU ─────────────────────────────────────────────────────────────────────

def menu():
    print()
    print("╔═══════════════════════════════════╗")
    print("║   fx-9860G Screen Stream          ║")
    print("╠═══════════════════════════════════╣")
    print("║  1. Mode duplication              ║")
    print("║     (capture ecran principal)     ║")
    print("║                                   ║")
    print("║  2. Mode ecran virtuel            ║")
    print("║     (fenetre tkinter dediee)      ║")
    print("║                                   ║")
    print("║  q. Quitter                       ║")
    print("╚═══════════════════════════════════╝")
    return input("Choix: ").strip()

# ─── STREAM ───────────────────────────────────────────────────────────────────

running = True

def stream_loop(ep_out, mode):
    global running

    frame_idx  = 0
    start      = time.time()
    last_fps_t = start
    last_fps_f = 0

    print(f"\nStreaming... Ctrl+C pour arreter\n")

    while running:
        t0 = time.time()

        try:
            if mode == '1':
                img = capture_screen()
            else:
                img = capture_region(
                    virtual_region['x'],
                    virtual_region['y'],
                    virtual_region['w'],
                    virtual_region['h']
                )

            packet = build_packet(frame_to_1bpp(img))
            ep_out.write(packet)
            frame_idx += 1

        except Exception as e:
            print(f"\nErreur frame {frame_idx}: {e}")

        # Stats toutes les 20 frames
        if frame_idx % 20 == 0 and frame_idx > 0:
            now     = time.time()
            elapsed = now - last_fps_t
            fps     = (frame_idx - last_fps_f) / elapsed if elapsed > 0 else 0
            last_fps_t = now
            last_fps_f = frame_idx
            print(f"Frame {frame_idx} | {fps:.1f} fps reels", end='\r')

        # Timing
        elapsed  = time.time() - t0
        leftover = FRAME_INTERVAL - elapsed
        if leftover > 0:
            time.sleep(leftover)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    global running, virtual_proc

    def on_sigint(sig, frame):
        global running
        running = False

    signal.signal(signal.SIGINT, on_sigint)

    choix = menu()
    if choix == 'q':
        return
    if choix not in ('1', '2'):
        print("Choix invalide.")
        return

    dev, intf_num, ep_out = setup_usb()
    if ep_out is None:
        return

    if choix == '2':
        print("\nOuverture fenetre virtuelle...")
        open_virtual_window()
        print("Positionne la fenetre ou tu veux, puis appuie sur Entree.")
        input()

    try:
        stream_loop(ep_out, choix)
    finally:
        running = False
        print("\nArret.")
        try:
            os.remove(TMP_SCREENSHOT)
        except:
            pass
        try:
            usb.util.release_interface(dev, intf_num)
        except:
            pass
        if virtual_proc:
            virtual_proc.terminate()

if __name__ == "__main__":
    main()