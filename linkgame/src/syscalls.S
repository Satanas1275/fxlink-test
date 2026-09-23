/* Timeouts — Stubs des syscalls serie de l'OS (fx-9860G II / II+ / Slim, OS 2.x)
 *
 * gint n'a pas de driver pour le port 3-pin : on appelle le driver serie de
 * l'OS en passant par le systeme de syscalls, via gint_world_switch().
 *
 * L'OS expose un point d'entree unique : charger le numero de syscall dans
 * r0 et sauter vers 0x80010070 (table de syscalls "nouvelle generation").
 * Les arguments restent en r4..r6 (convention SH), le retour est dans r0.
 *
 * Sur les tres anciennes fx-9860G OS 1.xx la table n'est pas a 0x80010070 :
 * pas supporte ici.
 */

.text
.balign 4

.macro SYSCALL name, id
    .global \name
    .type \name, @function
\name:
    mov.l syscall_table, r2
    mov.l 1f, r0
    jmp @r2
    nop
    .balign 4
1:
    .long \id
.endm

/* 0x0418: int Serial_Open(unsigned char *mode) */
SYSCALL _Serial_Open,     0x0418
/* 0x0419: int Serial_Close(int mode) */
SYSCALL _Serial_Close,    0x0419
/* 0x0425: int Serial_IsOpen(void) */
SYSCALL _Serial_IsOpen,   0x0425
/* 0x0411: int Serial_GetReceivedBytesAvailable(void) */
SYSCALL _Serial_Avail,    0x0411
/* 0x040C: int Serial_ReadOneByte(unsigned char *result) */
SYSCALL _Serial_ReadByte, 0x040C
/* 0x0412: int Serial_GetFreeTransmitSpace(void) */
SYSCALL _Serial_TxSpace,  0x0412
/* 0x040E: int Serial_BufferedTransmitOneByte(unsigned char byte) */
SYSCALL _Serial_WriteByte, 0x040E
/* 0x0413: int Serial_ClearReceiveBuffer(void) */
SYSCALL _Serial_ClearRX,  0x0413

.balign 4
syscall_table:
    .long 0x80010070