#include <gint/display.h>
#include <gint/keyboard.h>
#include <gint/usb.h>
#include <gint/usb-ff-bulk.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>

void display_mono_image(uint8_t *pixels, int width, int height) {
    int bytes_per_row = (width + 7) >> 3;
    for(int y = 0; y < height && y < 64; y++) {
        for(int x = 0; x < width && x < 128; x++) {
            int byte_idx = y * bytes_per_row + (x >> 3);
            int bit_idx  = 7 - (x & 7);
            if(pixels[byte_idx] & (1 << bit_idx))
                dpixel(x, y, C_BLACK);
        }
    }
}

uint32_t read_exact(int pipe, void *buf, uint32_t n) {
    uint32_t got = 0, r;
    while(got < n) {
        r = usb_read_sync(pipe, (char*)buf + got, n - got, false);
        if(r <= 0) break;
        got += r;
    }
    return got;
}

uint32_t read_le32(uint8_t *buf) {
    return buf[0] | (buf[1]<<8) | (buf[2]<<16) | (buf[3]<<24);
}

int main(void)
{
    usb_interface_t const *intf[] = { &usb_ff_bulk, NULL };
    usb_open(intf, GINT_CALL_NULL);
    usb_open_wait();

    dclear(C_WHITE);
    dtext(1, 1, C_BLACK, "Attente stream...");
    dtext(1, 15, C_BLACK, "AC/ON=quit");
    dupdate();

    // Buffer réutilisable pour la plus grande frame possible
    // 128*64/8 + 12 (img header) = 1036 octets
    uint8_t buffer[1036];

    while(1) {
        // Vérifier quitter
        key_event_t ev = pollevent();
        if(ev.type == KEYEV_DOWN && ev.key == KEY_ACON) break;

        struct usb_fxlink_header h;
        if(!usb_fxlink_handle_messages(&h)) continue;

        if(h.application[0] != 'f' || h.size > sizeof(buffer)) {
            usb_fxlink_drop_transaction();
            continue;
        }

        int pipe = usb_ff_bulk_input();
        uint32_t got = read_exact(pipe, buffer, h.size);

        if(got < 12) continue;

        uint32_t width  = read_le32(buffer);
        uint32_t height = read_le32(buffer + 4);
        uint32_t format = read_le32(buffer + 8);

        if(format == 1) {
            dclear(C_WHITE);
            display_mono_image(buffer + 12, width, height);
            dupdate();
        }
        // Pas de free, pas de drop, on reboucle direct
    }

    usb_close();
    return 1;
}