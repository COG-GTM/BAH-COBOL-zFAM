/*
 * Minimal CICS runtime stand-in for running zFAM Basic Mode browse
 * programs under GnuCOBOL.  Provides an in-memory VSAM KEY store (KSDS
 * keyed by the 255 byte primary key) and FILE store (keyed by the 16 byte
 * segment key), HTTP request headers, and writes the HTTP response
 * (headers, status, body) to stdout.
 *
 * Usage: <program> <dir>
 *   <dir>/commarea.bin  DFHCOMMAREA passed to the program
 *   <dir>/keys.bin      KEY store records (512 bytes each, sorted by key)
 *   <dir>/file.bin      FILE store records (2 byte BE length + record)
 *   <dir>/headers.txt   request headers, one "name<TAB>value" per line
 */
#include <stddef.h>
#include <libcob.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RESP_NORMAL 0
#define RESP_NOTFND 13
#define RESP_ENDFILE 20
#define RESP_LENGERR 22

#define FK_LEN 512
#define FK_KEYLEN 255
#define FF_KEYLEN 16
#define CA_LEN 275
#define CA_KEY_OFFSET 20

extern int ZFAM_PROGRAM(unsigned char *eib, unsigned char *commarea);

struct eib {
    char trnid[4];
    int32_t resp;
    int32_t resp2;
};

struct rec {
    unsigned char *data;
    int len;
};

static struct eib eib;
static unsigned char commarea[CA_LEN];
static struct rec *keys, *files;
static int nkeys, nfiles;
static char hdr_name[64][1024], hdr_value[64][1024];
static int nhdrs;

static int browse_first, browse_cur, browse_pos, browse_at_end, browse_exact;

static int get_be(const unsigned char *p, int n) {
    int v = 0;
    for (int i = 0; i < n; i++) v = (v << 8) | p[i];
    if (n == 2 && v & 0x8000) v -= 0x10000;
    return v;
}

static void put_be(unsigned char *p, int n, int v) {
    for (int i = n - 1; i >= 0; i--) { p[i] = v & 0xff; v >>= 8; }
}

static void resp(int r) { eib.resp = r; eib.resp2 = 0; }

static void print_bytes(const unsigned char *p, int n) {
    for (int i = 0; i < n; i++) {
        if (p[i] >= 0x20 && p[i] < 0x7f && p[i] != '\\') putchar(p[i]);
        else printf("\\x%02x", p[i]);
    }
}

static int is_key_store(const unsigned char *fct) { return memcmp(fct + 4, "KEY ", 4) == 0; }

static unsigned char *load(const char *path, long *size) {
    FILE *f = fopen(path, "rb");
    if (!f) { *size = 0; return NULL; }
    fseek(f, 0, SEEK_END);
    *size = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *buf = malloc(*size + 1);
    if (fread(buf, 1, *size, f) != (size_t)*size) { perror(path); exit(2); }
    fclose(f);
    return buf;
}

static void copy_rec(const struct rec *r, unsigned char *into, unsigned char *length,
                     unsigned char *ridfld, int keylen) {
    int max = get_be(length, 2);
    if (r->len > max) { put_be(length, 2, r->len); resp(RESP_LENGERR); return; }
    memcpy(into, r->data, r->len);
    put_be(length, 2, r->len);
    memcpy(ridfld, r->data, keylen);
    resp(RESP_NORMAL);
}

/* ---- CICS commands -------------------------------------------------- */

int CICSGETMAIN(void **set, unsigned char *flength, unsigned char *initimg) {
    int n = get_be(flength, 4);
    *set = malloc(n);
    memset(*set, initimg ? *initimg : 0, n);
    resp(RESP_NORMAL);
    return 0;
}

