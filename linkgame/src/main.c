#include <gint/display.h>
#include <gint/keyboard.h>
#include <gint/gint.h>
#include <stdio.h>

/* =====================================================================
 * LinkGame - mini jeu 2 perso par le port 3-pin (fx-9860G)
 *
 * Les deux calculatrices lancent ce meme add-in et sont reliees par le
 * cable 3-pin. Chacune bouge son personnage (carre plein) avec les
 * fleches ; la position est envoyee par le port serie et la position de
 * l'adversaire (carre vide) est affichee. C'est tout : map + 2 perso +
 * synchronisation.
 *
 * Le port serie n'a pas de driver dans gint -> on appelle les syscalls
 * de l'OS (table 0x80010070) avec gint_world_switch(), voir syscalls.S.
 *
 * Protocole utilise :  "P" <x> <y>   (x = colonne 0..19, y = ligne 0..5)
 * Une trame par envoi. Les coordonnees ont toujours une valeur < 'P'
 * (0x50) et servent donc de resynchronisation naturelle si un octet
 * est perdu. La derniere position recue gagne ; chaque cote re-emet
 * sa position si elle change, plus un battement periodique.
 *
 * Vitesse : 115200 baud, 8 bits, sans parite, 1 bit d'arret (8N1).
 *
 * EXIT / AC/ON = quitter
 * ===================================================================== */

/* --- Syscalls serie OS (declarations dans syscalls.S) --- */
extern int Serial_Open(unsigned char const *mode);
extern int Serial_Close(int mode);
extern int Serial_IsOpen(void);
extern int Serial_Avail(void);
extern int Serial_ReadByte(unsigned char *byte);
extern int Serial_TxSpace(void);
extern int Serial_WriteByte(unsigned char byte);
extern int Serial_ClearRX(void);

/* --- Constantes du jeu --- */
#define MAP_W 20   /* colonnes */
#define MAP_H 5    /* lignes */
#define TILE_W 6   /* pixels par colonne */
#define TILE_H 8   /* pixels par ligne */
#define MAP_X 4
#define MAP_Y 18

#define HDR 'P'

#define MOVE_EVERY  5      /* premier pas tous les N frames (~80 ms) */
#define HEARTBEAT   20     /* frames entre deux envois de survie */
#define LINK_TIMEOUT 45    /* frames sans reception = lien coupe */

/* --- Etat global --- */
static int x1 = 1, y1 = 1;                    /* votre perso (plein) */
static int x2 = MAP_W - 2, y2 = MAP_H - 2;    /* adversaire (vide) */

static unsigned int frame;       /* compteur de frames */
static unsigned int last_rx;     /* frame de la derniere trame recue */
static unsigned int rx_count;    /* nombre de trames recues */
static int rx_phase;             /* machine a etats de reception */
static unsigned char rx_x;
static int tx_dirty;             /* une position est a envoyer */
static unsigned int since_send;  /* frames depuis le dernier envoi */
static int link_open;            /* port serie ouvert ? */

/* ===================== Wrappers serie 3-pin ===================== */

static int ser_open(void)
{
    unsigned char mode[6] = { 0, 9, 0, 0, 0, 0 }; /* 115200 baud 8N1 */
    int st = gint_world_switch(GINT_CALL(Serial_Open, mode));
    /* 0 = ouvert, 3 = deja ouvert : dans les deux cas c'est bon */
    return (st == 0 || st == 3);
}

static int ser_avail(void)
{
    return gint_world_switch(GINT_CALL(Serial_Avail));
}

static int ser_read_byte(unsigned char *byte)
{
    return gint_world_switch(GINT_CALL(Serial_ReadByte, byte));
}

static int ser_tx_space(void)
{
    return gint_world_switch(GINT_CALL(Serial_TxSpace));
}

static void ser_write_byte(unsigned char byte)
{
    gint_world_switch(GINT_CALL(Serial_WriteByte, (int)byte));
}

