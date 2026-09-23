#include <gint/display.h>
#include <gint/keyboard.h>
#include <gint/usb.h>
#include <gint/usb-ff-bulk.h>
#include <string.h>
#include <stdio.h>

/*
 * GamePad Controller - add-in pour Casio fx-9860G
 *
 * Scanne le clavier et envoie l'etat de 32 touches au PC
 * via le protocole fxlink (USB bulk).
 *
 * Protocole: "S" + 16 hex digits (bitmap 64 bits)
 *   - Bit i = 1 si la touche i est enfoncee
 *   - Un message est envoye uniquement quand l'etat change
 *
 * AC/ON = quitter
 */

/* Key codes (must match Python mapping) */
enum {
    /* D-Pad */
    KC_UP      = 0x01,
    KC_DOWN    = 0x02,
    KC_LEFT    = 0x03,
    KC_RIGHT   = 0x04,
    /* Action */
    KC_EXE     = 0x05,
    KC_EXIT    = 0x06,
    /* Function */
    KC_F1      = 0x11,
    KC_F2      = 0x12,
    KC_F3      = 0x13,
    KC_F4      = 0x14,
    KC_F5      = 0x15,
    KC_F6      = 0x16,
    /* Modifier */
    KC_SHIFT   = 0x21,
    KC_ALPHA   = 0x22,
    KC_OPTN    = 0x23,
    KC_MENU    = 0x24,
    KC_DEL     = 0x25,
    KC_VARS    = 0x26,
    /* Numbers */
    KC_1       = 0x31,
    KC_2       = 0x32,
    KC_3       = 0x33,
    KC_4       = 0x34,
    KC_5       = 0x35,
    KC_6       = 0x36,
    KC_7       = 0x37,
    KC_8       = 0x38,
    KC_9       = 0x39,
    KC_0       = 0x30,
    /* Operators */
    KC_ADD     = 0x41,
    KC_SUB     = 0x42,
    KC_MUL     = 0x43,
    KC_DIV     = 0x44,
    /* Point decimal */
    KC_DOT     = 0x2E,
};

typedef struct {
    int gint_key;
    int code;
} KeyMap;

/* Ordre = position du bit dans la bitmap (0..31) */
static const KeyMap key_map[] = {
    {KEY_UP,     KC_UP},     /* bit 0 */
    {KEY_DOWN,   KC_DOWN},   /* bit 1 */
    {KEY_LEFT,   KC_LEFT},   /* bit 2 */
    {KEY_RIGHT,  KC_RIGHT},  /* bit 3 */
    {KEY_EXE,    KC_EXE},    /* bit 4 */
    {KEY_EXIT,   KC_EXIT},   /* bit 5 */
    {KEY_F1,     KC_F1},     /* bit 6 */
    {KEY_F2,     KC_F2},     /* bit 7 */
    {KEY_F3,     KC_F3},     /* bit 8 */
    {KEY_F4,     KC_F4},     /* bit 9 */
    {KEY_F5,     KC_F5},     /* bit 10 */
    {KEY_F6,     KC_F6},     /* bit 11 */
    {KEY_SHIFT,  KC_SHIFT},  /* bit 12 */
    {KEY_ALPHA,  KC_ALPHA},  /* bit 13 */
    {KEY_OPTN,   KC_OPTN},  /* bit 14 */
    {KEY_MENU,   KC_MENU},  /* bit 15 */
    {KEY_DEL,    KC_DEL},    /* bit 16 */
    {KEY_VARS,   KC_VARS},   /* bit 17 */
    {KEY_1,      KC_1},      /* bit 18 */
    {KEY_2,      KC_2},      /* bit 19 */
    {KEY_3,      KC_3},      /* bit 20 */
    {KEY_4,      KC_4},      /* bit 21 */
    {KEY_5,      KC_5},      /* bit 22 */
    {KEY_6,      KC_6},      /* bit 23 */
    {KEY_7,      KC_7},      /* bit 24 */
    {KEY_8,      KC_8},      /* bit 25 */
    {KEY_9,      KC_9},      /* bit 26 */
    {KEY_0,      KC_0},      /* bit 27 */
    {KEY_ADD,    KC_ADD},    /* bit 28 */
    {KEY_SUB,    KC_SUB},    /* bit 29 */
    {KEY_MUL,    KC_MUL},    /* bit 30 */
    {KEY_DIV,    KC_DIV},    /* bit 31 */
    {KEY_DOT,    KC_DOT},    /* bit 32 */
};

#define NUM_KEYS (sizeof(key_map) / sizeof(key_map[0]))

static void send_state(uint64_t bitmap) {
    char msg[18];
    msg[0] = 'S';
    static const char hex[] = "0123456789ABCDEF";
    for(int i = 0; i < 16; i++) {
        msg[1 + i] = hex[(bitmap >> (60 - i * 4)) & 0xF];
    }
    msg[17] = '\0';
    usb_fxlink_text(msg, 17);
}

int main(void) {
    usb_interface_t const *intf[] = { &usb_ff_bulk, NULL };
    usb_open(intf, GINT_CALL_NULL);
    usb_open_wait();

    uint64_t prev_bitmap = 0;
    int frame = 0;

    dclear(C_WHITE);
    dtext(1, 1,  C_BLACK, "GamePad Controller");
    dtext(1, 15, C_BLACK, "Connecte au PC");
    dtext(1, 30, C_BLACK, "AC/ON = quitter");
    dupdate();

    while(1) {
        /* Mettre a jour la matrice clavier */
        pollevent();

        /* Scanner toutes les touches */
        uint64_t bitmap = 0;
        for(unsigned int i = 0; i < NUM_KEYS; i++) {
            if(keydown(key_map[i].gint_key)) {
                bitmap |= (1ULL << i);
            }
        }

        /* Envoyer si changement */
        if(bitmap != prev_bitmap) {
            send_state(bitmap);
            prev_bitmap = bitmap;
        }

        /* Quitter sur AC/ON */
        if(keydown(KEY_ACON)) break;

        /* Affichage (toutes les 30 frames ~0.5s) */
        if(frame % 30 == 0) {
            dclear(C_WHITE);
            dtext(1, 1,  C_BLACK, "GamePad Active");
            char buf[32];
            snprintf(buf, sizeof(buf), "State: %016llX", (unsigned long long)bitmap);
            dtext(1, 15, C_BLACK, buf);
            snprintf(buf, sizeof(buf), "Frame: %d", frame);
            dtext(1, 30, C_BLACK, buf);
            dtext(1, 45, C_BLACK, "AC/ON = quit");
            dupdate();
        }

        frame++;

        /* Delai ~16ms (60 Hz) */
        for(volatile int i = 0; i < 80000; i++);
    }

    usb_close();
    return 0;
}