int CICSWEBREAD(unsigned char *name, unsigned char *namelen, unsigned char *value,
                unsigned char *valuelen, unsigned char *respfld) {
    int nl = get_be(namelen, 4), max = get_be(valuelen, 4);
    int r = RESP_NOTFND;
    for (int i = 0; i < nhdrs; i++) {
        if ((int)strlen(hdr_name[i]) == nl && strncasecmp(hdr_name[i], (char *)name, nl) == 0) {
            int vl = strlen(hdr_value[i]);
            if (vl > max) vl = max;
            memcpy(value, hdr_value[i], vl);
            put_be(valuelen, 4, vl);
            r = RESP_NORMAL;
            break;
        }
    }
    resp(r);
    if (respfld) put_be(respfld, 4, r);
    return 0;
}

int CICSWEBWRITE(unsigned char *name, unsigned char *namelen, unsigned char *value,
                 unsigned char *valuelen) {
    printf("HEADER ");
    print_bytes(name, get_be(namelen, 4));
    printf(": ");
    print_bytes(value, get_be(valuelen, 4));
    printf("\n");
    resp(RESP_NORMAL);
    return 0;
}

int CICSWEBSEND(unsigned char *from, unsigned char *doctoken, unsigned char *fromlen,
                unsigned char *mediatype, unsigned char *statuscode,
                unsigned char *statustext, unsigned char *statuslen, char *flag) {
    int ml = 0;
    while (ml < 56 && mediatype[ml] != 0 && mediatype[ml] != ' ') ml++;
    printf("STATUS %d ", get_be(statuscode, 2));
    print_bytes(statustext, get_be(statuslen, 4));
    printf("\nMEDIATYPE ");
    print_bytes(mediatype, ml);
    int fl = 12;
    while (fl > 0 && flag[fl - 1] == ' ') fl--;
    printf("\nCONVERT %.*s\n", fl, flag);
    if (from && !doctoken) {
        int n = get_be(fromlen, 4);
        printf("BODYLEN %d\nBODY ", n);
        print_bytes(from, n);
        printf("\n");
    } else {
        printf("BODYLEN 0\nBODY \n");
    }
    resp(RESP_NORMAL);
    return 0;
}

int CICSSTARTBR(unsigned char *fct, unsigned char *ridfld, char *flag) {
    (void)fct; (void)flag;
    static const unsigned char ff[FK_KEYLEN] = {0};
    int all_ff = 1;
    for (int i = 0; i < FK_KEYLEN; i++) if (ridfld[i] != 0xff) { all_ff = 0; break; }
    (void)ff;
    browse_first = 1;
    browse_at_end = all_ff;
    browse_exact = 0;
    if (all_ff) { browse_pos = nkeys; resp(RESP_NORMAL); return 0; }
    int i = 0;
    while (i < nkeys && memcmp(keys[i].data, ridfld, FK_KEYLEN) < 0) i++;
    if (i == nkeys) { resp(RESP_NOTFND); return 0; }
    browse_pos = i;
    browse_exact = memcmp(keys[i].data, ridfld, FK_KEYLEN) == 0;
    resp(RESP_NORMAL);
    return 0;
}

int CICSREADNEXT(unsigned char *fct, unsigned char *into, unsigned char *ridfld,
                 unsigned char *length) {
    (void)fct;
    int idx = browse_first ? browse_pos : browse_cur + 1;
    if (idx >= nkeys) { resp(RESP_ENDFILE); return 0; }
    copy_rec(&keys[idx], into, length, ridfld, FK_KEYLEN);
    browse_first = 0;
    browse_cur = idx;
    return 0;
}

int CICSREADPREV(unsigned char *fct, unsigned char *into, unsigned char *ridfld,
                 unsigned char *length) {
    (void)fct;
    int idx;
    if (browse_first) {
        if (browse_at_end) idx = nkeys - 1;
        else if (browse_exact) idx = browse_pos;
        else { resp(RESP_NOTFND); return 0; }
    } else {
        idx = browse_cur - 1;
    }
    if (idx < 0) { resp(RESP_ENDFILE); return 0; }
    copy_rec(&keys[idx], into, length, ridfld, FK_KEYLEN);
    browse_first = 0;
    browse_cur = idx;
    return 0;
}

