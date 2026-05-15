      *****************************************************************
      * CICS Execute Interface Block (EIB) stub for GnuCOBOL.        *
      * Provides the standard EIB fields used by CICS programs.      *
      *****************************************************************
       01  DFHEIBLK.
           02  EIBTIME            PIC S9(07) COMP-3 VALUE 0.
           02  EIBDATE            PIC S9(07) COMP-3 VALUE 0.
           02  EIBTRNID           PIC  X(04) VALUE SPACES.
           02  EIBTASKN           PIC S9(07) COMP-3 VALUE 0.
           02  EIBTRMID           PIC  X(04) VALUE SPACES.
           02  DFHEIGDI           PIC S9(04) COMP   VALUE 0.
           02  EIBCPOSN           PIC S9(04) COMP   VALUE 0.
           02  EIBCALEN           PIC S9(04) COMP   VALUE 0.
           02  EIBAID             PIC  X(01) VALUE SPACES.
           02  EIBFN              PIC  X(02) VALUE SPACES.
           02  EIBRCODE           PIC  X(06) VALUE SPACES.
           02  EIBDS              PIC  X(08) VALUE SPACES.
           02  EIBREQID           PIC  X(08) VALUE SPACES.
           02  EIBRSRCE           PIC  X(08) VALUE SPACES.
           02  EIBSYNC            PIC  X(01) VALUE SPACES.
           02  EIBFREE            PIC  X(01) VALUE SPACES.
           02  EIBRECV            PIC  X(01) VALUE SPACES.
           02  EIBSEND            PIC  X(01) VALUE SPACES.
           02  EIBATT             PIC  X(01) VALUE SPACES.
           02  EIBEOC             PIC  X(01) VALUE SPACES.
           02  EIBFMH             PIC  X(01) VALUE SPACES.
           02  EIBCOMPL           PIC  X(01) VALUE SPACES.
           02  EIBSIG             PIC  X(01) VALUE SPACES.
           02  EIBCONF            PIC  X(01) VALUE SPACES.
           02  EIBERR             PIC  X(01) VALUE SPACES.
           02  EIBERRCD           PIC  X(04) VALUE SPACES.
           02  EIBSYNRB           PIC  X(01) VALUE SPACES.
           02  EIBNODAT           PIC  X(01) VALUE SPACES.
           02  EIBRESP            PIC S9(08) COMP   VALUE 0.
           02  EIBRESP2           PIC S9(08) COMP   VALUE 0.
           02  EIBRLDBK           PIC  X(01) VALUE SPACES.
