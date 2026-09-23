#!/usr/bin/env python3
"""
GamePad Controller - Casio fx-9860G → PC clavier/souris (evdev/uinput)

Recoit l'etat des touches de la calculatrice via USB (protocole fxlink)
et le mappe vers des entrees clavier/souris PC via evdev (Wayland-compatible).

Usage:
    sudo python3 keypad_controller.py [mapping.json] [--mouse-speed N] [-v]

Dependances:
    pip install pyusb evdev
"""

import sys
import os
import time
import struct
import json
import signal
import argparse
import subprocess

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("pyusb manquant: pip install pyusb")

try:
    from evdev import UInput, ecodes
except ImportError:
    sys.exit("evdev manquant: pip install evdev")

# ── Constants ──────────────────────────────────────────────────────────────────

CASIO_VID       = 0x07cf
FXLINK_HDR_SIZE = 44

# ── Bit position → key name (ordre = key_map[] du C) ───────────────────────────

BIT_TO_NAME = {
    0: 'UP',    1: 'DOWN',  2: 'LEFT',   3: 'RIGHT',
    4: 'EXE',   5: 'EXIT',
    6: 'F1',    7: 'F2',    8: 'F3',     9: 'F4',    10: 'F5',   11: 'F6',
    12: 'SHIFT', 13: 'ALPHA', 14: 'OPTN', 15: 'MENU', 16: 'DEL', 17: 'VARS',
    18: '1',    19: '2',    20: '3',     21: '4',    22: '5',
    23: '6',    24: '7',    25: '8',     26: '9',    27: '0',
    28: 'ADD',  29: 'SUB',  30: 'MUL',   31: 'DIV',
    32: 'DOT',
}

# ── evdev keycode mapping ──────────────────────────────────────────────────────

EVDEV_KEYS = {
    'up': ecodes.KEY_UP,        'down': ecodes.KEY_DOWN,
    'left': ecodes.KEY_LEFT,    'right': ecodes.KEY_RIGHT,
    'space': ecodes.KEY_SPACE,  'enter': ecodes.KEY_ENTER,
    'shift': ecodes.KEY_LEFTSHIFT,  'ctrl': ecodes.KEY_LEFTCTRL,
    'alt': ecodes.KEY_LEFTALT,  'escape': ecodes.KEY_ESC,
    'tab': ecodes.KEY_TAB,      'backspace': ecodes.KEY_BACKSPACE,
    'delete': ecodes.KEY_DELETE,
    'f1': ecodes.KEY_F1,  'f2': ecodes.KEY_F2,  'f3': ecodes.KEY_F3,
    'f4': ecodes.KEY_F4,  'f5': ecodes.KEY_F5,  'f6': ecodes.KEY_F6,
    'f7': ecodes.KEY_F7,  'f8': ecodes.KEY_F8,  'f9': ecodes.KEY_F9,
    'f10': ecodes.KEY_F10, 'f11': ecodes.KEY_F11, 'f12': ecodes.KEY_F12,
    'home': ecodes.KEY_HOME,    'end': ecodes.KEY_END,
    'page_up': ecodes.KEY_PAGEUP, 'page_down': ecodes.KEY_PAGEDOWN,
    'insert': ecodes.KEY_INSERT,  'pause': ecodes.KEY_PAUSE,
    'semicolon': ecodes.KEY_SEMICOLON,
    # Letters
    'a': ecodes.KEY_A, 'b': ecodes.KEY_B, 'c': ecodes.KEY_C, 'd': ecodes.KEY_D,
    'e': ecodes.KEY_E, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G, 'h': ecodes.KEY_H,
    'i': ecodes.KEY_I, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L,
    'm': ecodes.KEY_M, 'n': ecodes.KEY_N, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
    'q': ecodes.KEY_Q, 'r': ecodes.KEY_R, 's': ecodes.KEY_S, 't': ecodes.KEY_T,
    'u': ecodes.KEY_U, 'v': ecodes.KEY_V, 'w': ecodes.KEY_W, 'x': ecodes.KEY_X,
    'y': ecodes.KEY_Y, 'z': ecodes.KEY_Z,
    # Numbers
    '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3,
    '4': ecodes.KEY_4, '5': ecodes.KEY_5, '6': ecodes.KEY_6,
    '7': ecodes.KEY_7, '8': ecodes.KEY_8, '9': ecodes.KEY_9, '0': ecodes.KEY_0,
}

