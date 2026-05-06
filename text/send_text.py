#!/usr/bin/env python3
"""
Script pour envoyer du texte a la calculatrice Casio via USB (protocole fxlink)
Usage: python3 send_text.py "texte a envoyer"
"""

import sys
import time
import struct

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erreur: pyusb n'est pas installe.")
    print("Installez-le avec: pip install pyusb")
    sys.exit(1)

# IDs USB de Casio
CASIO_VID = 0x07cf  # Vendor ID Casio

def find_calculator():
    """Trouve la calculatrice connectee"""
    devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
    
    for dev in devices:
        # Parcourir les configurations
        for cfg in dev:
            for intf in cfg:
                # Interface fxlink (bulk transfer)
                if intf.bInterfaceClass == 0xff and \
                   intf.bInterfaceSubClass == 0x77:
                    return dev, intf
    return None, None

def send_text(text):
    """Envoie du texte a la calculatrice via le protocole fxlink"""
    
    dev, intf = find_calculator()
    if dev is None:
        print("Calculatrice non trouvee.")
        print("Verifiez que l'add-in est lance et l'USB connecte.")
        return False
    
    print(f"Calculatrice trouvee: {dev.idVendor:04x}:{dev.idProduct:04x}")
    
    # Revenir au premier mode de configuration
    try:
        dev.set_configuration()
    except:
        pass
    
    cfg = dev.get_active_configuration()
    
    # Trouver l'interface fxlink
    intf_num = None
    ep_out = None
    
    for intf in cfg:
        if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
            intf_num = intf.bInterfaceNumber
            # Chercher l'endpoint OUT
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == \
                   usb.util.ENDPOINT_OUT:
                    ep_out = ep
                    break
            break
    
    if intf_num is None or ep_out is None:
        print("Interface fxlink non trouvee")
        return False
    
    print(f"Interface: {intf_num}, Endpoint OUT: 0x{ep_out.bEndpointAddress:02x}")
    
    # Detacher le driver kernel si necessaire
    try:
        if dev.is_kernel_driver_active(intf_num):
            dev.detach_kernel_driver(intf_num)
    except:
        pass
    
    # Claimer l'interface
    usb.util.claim_interface(dev, intf_num)
    
    # Construire le header fxlink (little-endian)
    text_bytes = text.encode('utf-8')
    
    # Header: version(4), size(4), transfer_size(4), app(16), type(16)
    # "fxlink" et "text" doivent etre pads a 16 octets
    app = b'fxlink' + b'\x00' * (16 - 6)
    typ = b'text' + b'\x00' * (16 - 4)
    
    header = struct.pack('<III16s16s',
                       0x00000100,           # version
                       len(text_bytes),       # taille des donnees
                       0,                     # transfer_size
                       app,
                       typ)
    
    try:
        # Envoyer le header
        ep_out.write(header)
        print(f"Header envoye: {len(header)} octets")
        time.sleep(0.01)
        
        # Envoyer le texte
        ep_out.write(text_bytes)
        print(f"Texte envoye: '{text}' ({len(text_bytes)} octets)")
        time.sleep(0.01)
        
    except Exception as e:
        print(f"Erreur: {e}")
        usb.util.release_interface(dev, intf_num)
        return False
    
    # Liberer l'interface
    usb.util.release_interface(dev, intf_num)
    
    print("Transmission terminee!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_text.py \"texte a envoyer\"")
        print("Exemple: python3 send_text.py \"Hello depuis le PC!\"")
        sys.exit(1)
    
    text = ' '.join(sys.argv[1:])
    print(f"Envoi du texte: '{text}'")
    
    # Attendre que la calculatrice soit prete
    time.sleep(0.5)
    
    success = send_text(text)
    sys.exit(0 if success else 1)
