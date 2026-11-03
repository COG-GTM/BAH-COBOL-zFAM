      *****************************************************************
      * Test stub for the HLASM ZUIDSTCK routine (STCKE wrapper).     *
      * Returns a deterministic, monotonically increasing TOD value.  *
      *****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ZUIDSTCK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  ZS-COUNTER             PIC  9(08) COMP VALUE ZEROES.
       01  ZS-TOD.
           02  ZS-HIGH            PIC  X(02) VALUE X'00D9'.
           02  ZS-LOW             PIC  9(08) COMP.
           02  FILLER             PIC  X(10) VALUE LOW-VALUES.
       LINKAGE SECTION.
       01  LK-TOD                 PIC  X(16).
       PROCEDURE DIVISION USING LK-TOD.
           ADD 1                  TO ZS-COUNTER.
           MOVE ZS-COUNTER        TO ZS-LOW.
           MOVE ZS-TOD            TO LK-TOD.
           DISPLAY 'ZT|CALL|ZUIDSTCK'.
           GOBACK.
