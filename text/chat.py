#!/usr/bin/env python3
"""
Script interactif pour communiquer avec la calculatrice Casio via USB
Tape du texte et appuie sur Entree pour envoyer
Les messages recus s'affichent automatiquement
"""

import sys
import time
import struct
import threading

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erreur: pyusb n'est pas installe.")
    print("Installez-le avec: pip install pyusb")
    sys.exit(1)

# IDs USB de Casio
CASIO_VID = 0x07cf

# Pour arreter le thread de reception
running = True

def find_calculator():
    """Trouve la calculatrice connectee"""
    devices = usb.core.find(find_all=True, idVendor=CASIO_VID)
    
    for dev in devices:
        for cfg in dev:
            for intf in cfg:
                if intf.bInterfaceClass == 0xff and \
                   intf.bInterfaceSubClass == 0x77:
                    return dev, intf
    return None, None

def receive_messages(dev, ep_in):
    """Thread de reception des messages de la calculatrice"""
    global running
    
    while running:
        try:
            # Lire le header fxlink (44 octets)
            data = dev.read(ep_in.bEndpointAddress, 44, timeout=100)
            if len(data) == 44:
                # Parser le header
                version, size, transfer_size = struct.unpack_from('<III', data, 0)
                app = data[12:28].split(b'\x00')[0].decode('utf-8', errors='ignore')
                typ = data[28:44].split(b'\x00')[0].decode('utf-8', errors='ignore')
                
                # Lire les donnees
                received = b''
                remaining = size
                while remaining > 0:
                    chunk = dev.read(ep_in.bEndpointAddress, 
                                   min(remaining, 64), timeout=1000)
                    received += chunk
                    remaining -= len(chunk)
                
                text = received.decode('utf-8', errors='ignore')
                print(f"\n[Calculatrice]: {text}")
                print("> ", end='', flush=True)
        except usb.core.USBError as e:
            if e.args[0] != -116:  # Timeout, c'est normal
                if running:
                    print(f"\nErreur USB: {e}")
                    break
        except Exception as e:
            if running:
                print(f"\nErreur reception: {e}")
                break
        
        time.sleep(0.01)

def send_to_calculator(dev, ep_out, text):
    """Envoie du texte a la calculatrice"""
    text_bytes = text.encode('utf-8')
    
    # Preparer le header
    app = b'fxlink' + b'\x00' * (16 - 6)
    typ = b'text' + b'\x00' * (16 - 4)
    
    header = struct.pack('<III16s16s',
                       0x00000100,
                       len(text_bytes),
                       0,
                       app,
                       typ)
    
    try:
        ep_out.write(header)
        time.sleep(0.01)
        ep_out.write(text_bytes)
        time.sleep(0.01)
        return True
    except Exception as e:
        print(f"Erreur envoi: {e}")
        return False

def main():
    global running
    
    print("Recherche de la calculatrice...")
    dev, intf = find_calculator()
    
    if dev is None:
        print("Calculatrice non trouvee.")
        print("Verifiez que:")
        print("  - La calculatrice est connectee")
        print("  - L'add-in est lance")
        print("  - L'USB est connecte")
        return
    
    print(f"Calculatrice trouvee: {dev.idVendor:04x}:{dev.idProduct:04x}")
    
    # Configuration
    try:
        dev.set_configuration()
    except:
        pass
    
    cfg = dev.get_active_configuration()
    
    intf_num = None
    ep_out = None
    ep_in = None
    
    for intf in cfg:
        if intf.bInterfaceClass == 0xff and intf.bInterfaceSubClass == 0x77:
            intf_num = intf.bInterfaceNumber
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == \
                   usb.util.ENDPOINT_OUT:
                    ep_out = ep
                else:
                    ep_in = ep
            break
    
    if intf_num is None or ep_out is None or ep_in is None:
        print("Erreur: interfaces USB incompletes")
        return
    
    print(f"Interface: {intf_num}")
    print(f"Endpoint OUT: 0x{ep_out.bEndpointAddress:02x}")
    print(f"Endpoint IN: 0x{ep_in.bEndpointAddress:02x}")
    
    # Detacher le driver kernel
    try:
        if dev.is_kernel_driver_active(intf_num):
            dev.detach_kernel_driver(intf_num)
    except:
        pass
    
    # Claimer l'interface
    usb.util.claim_interface(dev, intf_num)
    
    print("\nMode interactif demarre!")
    print("Tape 'quit' pour quitter")
    print("Tape ton message et appuie sur Entree\n")
    
    # Demarrer le thread de reception
    recv_thread = threading.Thread(target=receive_messages, args=(dev, ep_in))
    recv_thread.daemon = True
    recv_thread.start()
    
    # Boucle principale d'envoi
    try:
        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            text = input()
            
            if text.lower() == 'quit':
                break
            
            if text:
                send_to_calculator(dev, ep_out, text)
    
    except KeyboardInterrupt:
        print("\n\nInterruption utilisateur")
    except EOFError:
        print("\n\nFin de l'entree")
    finally:
        running = False
        time.sleep(0.5)
        usb.util.release_interface(dev, intf_num)
        print("Deconnecte.")

if __name__ == "__main__":
    main()