# ── Caracteres francais (clavier AZERTY / layout fr) ──────────────────────────
# Sur un layout AZERTY (fr), une lettre ne correspond pas au code du meme nom :
#   - la touche physique "Z" (QWERTY-W) produit 'z'  -> 'z' = KEY_W
#   - la touche physique "Q" (QWERTY-A) produit 'q'  -> 'q' = KEY_A
#   - 'w' et 'a' sont sur les positions QWERTY-Z / QWERTY-Q
# Ici on mappe le CARACTERE a produire vers le code evdev correct pour le layout
# fr. Les touches 1..9 du AZERTY produisent directement : & é " ' ( - è _ ç.

FR_KEYS = {
    'a':  ecodes.KEY_Q, 'z':  ecodes.KEY_W, 'w':  ecodes.KEY_Z,
    'q':  ecodes.KEY_A,
    'e':  ecodes.KEY_E, 'r':  ecodes.KEY_R, 't':  ecodes.KEY_T,
    'y':  ecodes.KEY_Y, 'u':  ecodes.KEY_U, 'i':  ecodes.KEY_I,
    'o':  ecodes.KEY_O, 'p':  ecodes.KEY_P,
    's':  ecodes.KEY_S, 'd':  ecodes.KEY_D, 'f':  ecodes.KEY_F,
    'g':  ecodes.KEY_G, 'h':  ecodes.KEY_H, 'j':  ecodes.KEY_J,
    'k':  ecodes.KEY_K, 'l':  ecodes.KEY_L, 'm':  ecodes.KEY_SEMICOLON,
    'x':  ecodes.KEY_X, 'c':  ecodes.KEY_C, 'v':  ecodes.KEY_V,
    'b':  ecodes.KEY_B, 'n':  ecodes.KEY_N,
    '&':  ecodes.KEY_1, 'é':  ecodes.KEY_2, '"':  ecodes.KEY_3,
    "'":  ecodes.KEY_4, '(':  ecodes.KEY_5, '-':  ecodes.KEY_6,
    'è':  ecodes.KEY_7, '_':  ecodes.KEY_8, 'ç':  ecodes.KEY_9,
    'à':  ecodes.KEY_0,
}

# ── Default mapping (Minecraft-friendly) ───────────────────────────────────────

DEFAULT_MAPPING = {
    "keyboard": {
        "UP": "w",    "DOWN": "s",    "LEFT": "a",    "RIGHT": "d",
        "EXE": "space",
        "SHIFT": "shift",
        "F1": "1",    "F2": "2",      "F3": "3",
        "F4": "e",    "F5": "f",      "F6": "ctrl",
        "OPTN": "q",  "EXIT": "escape",
        "MENU": "t",  "DEL": "r",
        "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
        "6": "6", "7": "7", "8": "8", "9": "9", "0": "0",
    },
    "mouse": {
        "speed": 10,
        "toggle": "ALPHA",
        "buttons": {
            "UP": "up",   "DOWN": "down",
            "LEFT": "left", "RIGHT": "right",
            "EXE": "left_click",
            "DEL": "right_click",
        }
    }
}


# ── Virtual devices ────────────────────────────────────────────────────────────

def create_keyboard():
    caps = {ecodes.EV_KEY: list(EVDEV_KEYS.values())}
    return UInput(caps, name="GamePad Keyboard")


def create_mouse():
    caps = {
        ecodes.EV_KEY: [
            ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
        ],
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],
    }
    return UInput(caps, name="GamePad Mouse")


# ── Controller ─────────────────────────────────────────────────────────────────

