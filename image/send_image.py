#!/usr/bin/env python3
"""
Script pour envoyer une image monochrome a la calculatrice Casio via USB (protocole fxlink)
Usage: python3 send_image.py image.png
"""

import sys
import time
import struct

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erreur: pyusb n'est pas installe.")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Erreur: Pillow n'est pas installe.")
    sys.exit(1)

CASIO_VID = 0x07cf

def find_calculator():
    devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
    for dev in devices:
        for cfg in dev:
            for intf in cfg:
                if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
                    return dev, intf
    return None, None

def send_image(image_path, threshold=128):
    dev, intf = find_calculator()
    if dev is None:
        print("Calculatrice non trouvee.")
        return False
    
    print(f"Calculatrice trouvee: {dev.idVendor:04x}:{dev.idProduct:04x}")
    
    try:
        dev.set_configuration()
    except:
        pass
    
    cfg = dev.get_active_configuration()
    intf_num = None
    ep_out = None
    
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
    
    try:
        # Convertir l'image
        img = Image.open(image_path).convert('L')
        width, height = img.size
        print(f"Image originale: {width}x{height}")
        
        if width > 128 or height > 64:
            print("Redimensionnement pour fx-9860G...")
            img.thumbnail((128, 64), Image.Resampling.LANCZOS)
            width, height = img.size
            print(f"Nouvelle taille: {width}x{height}")
        
        img_mono = img.point(lambda x: 255 if x > threshold else 0, mode='1')
        
        # Convertir en binaire (1 bit/pixel, MSB first)
        bytes_per_row = (width + 7) >> 3
        pixel_data = bytearray(bytes_per_row * height)
        
        for y in range(height):
            for x in range(width):
                if img_mono.getpixel((x, y)) == 0:  # Pixel noir
                    byte_idx = y * bytes_per_row + (x >> 3)
                    bit_idx = 7 - (x & 7)
                    pixel_data[byte_idx] |= (1 << bit_idx)
        
        print(f"Image: {width}x{height}, {len(pixel_data)} octets")
        
        # Header fxlink
        app = b'fxlink' + b'\x00' * 10
        typ = b'image' + b'\x00' * 11
        
        # Header image
        img_header = struct.pack('<III', width, height, 1)
        
        # Payload complet
        payload = img_header + bytes(pixel_data)
        
        # Header fxlink avec taille du payload
        header = struct.pack('<III16s16s',
                             0x00000100,
                             len(payload),
                             0,
                             app,
                             typ)
        
        print(f"Header (hex): {header.hex()}")
        print(f"Payload (hex debut): {payload[:20].hex()}...")
        print(f"Envoi header ({len(header)} octets) + payload ({len(payload)} octets)")
        
        # Envoyer header puis payload
        ep_out.write(header + payload)
        time.sleep(0.05)
        
        print("Transmission terminee!")
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            usb.util.release_interface(dev, intf_num)
        except:
            pass
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_image.py <image> [seuil]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    threshold = 128
    if len(sys.argv) > 2:
        threshold = int(sys.argv[2])
    
    print(f"Envoi de l'image: {image_path}")
    time.sleep(0.5)
    
    success = send_image(image_path, threshold)
    sys.exit(0 if success else 1)
