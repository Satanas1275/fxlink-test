import sys
import subprocess
import numpy as np
import struct

TARGET_W = 128
TARGET_H = 64
BYTES_PER_FRAME = (TARGET_W * TARGET_H) // 8  # 1024 octets

def convert_video(input_path, output_path, fps_target=20, threshold=128):
    # D'abord récupérer la durée via ffprobe
    probe = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_path
    ], capture_output=True, text=True)

    duration = float(probe.stdout.strip())
    expected_out = int(duration * fps_target)

    print(f"Durée source  : {duration:.1f}s")
    print(f"Sortie cible  : {fps_target} fps → ~{expected_out} frames")
    print(f"Taille estimée: {expected_out * BYTES_PER_FRAME / 1024 / 1024:.1f} MB")

    # ffmpeg decode + resize + grayscale → rawvideo pipe
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', f'fps={fps_target},scale={TARGET_W}:{TARGET_H}',
        '-pix_fmt', 'gray',
        '-f', 'rawvideo',
        '-v', 'error',
        'pipe:1'
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    frames_written = 0

    with open(output_path, 'wb') as f:
        # Header: magic(4) + fps(4) + frame_count(4) + width(2) + height(2)
        f.write(b'FXBV')
        f.write(struct.pack('<I', fps_target))
        f.write(struct.pack('<I', 0))  # placeholder
        f.write(struct.pack('<HH', TARGET_W, TARGET_H))

        while True:
            # Lire une frame brute (1 octet par pixel en grayscale)
            raw = proc.stdout.read(TARGET_W * TARGET_H)
            if len(raw) < TARGET_W * TARGET_H:
                break

            frame = np.frombuffer(raw, dtype=np.uint8).reshape(TARGET_H, TARGET_W)

            # Binariser
            binary = (frame < threshold).astype(np.uint8)  # 1 = noir

            # Convertir en 1bpp MSB first via numpy (rapide)
            packed = np.packbits(binary, axis=1, bitorder='big')
            f.write(packed.tobytes())

            frames_written += 1

            if frames_written % 200 == 0:
                pct = frames_written / expected_out * 100
                print(f"  {frames_written}/{expected_out} frames ({pct:.1f}%)")

        # Réécrire frame_count
        f.seek(8)
        f.write(struct.pack('<I', frames_written))

    proc.wait()

    print(f"\nTerminé: {frames_written} frames → {output_path}")
    print(f"Taille finale: {(frames_written * BYTES_PER_FRAME + 16) / 1024 / 1024:.2f} MB")
    print(f"Durée: {frames_written / fps_target:.1f}s")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 convert_video.py <input.webm> <output.bin> [seuil]")
        sys.exit(1)
clear
    threshold = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    success = convert_video(sys.argv[1], sys.argv[2], fps_target=20, threshold=threshold)
    sys.exit(0 if success else 1)