/* Reception : prouve les trames "P x y" et met x2/y2 a jour */
static void ser_rx(void)
{
    if(!link_open)
        return;

    int n = ser_avail();
    while(n-- > 0) {
        unsigned char b;
        if(ser_read_byte(&b) != 0)
            break;

        if(rx_phase == 0) {
            if(b == HDR)
                rx_phase = 1;
        }
        else if(rx_phase == 1) {
            rx_x = b;
            rx_phase = 2;
        }
        else {
            /* positions valides toujours < 'P' : un octet parasite ne
               peut pas passer pour un en-tete */
            if(rx_x < MAP_W && b < MAP_H) {
                x2 = rx_x;
                y2 = b;
                last_rx = frame;
                rx_count++;
            }
            rx_phase = 0;
        }
    }
}

/* Emission : si position en attente ou battement periodique, envoyer */
static void ser_tx(void)
{
    unsigned char pkt[3];
    if(!link_open)
        return;

    since_send++;
    if(!tx_dirty && since_send < HEARTBEAT)
        return;

    if(ser_tx_space() < 3) {
        /* buffer plein : on abandonne, la derniere position gagne */
        if(!tx_dirty)
            since_send = 0;
        return;
    }

    pkt[0] = HDR;
    pkt[1] = (unsigned char)x1;
    pkt[2] = (unsigned char)y1;
    ser_write_byte(pkt[0]);
    ser_write_byte(pkt[1]);
    ser_write_byte(pkt[2]);

    tx_dirty = 0;
    since_send = 0;
}

/* ===================== Le jeu ===================== */

static void handle_input(void)
{
    static unsigned int step;
    int nx, ny;

    step++;
    if(step % MOVE_EVERY)
        return;

    nx = x1;
    ny = y1;
    if(keydown(KEY_LEFT)  && nx > 0)       nx--;
    if(keydown(KEY_RIGHT) && nx < MAP_W-1) nx++;
    if(keydown(KEY_UP)    && ny > 0)       ny--;
    if(keydown(KEY_DOWN)  && ny < MAP_H-1) ny++;

    if(nx != x1 || ny != y1) {
        x1 = nx;
        y1 = ny;
        tx_dirty = 1;
    }
}

static void draw_box(int col, int row, int hollow)
{
    int x = MAP_X + col * TILE_W;
    int y = MAP_Y + row * TILE_H;

    if(hollow)
        drect_border(x, y, x + TILE_W - 1, y + TILE_H - 1,
                     C_WHITE, 2, C_BLACK);
    else
        drect(x, y, x + TILE_W - 1, y + TILE_H - 1, C_BLACK);
}

static void draw_scene(void)
{
    char txt[24];
    int link_up = (frame - last_rx) < LINK_TIMEOUT;

    dclear(C_WHITE);

    dtext(1, 1, C_BLACK, "3PIN LINKGAME");

    /* indicateur de lien en haut a droite : plein = OK, vide = coupe */
    if(link_up && link_open)
        drect(MAP_X + MAP_W * TILE_W - 7, 1,
              MAP_X + MAP_W * TILE_W - 2, 6, C_BLACK);
    else
        drect_border(MAP_X + MAP_W * TILE_W - 7, 1,
                     MAP_X + MAP_W * TILE_W - 2, 6, C_WHITE, 2, C_BLACK);

    /* cadre de la map */
    drect_border(MAP_X - 1, MAP_Y - 1,
                 MAP_X + MAP_W * TILE_W, MAP_Y + MAP_H * TILE_H,
                 C_WHITE, 1, C_BLACK);

    draw_box(x1, y1, 0);
    draw_box(x2, y2, 1);

    snprintf(txt, sizeof txt, "Vous %d,%d  Adv %d,%d  #%d",
             x1, y1, x2, y2, (int)rx_count);
    dtext(1, 9, C_BLACK, txt);
}

int main(void)
{
    link_open = ser_open();
    if(link_open)
        gint_world_switch(GINT_CALL(Serial_ClearRX));

    while(1) {
        pollevent();

        handle_input();
        ser_rx();
        ser_tx();

        draw_scene();
        dupdate();

        if(keydown(KEY_ACON) || keydown(KEY_EXIT))
            break;

        /* ~16 ms par frame */
        for(volatile int i = 0; i < 80000; i++);
        frame++;
    }

    if(link_open)
        gint_world_switch(GINT_CALL(Serial_Close, 1));

    dclear(C_WHITE);
    dupdate();
    return 0;
}