class GamePadController:
    def __init__(self, mapping=None, mouse_speed=None, verbose=False):
        self.mapping = mapping or DEFAULT_MAPPING
        self.mouse_speed = mouse_speed or self.mapping.get('mouse', {}).get('speed', 10)
        self.verbose = verbose

        self.prev_bitmap = 0
        self.pressed_keys = set()
        self.running = True

        self._acc_x = 0.0
        self._acc_y = 0.0
        self.last_move = time.monotonic()

        self.dev = None
        self.intf_num = None
        self.ep_in = None

        self.rx_buf = bytearray()
        self.kbd = None
        self.mouse = None

    def log(self, *args):
        if self.verbose:
            print(*args)

    # ── USB ────────────────────────────────────────────────────────────────

    def find_calculator(self):
        devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
        for dev in devices:
            for cfg in dev:
                for intf in cfg:
                    if (intf.bInterfaceClass == 0xff and
                            intf.bInterfaceSubClass == 0x77):
                        return dev, intf
        return None, None

    def connect(self):
        dev, intf = self.find_calculator()
        if dev is None:
            sys.exit("Calculatrice non trouvee. L'add-in GamePad est-il lance ?")

        self.log(f"Calculatrice: {dev.idVendor:04x}:{dev.idProduct:04x}")

        try:
            dev.set_configuration()
        except Exception:
            pass

        cfg = dev.get_active_configuration()
        intf_num = None
        ep_in = None

        for intf in cfg:
            if (intf.bInterfaceClass == 0xff and
                    intf.bInterfaceSubClass == 0x77):
                intf_num = intf.bInterfaceNumber
                for ep in intf:
                    if (usb.util.endpoint_direction(ep.bEndpointAddress)
                            == usb.util.ENDPOINT_IN):
                        ep_in = ep
                        break
                break

        if intf_num is None or ep_in is None:
            sys.exit("Interface fxlink non trouvee")

        try:
            if dev.is_kernel_driver_active(intf_num):
                dev.detach_kernel_driver(intf_num)
        except Exception:
            pass

        usb.util.claim_interface(dev, intf_num)

        self.dev = dev
        self.intf_num = intf_num
        self.ep_in = ep_in
        self.log(f"Connecte. IN endpoint: 0x{ep_in.bEndpointAddress:02x}")

    def disconnect(self):
        if self.dev and self.intf_num is not None:
            try:
                usb.util.release_interface(self.dev, self.intf_num)
            except Exception:
                pass

    def read_exact(self, n, timeout=100):
        while len(self.rx_buf) < n:
            try:
                chunk = bytes(self.ep_in.read(2048, timeout=timeout))
                self.rx_buf.extend(chunk)
            except usb.core.USBTimeoutError:
                return None
            except usb.core.USBError:
                return None
        data = bytes(self.rx_buf[:n])
        del self.rx_buf[:n]
        return data

    def read_fxlink_message(self, timeout=100):
        header = self.read_exact(FXLINK_HDR_SIZE, timeout=timeout)
        if not header:
            return None

        if self.verbose:
            self.log(f"  raw> {header.hex()}")

        _ver, size, _xfer = struct.unpack_from('<III', header, 0)
        app = header[12:28].rstrip(b'\x00')
        typ = header[28:44].rstrip(b'\x00')

        if self.verbose:
            self.log(f"  app={app!r} type={typ!r} size={size}")

        if app != b'fxlink':
            self.log(f"App inconnue: {app}")
            return None

        if size > 0:
            payload = self.read_exact(size, timeout=100)
            if not payload:
                return None
        else:
            payload = b''

        if typ == b'text':
            return payload.decode('ascii', errors='ignore')
        return None

    # ── Input processing ───────────────────────────────────────────────────

    def process_state(self, bitmap):
        changed = bitmap ^ self.prev_bitmap
        if not changed:
            return

        for bit in range(33):
            if changed & (1 << bit):
                pressed = bool(bitmap & (1 << bit))
                name = BIT_TO_NAME.get(bit)
                if name:
                    self.handle_key(name, pressed)

        self.prev_bitmap = bitmap

    def handle_key(self, name, pressed):
        self.handle_keyboard_key(name, pressed)
        self.handle_mouse_key(name, pressed)

    def handle_keyboard_key(self, name, pressed):
        target = self.mapping.get('keyboard', {}).get(name)
        action = "Appui " if pressed else "Relache"
        if not target:
            self.log(f"[{action}] {name} (non mappe[e])")
            return

        evdev_code = FR_KEYS.get(target)
        if evdev_code is None:
            evdev_code = EVDEV_KEYS.get(target)
        if evdev_code is None:
            self.log(f"[{action}] {name} -> PC: {target} (code inconnu)")
            return

        print(f"[{action}] {name} -> PC: {target}")

        try:
            if pressed:
                self.kbd.write(ecodes.EV_KEY, evdev_code, 1)
                self.kbd.syn()
                self.pressed_keys.add(('kb', evdev_code))
            else:
                self.kbd.write(ecodes.EV_KEY, evdev_code, 0)
                self.kbd.syn()
                self.pressed_keys.discard(('kb', evdev_code))
        except Exception as e:
            self.log(f"Erreur clavier: {e}")

    def handle_mouse_key(self, name, pressed):
        buttons = self.mapping.get('mouse', {}).get('buttons', {})
        target = buttons.get(name)

        BTN_MAP = {
            'left_click': ecodes.BTN_LEFT,
            'right_click': ecodes.BTN_RIGHT,
            'middle_click': ecodes.BTN_MIDDLE,
        }

        if target in BTN_MAP:
            action = "Appui " if pressed else "Relache"
            print(f"[{action}] {name} -> Souris: {target}")
            try:
                btn = BTN_MAP[target]
                self.mouse.write(ecodes.EV_KEY, btn, 1 if pressed else 0)
                self.mouse.syn()
                if pressed:
                    self.pressed_keys.add(('mouse', btn))
                else:
                    self.pressed_keys.discard(('mouse', btn))
            except Exception as e:
                self.log(f"Erreur souris: {e}")

    def release_all(self):
        for kind, obj in list(self.pressed_keys):
            try:
                if kind == 'kb':
                    self.kbd.write(ecodes.EV_KEY, obj, 0)
                    self.kbd.syn()
                elif kind == 'mouse':
                    self.mouse.write(ecodes.EV_KEY, obj, 0)
                    self.mouse.syn()
            except Exception:
                pass
        self.pressed_keys.clear()

    def update_mouse_movement(self):
        now = time.monotonic()
        dt = min(now - self.last_move, 0.05)
        self.last_move = now

        speed = self.mouse_speed * 100.0  # pixels par seconde

        vx = 0.0
        vy = 0.0
        if self.prev_bitmap & (1 << 0):
            vy -= speed
        if self.prev_bitmap & (1 << 1):
            vy += speed
        if self.prev_bitmap & (1 << 2):
            vx -= speed
        if self.prev_bitmap & (1 << 3):
            vx += speed

        self._acc_x += vx * dt
        self._acc_y += vy * dt

        ix = int(self._acc_x)
        iy = int(self._acc_y)
        self._acc_x -= ix
        self._acc_y -= iy

        if ix != 0 or iy != 0:
            try:
                self.mouse.write(ecodes.EV_REL, ecodes.REL_X, ix)
                self.mouse.write(ecodes.EV_REL, ecodes.REL_Y, iy)
                self.mouse.syn()
            except Exception as e:
                self.log(f"Erreur souris: {e}")

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self):
        self.kbd = create_keyboard()
        self.mouse = create_mouse()
        print(f"Devices virtuels crees: {self.kbd.name}, {self.mouse.name}")

        self.connect()
        print("GamePad actif. Ctrl+C pour quitter.")

        def on_signal(sig, frame):
            self.running = False

        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

        try:
            while self.running:
                msg = self.read_fxlink_message(timeout=5)
                if msg:
                    if self.verbose:
                        self.log(f"  texte recu> {msg!r}")
                    if msg.startswith('S') and len(msg) >= 17:
                        try:
                            bitmap = int(msg[1:17], 16)
                            self.process_state(bitmap)
                        except ValueError:
                            pass
                    elif msg.startswith('S') and len(msg) >= 9:
                        try:
                            bitmap = int(msg[1:9], 16)
                            self.process_state(bitmap)
                        except ValueError:
                            pass

                self.update_mouse_movement()
                time.sleep(0.001)
        finally:
            self.release_all()
            self.disconnect()
            self.kbd.close()
            self.mouse.close()
            print("Deconnecte.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='GamePad Controller - Casio fx-9860G → PC (evdev)'
    )
    parser.add_argument('mapping', nargs='?',
                        help='Fichier JSON de mapping')
    parser.add_argument('--mouse-speed', type=int,
                        help='Vitesse du curseur souris')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Afficher les details')
    args = parser.parse_args()

    mapping = None
    if args.mapping:
        with open(args.mapping) as f:
            mapping = json.load(f)

    controller = GamePadController(
        mapping=mapping,
        mouse_speed=args.mouse_speed,
        verbose=args.verbose,
    )
    controller.run()


if __name__ == '__main__':
    main()
