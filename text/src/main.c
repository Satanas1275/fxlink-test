#include <gint/display.h>
#include <gint/keyboard.h>
#include <gint/usb.h>
#include <gint/usb-ff-bulk.h>
#include <stdio.h>
#include <string.h>

const char* key_to_str(int key)
{
    switch(key) {
        case KEY_0: return "0";
        case KEY_1: return "1";
        case KEY_2: return "2";
        case KEY_3: return "3";
        case KEY_4: return "4";
        case KEY_5: return "5";
        case KEY_6: return "6";
        case KEY_7: return "7";
        case KEY_8: return "8";
        case KEY_9: return "9";
        case KEY_F1: return "F1";
        case KEY_F2: return "F2";
        case KEY_F3: return "F3";
        case KEY_F4: return "F4";
        case KEY_F5: return "F5";
        case KEY_F6: return "F6";
        case KEY_SHIFT: return "SHIFT";
        case KEY_OPTN: return "OPTN";
        case KEY_VARS: return "VARS";
        case KEY_MENU: return "MENU";
        case KEY_LEFT: return "LEFT";
        case KEY_UP: return "UP";
        case KEY_DOWN: return "DOWN";
        case KEY_RIGHT: return "RIGHT";
        case KEY_ALPHA: return "ALPHA";
        case KEY_SQUARE: return "x²";
        case KEY_POWER: return "^";
        case KEY_EXIT: return "EXIT";
        case KEY_XOT: return "X,θ,T";
        case KEY_LOG: return "log";
        case KEY_LN: return "ln";
        case KEY_SIN: return "sin";
        case KEY_COS: return "cos";
        case KEY_TAN: return "tan";
        case KEY_FRAC: return "a b/c";
        case KEY_FD: return "F<->D";
        case KEY_LEFTP: return "(";
        case KEY_RIGHTP: return ")";
        case KEY_COMMA: return ",";
        case KEY_ARROW: return "->";
        case KEY_DOT: return ".";
        case KEY_EXP: return "EXP";
        case KEY_NEG: return "(-)";
        case KEY_EXE: return "EXE";
        case KEY_MUL: return "×";
        case KEY_DIV: return "÷";
        case KEY_ADD: return "+";
        case KEY_SUB: return "-";
        case KEY_DEL: return "DEL";
        case KEY_ACON: return "AC/ON";
        default: return "?";
    }
}

const char* alpha_key_to_str(int key)
{
    switch(key) {
        case KEY_XOT: return "A";
        case KEY_LOG: return "B";
        case KEY_LN: return "C";
        case KEY_SIN: return "D";
        case KEY_COS: return "E";
        case KEY_TAN: return "F";
        case KEY_FRAC: return "G";
        case KEY_FD: return "H";
        case KEY_LEFTP: return "I";
        case KEY_RIGHTP: return "J";
        case KEY_COMMA: return "K";
        case KEY_ARROW: return "L";
        case KEY_7: return "M";
        case KEY_8: return "N";
        case KEY_9: return "O";
        case KEY_4: return "P";
        case KEY_5: return "Q";
        case KEY_6: return "R";
        case KEY_MUL: return "S";
        case KEY_DIV: return "T";
        case KEY_1: return "U";
        case KEY_2: return "V";
        case KEY_3: return "W";
        case KEY_ADD: return "X";
        case KEY_SUB: return "Y";
        case KEY_0: return "Z";
        case KEY_DOT: return " ";
        default: return NULL;
    }
}

int main(void)
{
    usb_interface_t const *intf[] = { &usb_ff_bulk, NULL };
    usb_open(intf, GINT_CALL_NULL);
    usb_open_wait();
    
    char input[64];
    int pos = 0;
    int alpha_pending = 0;
    clearevents();
    
    while(1) {
        // Affichage simple
        dclear(C_WHITE);
        dtext(1, 1, C_BLACK, "Tape texte:");
        dtext(1, 15, C_BLACK, input);
        dtext(1, 30, C_BLACK, "EXE=envoie AC/ON=quit");
        dupdate();
        
        // Verifier les messages recus
        struct usb_fxlink_header h;
        while(usb_fxlink_handle_messages(&h)) {
            if(h.application[0] == 'f') { // fxlink
                int pipe = usb_ff_bulk_input();
                char buf[64];
                uint32_t got = 0, n;
                while(got < h.size && got < 63) {
                    n = usb_read_sync(pipe, buf + got, 
                        (h.size - got < 64 - got) ? h.size - got : 64 - got, false);
                    if(n <= 0) break;
                    got += n;
                }
                buf[got] = '\0';
                
                dclear(C_WHITE);
                dtext(1, 1, C_BLACK, "Recu du PC:");
                dtext(1, 15, C_BLACK, buf);
                dtext(1, 30, C_BLACK, "EXE=continuer");
                dupdate();
                while(1) {
                    key_event_t ev = pollevent();
                    if(ev.type == KEYEV_DOWN && ev.key == KEY_EXE) break;
                }
            } else {
                usb_fxlink_drop_transaction();
            }
        }
        
        // Gerer les touches
        key_event_t ev = pollevent();
        if(ev.type == KEYEV_DOWN) {
            int key = ev.key;
            
            if(key == KEY_ACON) break;
            
            if(key == KEY_ALPHA) {
                alpha_pending = 1;
                continue;
            }
            
            if(key == KEY_EXE && pos > 0) {
                input[pos] = '\0';
                
                // Envoyer au PC
                char msg[96];
                int len = snprintf(msg, sizeof(msg), "%s\n", input);
                usb_fxlink_text(msg, len);
                
                dclear(C_WHITE);
                dtext(1, 1, C_BLACK, "Envoye:");
                dtext(1, 15, C_BLACK, input);
                dupdate();
                while(1) {
                    key_event_t ev2 = pollevent();
                    if(ev2.type == KEYEV_DOWN && ev2.key == KEY_EXE) break;
                }
                
                pos = 0;
                input[0] = '\0';
            }
            else if(key == KEY_DEL && pos > 0) {
                input[--pos] = '\0';
            }
            else {
                const char* kn;
                if(alpha_pending) {
                    kn = alpha_key_to_str(key);
                    if(kn) {
                        int kl = strlen(kn);
                        if(pos + kl < 63) {
                            strcpy(input + pos, kn);
                            pos += kl;
                        }
                    }
                    alpha_pending = 0;
                } else {
                    kn = key_to_str(key);
                    int kl = strlen(kn);
                    if(pos + kl < 63) {
                        strcpy(input + pos, kn);
                        pos += kl;
                    }
                }
            }
        }
        
        for(volatile int i = 0; i < 30000; i++);
    }
    
    usb_close();
    return 1;
}