int CICSREAD(unsigned char *fct, unsigned char *into, unsigned char *ridfld,
             unsigned char *length, char *flag) {
    int gteq = memcmp(flag, "GTEQ", 4) == 0;
    if (is_key_store(fct)) {
        for (int i = 0; i < nkeys; i++) {
            int c = memcmp(keys[i].data, ridfld, FK_KEYLEN);
            if (c == 0 || (gteq && c > 0)) { copy_rec(&keys[i], into, length, ridfld, FK_KEYLEN); return 0; }
        }
    } else {
        for (int i = 0; i < nfiles; i++) {
            if (memcmp(files[i].data, ridfld, FF_KEYLEN) == 0) {
                copy_rec(&files[i], into, length, ridfld, FF_KEYLEN);
                return 0;
            }
        }
    }
    resp(RESP_NOTFND);
    return 0;
}

/*
 * EBCDIC to ASCII conversion stand-in.  The harness runs in ASCII, so the
 * conversion is modelled as upper-casing, which makes the converted byte
 * ranges visible in the response body.
 */
int ZFAMASCII(unsigned char *field, unsigned char *length) {
    int n = 0;
    for (int i = 0; i < 3; i++) n = n * 10 + (length[i] & 0x0f);
    for (int i = 0; i < n; i++)
        if (field[i] >= 'a' && field[i] <= 'z') field[i] -= 32;
    return 0;
}

/* ZFAM006: increment the 255 byte commarea key by one. */
int CICSLINK(unsigned char *program, unsigned char *ca) {
    if (memcmp(program, "ZFAM006 ", 8) != 0) { resp(RESP_NOTFND); return 0; }
    unsigned char *key = ca + CA_KEY_OFFSET;
    for (int i = FK_KEYLEN - 1; i >= 0; i--) { if (++key[i] != 0) break; }
    resp(RESP_NORMAL);
    return 0;
}

int CICSRETURN(void) {
    fflush(stdout);
    exit(0);
}

/* ---- driver --------------------------------------------------------- */

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: %s <scenario-dir>\n", argv[0]); return 2; }
    char path[4096];
    long size;
    unsigned char *buf;

    snprintf(path, sizeof path, "%s/commarea.bin", argv[1]);
    buf = load(path, &size);
    if (size != CA_LEN) { fprintf(stderr, "bad commarea size %ld\n", size); return 2; }
    memcpy(commarea, buf, CA_LEN);

    snprintf(path, sizeof path, "%s/keys.bin", argv[1]);
    buf = load(path, &size);
    nkeys = size / FK_LEN;
    keys = calloc(nkeys + 1, sizeof *keys);
    for (int i = 0; i < nkeys; i++) { keys[i].data = buf + i * FK_LEN; keys[i].len = FK_LEN; }

    snprintf(path, sizeof path, "%s/file.bin", argv[1]);
    buf = load(path, &size);
    files = calloc(size / 2 + 1, sizeof *files);
    for (long off = 0; off < size; nfiles++) {
        files[nfiles].len = get_be(buf + off, 2) & 0xffff;
        files[nfiles].data = buf + off + 2;
        off += 2 + files[nfiles].len;
    }

    snprintf(path, sizeof path, "%s/headers.txt", argv[1]);
    FILE *f = fopen(path, "r");
    char line[1024];
    while (f && fgets(line, sizeof line, f) && nhdrs < 64) {
        line[strcspn(line, "\n")] = 0;
        char *tab = strchr(line, '\t');
        if (!tab) continue;
        *tab = 0;
        snprintf(hdr_name[nhdrs], sizeof hdr_name[0], "%s", line);
        snprintf(hdr_value[nhdrs], sizeof hdr_value[0], "%s", tab + 1);
        nhdrs++;
    }
    if (f) fclose(f);

    memcpy(eib.trnid, "FA01", 4);
    cob_init(0, NULL);
    ZFAM_PROGRAM((unsigned char *)&eib, commarea);
    printf("ERROR program ended without EXEC CICS RETURN\n");
    return 1;
}
