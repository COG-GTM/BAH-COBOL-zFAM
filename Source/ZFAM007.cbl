       CBL DBCS,CICS(SP)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ZFAM007.
       AUTHOR.  Rich Jackson and Randy Frerking.
      *****************************************************************
      *                                                               *
      * zFAM - z/OS File Access Manager.                              *
      *                                                               *
      * Basic Mode multi-row browse.                                  *
      *                                                               *
      * This program is executed via XCTL from ZFAM002 to process an  *
      * HTTP/GET request that returns more than one row, which is     *
      * any GET with the ROWS and/or KEYSONLY query string parameter. *
      *                                                               *
      * Browse direction is selected by GET-CA-TYPE:                  *
      *   GE, GT        - browse forward  (READNEXT).                 *
      *   LE, LT        - browse backward (READPREV).                 *
      *   anything else - browse forward as GE.                       *
      *                                                               *
      * Response format is selected by GET-CA-KEYS-ONLY:              *
      *   'Y'           - keys only.                                  *
      *   otherwise     - keys and record data.                       *
      *                                                               *
      * Each row in the response body is formatted as follows.        *
      *                                                               *
      *   No delimiter (GET-CA-DELIM is spaces or low-values):        *
      *     keys only : kkk<key>                                      *
      *     records   : kkk<key>rrrrrrr<data>                         *
      *     where kkk is the 3 digit key length and rrrrrrr is the 7  *
      *     digit record length.                                      *
      *                                                               *
      *   Delimiter (d):                                              *
      *     keys only : <key>        rows separated by d              *
      *     records   : <key>d<data> rows separated by d              *
      *                                                               *
      * Response headers:                                             *
      *   zFAM-LastKey  - last key browsed, used to continue a browse *
      *   zFAM-Rows     - number of rows in the response body         *
      *                                                               *
      * HTTP status:                                                  *
      *   200 - rows returned.                                        *
      *   204 - no rows found.                                        *
      *   206 - response buffer full; continue from zFAM-LastKey.     *
      *                                                               *
      * Date       UserID   Description                               *
      * ---------- -------- ----------------------------------------- *
      *                     Consolidated ZFAM007 (GE/GT ROWS),        *
      *                     ZFAM008 (LE/LT ROWS) and ZFAM009          *
      *                     (KEYSONLY) into this program.             *
      *                                                               *
      *****************************************************************
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *****************************************************************
      * Request options derived from DFHCOMMAREA.                     *
      *****************************************************************
       01  BROWSE-DIRECTION       PIC  X(01) VALUE 'F'.
           88  BROWSE-FORWARD                VALUE 'F'.
           88  BROWSE-BACKWARD               VALUE 'B'.

       01  RESPONSE-FORMAT        PIC  X(01) VALUE 'R'.
           88  FORMAT-RECORDS                VALUE 'R'.
           88  FORMAT-KEYS-ONLY              VALUE 'K'.

      *****************************************************************
      * Process switches.                                             *
      *****************************************************************
       01  PROCESS-SWITCH         PIC  X(01) VALUE 'N'.
           88  PROCESS-COMPLETE              VALUE 'Y'.
           88  PROCESS-INCOMPLETE            VALUE 'N'.

       01  RANGE-SWITCH           PIC  X(01) VALUE 'N'.
           88  RANGE-EXCEEDED                VALUE 'Y'.
           88  RANGE-NOT-EXCEEDED            VALUE 'N'.

       01  SELECT-SWITCH          PIC  X(01) VALUE 'N'.
           88  SELECT-MATCHED                VALUE 'Y'.
           88  SELECT-NOT-MATCHED            VALUE 'N'.

       01  SEGMENTS-SWITCH        PIC  X(01) VALUE 'N'.
           88  SEGMENTS-COMPLETE             VALUE 'Y'.
           88  SEGMENTS-INCOMPLETE           VALUE 'N'.

       01  SEGMENTS-STATUS        PIC  X(01) VALUE 'Y'.
           88  SEGMENTS-SUCCESSFUL           VALUE 'Y'.
           88  SEGMENTS-FAILED               VALUE 'N'.

       01  BUFFER-SWITCH          PIC  X(01) VALUE 'N'.
           88  BUFFER-FULL                   VALUE 'Y'.
           88  BUFFER-AVAILABLE              VALUE 'N'.

      *****************************************************************
      * HTTP request headers.                                         *
      *****************************************************************
       01  HEADER-SELECT          PIC  X(11) VALUE 'zFAM-Select'.
       01  HEADER-SELECT-LENGTH   PIC S9(08) COMP VALUE 11.
       01  SELECT-LENGTH          PIC S9(08) COMP VALUE 6.
       01  SELECT-TYPE            PIC  X(06) VALUE 'text'.

       01  HEADER-RANGE           PIC  X(13) VALUE 'zFAM-RangeEnd'.
       01  HEADER-RANGE-LENGTH    PIC S9(08) COMP VALUE 13.
       01  RANGE-RESPONSE         PIC S9(08) COMP VALUE ZEROES.
       01  RANGE-VALUE-LENGTH     PIC S9(08) COMP VALUE 255.
       01  RANGE-VALUE            PIC X(255) VALUE LOW-VALUES.

      *****************************************************************
      * HTTP response headers.                                        *
      *****************************************************************
       01  HEADER-LASTKEY         PIC  X(12) VALUE 'zFAM-LastKey'.
       01  HEADER-LASTKEY-LENGTH  PIC S9(08) COMP VALUE 12.
       01  HEADER-ROWS            PIC  X(09) VALUE 'zFAM-Rows'.
       01  HEADER-ROWS-LENGTH     PIC S9(08) COMP VALUE 9.

      *****************************************************************
      * HTTP response status and media types.                         *
      *****************************************************************
       01  HTTP-STATUS            PIC S9(04) COMP VALUE 000.
       01  HTTP-STATUS-200        PIC S9(04) COMP VALUE 200.
       01  HTTP-STATUS-204        PIC S9(04) COMP VALUE 204.
       01  HTTP-STATUS-206        PIC S9(04) COMP VALUE 206.

       01  HTTP-NOT-FOUND         PIC  X(16) VALUE 'Record not found'.
       01  HTTP-NOT-FOUND-LENGTH  PIC S9(08) COMP VALUE 16.

       01  TEXT-ANYTHING          PIC  X(04) VALUE 'text'.
       01  TEXT-PLAIN             PIC  X(56) VALUE 'text/plain'.
       01  APPLICATION-XML        PIC  X(56) VALUE 'application/xml'.
       01  APPLICATION-JSON       PIC  X(56) VALUE 'application/json'.

       01  WEB-MEDIA-TYPE         PIC  X(56).
       01  SEND-ACTION            PIC S9(08) COMP VALUE ZEROES.
       01  DOCUMENT-TOKEN         PIC  X(16) VALUE SPACES.

      *****************************************************************
      * EBCDIC to ASCII conversion.                                   *
      *****************************************************************
       01  EBCDIC-CCSID           PIC  9(04) BINARY VALUE 1140.
       01  ASCII-CCSID            PIC  9(04) BINARY VALUE 819.
       01  FIELD-LENGTH           PIC  9(03) VALUE ZEROES.

      *****************************************************************
      * Response buffer management.                                   *
      *                                                               *
      * The response is built in a GETMAIN area.  START-ADDRESS is    *
      * the end of the last complete row.  Each new row is built from *
      * START-ADDRESS and only committed to MESSAGE-LENGTH and        *
      * START-ADDRESS once the row is complete.                       *
      *****************************************************************
       01  LINKAGE-ADDRESSES.
           02  ORIGINAL-ADDRESS   USAGE POINTER.
           02  ORIGINAL-ADDRESS-X REDEFINES ORIGINAL-ADDRESS
                                  PIC S9(08) COMP.

           02  CURRENT-ADDRESS    USAGE POINTER.
           02  CURRENT-ADDRESS-X  REDEFINES CURRENT-ADDRESS
                                  PIC S9(08) COMP.

           02  START-ADDRESS      USAGE POINTER.
           02  START-ADDRESS-X    REDEFINES START-ADDRESS
                                  PIC S9(08) COMP.

           02  LENGTH-ADDRESS     USAGE POINTER.
           02  LENGTH-ADDRESS-X   REDEFINES LENGTH-ADDRESS
                                  PIC S9(08) COMP.

       01  GETMAIN-LENGTH         PIC S9(08) COMP VALUE 3200000.
       01  BINARY-ZEROES          PIC  X(01) VALUE LOW-VALUES.
       01  MESSAGE-LENGTH         PIC S9(08) COMP VALUE ZEROES.
       01  ROW-LENGTH             PIC S9(08) COMP VALUE ZEROES.
       01  LOGICAL-LENGTH         PIC S9(08) COMP VALUE ZEROES.
       01  AVAILABLE-LENGTH       PIC S9(08) COMP VALUE ZEROES.
       01  THIRTY-TWO-KB          PIC S9(08) COMP VALUE 32000.

       01  KEY-LENGTH-DIGITS      PIC S9(08) COMP VALUE 3.
       01  RECORD-LENGTH-DIGITS   PIC S9(08) COMP VALUE 7.
       01  DELIMITER-LENGTH       PIC S9(08) COMP VALUE 1.

       01  KEY-LENGTH             PIC  9(03) VALUE 0.
       01  RECORD-LENGTH          PIC  9(07) VALUE 0.
       01  TRAILING-NULLS         PIC S9(08) COMP VALUE 0.

       01  ROWS-COUNT             PIC S9(08) COMP VALUE 0.
       01  MESSAGE-COUNT          PIC  9(04) VALUE 0.
       01  MESSAGE-COUNT-LENGTH   PIC S9(08) COMP VALUE 4.

      *****************************************************************
      * Browse keys.                                                  *
      *****************************************************************
       01  PREVIOUS-KEY           PIC X(255) VALUE LOW-VALUES.
       01  LAST-KEY               PIC X(255) VALUE LOW-VALUES.
       01  STATUS-LENGTH          PIC S9(08) COMP VALUE 255.

       01  TWO-FIFTY-FIVE         PIC S9(08) COMP VALUE 255.
       01  ONE                    PIC S9(08) COMP VALUE 1.
       01  HEX-01                 PIC  X(01) VALUE X'01'.

       01  ZFAM006                PIC  X(08) VALUE 'ZFAM006 '.

      *****************************************************************
      * KEY and FILE stores.                                          *
      *****************************************************************
       01  FK-FCT.
           02  FK-TRANID          PIC  X(04) VALUE 'FA##'.
           02  FILLER             PIC  X(04) VALUE 'KEY '.

       01  FF-FCT.
           02  FF-TRANID          PIC  X(04) VALUE 'FA##'.
           02  FF-DDNAME          PIC  X(04) VALUE 'FILE'.

       01  FK-LENGTH              PIC S9(04) COMP VALUE ZEROES.
       01  FF-LENGTH              PIC S9(04) COMP VALUE ZEROES.

       COPY ZFAMFKC.

       COPY ZFAMFFC.

      *****************************************************************
      * Trace.                                                        *
      *****************************************************************
       01  T_LEN                  PIC S9(04) COMP VALUE 8.
       01  T_46                   PIC S9(04) COMP VALUE 46.
       01  T_46_M                 PIC  X(08) VALUE SPACES.
       01  T_RES                  PIC  X(08) VALUE 'ZFAM002 '.

      *****************************************************************
      * Dynamic Storage                                               *
      *****************************************************************
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           02  GET-CA-TYPE        PIC  X(02).
               88  GET-CA-GT                 VALUE 'gt'.
               88  GET-CA-LE                 VALUE 'le'.
               88  GET-CA-LT                 VALUE 'lt'.
               88  GET-CA-BACKWARD           VALUE 'le' 'lt'.
           02  GET-CA-ROWS        PIC  9(04).
           02  GET-CA-DELIM       PIC  X(01).
               88  GET-CA-NO-DELIM           VALUE LOW-VALUE SPACE.
           02  GET-CA-KEYS-ONLY   PIC  X(01).
               88  GET-CA-KEYS-REQUESTED     VALUE 'Y'.
           02  GET-CA-TTL         PIC  X(01).
           02  FILLER             PIC  X(07).
           02  GET-CA-KEY-LENGTH  PIC S9(08) COMP.
           02  GET-CA-KEY         PIC X(255).

      *****************************************************************
      * zFAM  message.                                                *
      * This is the response message buffer.                          *
      *****************************************************************
       01  ZFAM-MESSAGE           PIC  X(32000).

       PROCEDURE DIVISION.

      *****************************************************************
      * Main process.                                                 *
      *****************************************************************
           PERFORM 1000-INITIALIZE         THRU 1000-EXIT.
           PERFORM 2000-START-BROWSE       THRU 2000-EXIT.

           PERFORM 3000-PROCESS-ROW        THRU 3000-EXIT
               WITH TEST AFTER
               UNTIL PROCESS-COMPLETE.

           PERFORM 4000-SEND-RESPONSE      THRU 4000-EXIT.
           PERFORM 9000-RETURN             THRU 9000-EXIT.

      *****************************************************************
      * Perform initialization.                                       *
      *                                                               *
      * The zFAM-Select header only applies to record data, so it is  *
      * not read for a KEYSONLY request.                              *
      *****************************************************************
       1000-INITIALIZE.
           SET PROCESS-INCOMPLETE            TO TRUE.
           SET RANGE-NOT-EXCEEDED            TO TRUE.
           MOVE EIBTRNID(3:2)                TO FK-TRANID(3:2).
           MOVE EIBTRNID(3:2)                TO FF-TRANID(3:2).

           IF  GET-CA-BACKWARD
               SET BROWSE-BACKWARD           TO TRUE
           ELSE
               SET BROWSE-FORWARD            TO TRUE
           END-IF.

           IF  GET-CA-KEYS-REQUESTED
               SET FORMAT-KEYS-ONLY          TO TRUE
           ELSE
               SET FORMAT-RECORDS            TO TRUE
           END-IF.

           EXEC CICS GETMAIN SET(ORIGINAL-ADDRESS)
                FLENGTH(GETMAIN-LENGTH)
                INITIMG(BINARY-ZEROES)
                NOHANDLE
           END-EXEC.

           SET ADDRESS OF ZFAM-MESSAGE       TO ORIGINAL-ADDRESS.
           MOVE ORIGINAL-ADDRESS-X           TO START-ADDRESS-X.

           IF  FORMAT-RECORDS
               EXEC CICS WEB READ
                    HTTPHEADER  (HEADER-SELECT)
                    NAMELENGTH  (HEADER-SELECT-LENGTH)
                    VALUE       (SELECT-TYPE)
                    VALUELENGTH (SELECT-LENGTH)
                    NOHANDLE
               END-EXEC
           END-IF.

           EXEC CICS WEB READ
                HTTPHEADER  (HEADER-RANGE)
                NAMELENGTH  (HEADER-RANGE-LENGTH)
                VALUE       (RANGE-VALUE)
                VALUELENGTH (RANGE-VALUE-LENGTH)
                RESP        (RANGE-RESPONSE)
                NOHANDLE
           END-EXEC.

       1000-EXIT.
           EXIT.

      *****************************************************************
      * Position the KEY store browse.                                *
      *****************************************************************
       2000-START-BROWSE.
           MOVE LENGTH OF FK-RECORD          TO FK-LENGTH.

           IF  BROWSE-FORWARD
               PERFORM 2100-START-FORWARD    THRU 2100-EXIT
           ELSE
               PERFORM 2200-START-BACKWARD   THRU 2200-EXIT
           END-IF.

       2000-EXIT.
           EXIT.

      *****************************************************************
      * Forward browse (GE/GT).                                       *
      *                                                               *
      * When GE is specified, use the key as is, however when GT is   *
      * specified, the key must be incremented by one bit otherwise   *
      * the key presented could be read again.                        *
      *****************************************************************
       2100-START-FORWARD.
           IF  GET-CA-GT
               PERFORM 2110-AUGMENT-KEY      THRU 2110-EXIT
           END-IF.

           MOVE GET-CA-KEY                   TO FK-KEY.

           EXEC CICS STARTBR FILE(FK-FCT)
                RIDFLD(FK-KEY)
                NOHANDLE
                GTEQ
           END-EXEC.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               PERFORM 9100-NOT-FOUND        THRU 9100-EXIT
           END-IF.

       2100-EXIT.
           EXIT.

      *****************************************************************
      * Increment the GT key by one bit.                              *
      *                                                               *
      * The key is always padded with x'00' (low-values), so when the *
      * key is shorter than 255 bytes, setting the last byte to x'01' *
      * is sufficient.  A full 255 byte key is incremented by the     *
      * Assembler program ZFAM006.                                    *
      *****************************************************************
       2110-AUGMENT-KEY.
           IF  GET-CA-KEY-LENGTH LESS THAN TWO-FIFTY-FIVE
               MOVE HEX-01                   TO GET-CA-KEY(255:1)
           ELSE
               EXEC CICS LINK PROGRAM(ZFAM006)
                    COMMAREA(DFHCOMMAREA)
                    NOHANDLE
               END-EXEC
           END-IF.

       2110-EXIT.
           EXIT.

      *****************************************************************
      * Backward browse (LE/LT).                                      *
      *                                                               *
      * READPREV following STARTBR requires the RIDFLD of a record    *
      * that exists, so READ GTEQ is issued first to obtain it.  When *
      * there is no record GTEQ the supplied key, the browse is       *
      * positioned at end of file with a key of x'FF's.               *
      *                                                               *
      * The first READPREV returns the record at the start position,  *
      * so that record is skipped when it is beyond the requested     *
      * key (LE) or not less than the requested key (LT).  No record  *
      * is skipped when positioned at end of file.                    *
      *****************************************************************
       2200-START-BACKWARD.
           MOVE GET-CA-KEY                   TO FK-KEY.

           EXEC CICS READ FILE(FK-FCT)
                INTO(FK-RECORD)
                RIDFLD(FK-KEY)
                LENGTH(FK-LENGTH)
                GTEQ
                NOHANDLE
           END-EXEC.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               MOVE HIGH-VALUES              TO FK-KEY
           END-IF.

           EXEC CICS STARTBR FILE(FK-FCT)
                RIDFLD(FK-KEY)
                NOHANDLE
                GTEQ
           END-EXEC.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               PERFORM 9100-NOT-FOUND        THRU 9100-EXIT
           END-IF.

           IF  FK-KEY NOT EQUAL HIGH-VALUES
               EVALUATE TRUE
                   WHEN GET-CA-LE
                    AND FK-KEY GREATER THAN GET-CA-KEY
                       PERFORM 2210-SKIP-RECORD  THRU 2210-EXIT
                   WHEN GET-CA-LT
                    AND FK-KEY NOT LESS THAN GET-CA-KEY
                       PERFORM 2210-SKIP-RECORD  THRU 2210-EXIT
               END-EVALUATE
           END-IF.

       2200-EXIT.
           EXIT.

      *****************************************************************
      * Skip the record at the backward browse start position.        *
      *****************************************************************
       2210-SKIP-RECORD.
           MOVE LENGTH OF FK-RECORD          TO FK-LENGTH.

           EXEC CICS READPREV FILE(FK-FCT)
                INTO(FK-RECORD)
                RIDFLD(FK-KEY)
                LENGTH(FK-LENGTH)
                NOHANDLE
           END-EXEC.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               PERFORM 9100-NOT-FOUND        THRU 9100-EXIT
           END-IF.

       2210-EXIT.
           EXIT.

      *****************************************************************
      * Read the next KEY store record and, when it is selected,      *
      * append it to the response.                                    *
      *****************************************************************
       3000-PROCESS-ROW.
           PERFORM 3100-READ-KEY             THRU 3100-EXIT.

           IF  PROCESS-INCOMPLETE AND SELECT-MATCHED
               PERFORM 3150-CHECK-ROW-SPACE  THRU 3150-EXIT
           END-IF.

           IF  PROCESS-INCOMPLETE AND SELECT-MATCHED
               IF  FORMAT-KEYS-ONLY
                   PERFORM 3300-APPEND-KEY-ROW    THRU 3300-EXIT
               ELSE
                   PERFORM 3400-APPEND-RECORD-ROW THRU 3400-EXIT
               END-IF
           END-IF.

           IF  ROWS-COUNT EQUAL GET-CA-ROWS
               SET PROCESS-COMPLETE          TO TRUE
           END-IF.

       3000-EXIT.
           EXIT.

      *****************************************************************
      * Issue READNEXT/READPREV for the next KEY store record.        *
      *****************************************************************
       3100-READ-KEY.
           SET SELECT-NOT-MATCHED            TO TRUE.
           MOVE FK-KEY                       TO PREVIOUS-KEY.
           MOVE LENGTH OF FK-RECORD          TO FK-LENGTH.

           IF  BROWSE-FORWARD
               EXEC CICS READNEXT FILE(FK-FCT)
                    INTO(FK-RECORD)
                    RIDFLD(FK-KEY)
                    LENGTH(FK-LENGTH)
                    NOHANDLE
               END-EXEC
           ELSE
               EXEC CICS READPREV FILE(FK-FCT)
                    INTO(FK-RECORD)
                    RIDFLD(FK-KEY)
                    LENGTH(FK-LENGTH)
                    NOHANDLE
               END-EXEC
           END-IF.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               SET PROCESS-COMPLETE          TO TRUE
           ELSE
               IF  RANGE-RESPONSE EQUAL DFHRESP(NORMAL)
                   PERFORM 3110-CHECK-RANGE  THRU 3110-EXIT
               END-IF
           END-IF.

           IF  PROCESS-INCOMPLETE
               PERFORM 3120-CHECK-SELECT     THRU 3120-EXIT
           END-IF.

       3100-EXIT.
           EXIT.

      *****************************************************************
      * Compare the zFAM-RangeEnd header with the primary key.        *
      *****************************************************************
       3110-CHECK-RANGE.
           IF  BROWSE-FORWARD
               IF  FK-KEY     (1:RANGE-VALUE-LENGTH) GREATER THAN
                   RANGE-VALUE(1:RANGE-VALUE-LENGTH)
                   SET RANGE-EXCEEDED        TO TRUE
               END-IF
           ELSE
               IF  FK-KEY     (1:RANGE-VALUE-LENGTH) LESS THAN
                   RANGE-VALUE(1:RANGE-VALUE-LENGTH)
                   SET RANGE-EXCEEDED        TO TRUE
               END-IF
           END-IF.

           IF  RANGE-EXCEEDED
               SET PROCESS-COMPLETE          TO TRUE
           END-IF.

       3110-EXIT.
           EXIT.

      *****************************************************************
      * Select the record.                                            *
      *                                                               *
      * KEYSONLY selects every key.  Otherwise a zFAM-Select of       *
      * 'text*' selects text objects and any other value selects      *
      * non-text objects.                                             *
      *****************************************************************
       3120-CHECK-SELECT.
           EVALUATE TRUE
               WHEN FORMAT-KEYS-ONLY
                   SET SELECT-MATCHED        TO TRUE
               WHEN SELECT-TYPE(1:4) EQUAL TEXT-ANYTHING
                AND FK-OBJECT        EQUAL TEXT-ANYTHING
                   SET SELECT-MATCHED        TO TRUE
               WHEN SELECT-TYPE(1:4) NOT EQUAL TEXT-ANYTHING
                AND FK-OBJECT        NOT EQUAL TEXT-ANYTHING
                   SET SELECT-MATCHED        TO TRUE
           END-EVALUATE.

       3120-EXIT.
           EXIT.

      *****************************************************************
      * Make sure the key and framing of the next row fit in the      *
      * response buffer before any of the row is built.  When they    *
      * do not, set the BUFFER-FULL condition, which ends the browse  *
      * and returns HTTP status code 206.                             *
      *****************************************************************
       3150-CHECK-ROW-SPACE.
           MOVE ZEROES                       TO TRAILING-NULLS.
           INSPECT FUNCTION REVERSE(FK-KEY)
               TALLYING TRAILING-NULLS FOR LEADING LOW-VALUES.

           SUBTRACT TRAILING-NULLS FROM LENGTH OF FK-KEY
               GIVING KEY-LENGTH.

           MOVE KEY-LENGTH                   TO ROW-LENGTH.

           IF  GET-CA-NO-DELIM
               ADD KEY-LENGTH-DIGITS         TO ROW-LENGTH
               IF  FORMAT-RECORDS
                   ADD RECORD-LENGTH-DIGITS  TO ROW-LENGTH
               END-IF
           ELSE
               IF  MESSAGE-COUNT NOT EQUAL ZEROES
                   ADD DELIMITER-LENGTH      TO ROW-LENGTH
               END-IF
               IF  FORMAT-RECORDS
                   ADD DELIMITER-LENGTH      TO ROW-LENGTH
               END-IF
           END-IF.

           SUBTRACT MESSAGE-LENGTH FROM GETMAIN-LENGTH
               GIVING AVAILABLE-LENGTH.

           IF  ROW-LENGTH GREATER THAN AVAILABLE-LENGTH
               SET BUFFER-FULL               TO TRUE
               SET PROCESS-COMPLETE          TO TRUE
           END-IF.

       3150-EXIT.
           EXIT.

      *****************************************************************
      * Build the start of a row at START-ADDRESS:                    *
      *   - the 3 digit key length, or                                *
      *   - the delimiter, for every row except the first, and        *
      *   - the key.                                                  *
      * KEY-LENGTH is set by 3150-CHECK-ROW-SPACE.                     *
      * On exit, CURRENT-ADDRESS is the end of the key and ROW-LENGTH *
      * is the number of bytes built.                                 *
      *****************************************************************
       3200-BUILD-ROW-KEY.
           MOVE ZEROES                       TO ROW-LENGTH.
           MOVE START-ADDRESS-X              TO CURRENT-ADDRESS-X.
           SET ADDRESS OF ZFAM-MESSAGE       TO CURRENT-ADDRESS.

           IF  GET-CA-NO-DELIM
               MOVE KEY-LENGTH               TO ZFAM-MESSAGE(1:3)
               MOVE KEY-LENGTH-DIGITS        TO FIELD-LENGTH
               PERFORM 3500-APPEND-FIELD     THRU 3500-EXIT
           ELSE
               IF  MESSAGE-COUNT NOT EQUAL ZEROES
                   MOVE GET-CA-DELIM         TO ZFAM-MESSAGE(1:1)
                   MOVE DELIMITER-LENGTH     TO FIELD-LENGTH
                   PERFORM 3500-APPEND-FIELD THRU 3500-EXIT
               END-IF
           END-IF.

           MOVE FK-KEY(1:KEY-LENGTH)  TO ZFAM-MESSAGE(1:KEY-LENGTH).
           MOVE KEY-LENGTH                   TO FIELD-LENGTH.
           PERFORM 3500-APPEND-FIELD         THRU 3500-EXIT.

       3200-EXIT.
           EXIT.

      *****************************************************************
      * Append a KEYSONLY row.                                        *
      *****************************************************************
       3300-APPEND-KEY-ROW.
           PERFORM 3200-BUILD-ROW-KEY        THRU 3200-EXIT.
           PERFORM 3600-COMMIT-ROW           THRU 3600-EXIT.

       3300-EXIT.
           EXIT.

      *****************************************************************
      * Append a key and record data row.                             *
      *                                                               *
      * The record length is not known until all segments are read,   *
      * so a 7 digit placeholder is written and its address saved in  *
      * LENGTH-ADDRESS.  The row is discarded when the segments can   *
      * not be read or do not fit in the response buffer.             *
      *****************************************************************
       3400-APPEND-RECORD-ROW.
           PERFORM 3200-BUILD-ROW-KEY        THRU 3200-EXIT.

           MOVE CURRENT-ADDRESS-X            TO LENGTH-ADDRESS-X.

           IF  GET-CA-NO-DELIM
               MOVE ZEROES                   TO ZFAM-MESSAGE(1:7)
               MOVE RECORD-LENGTH-DIGITS     TO FIELD-LENGTH
           ELSE
               MOVE GET-CA-DELIM             TO ZFAM-MESSAGE(1:1)
               MOVE DELIMITER-LENGTH         TO FIELD-LENGTH
           END-IF.

           PERFORM 3500-APPEND-FIELD         THRU 3500-EXIT.

           MOVE FK-DDNAME                    TO FF-DDNAME.
           MOVE FK-FF-KEY                    TO FF-KEY.
           MOVE ZEROES                       TO FF-ZEROES.
           MOVE ONE                          TO FF-SEGMENT.
           MOVE ZEROES                       TO RECORD-LENGTH.

           SET SEGMENTS-SUCCESSFUL           TO TRUE.
           SET SEGMENTS-INCOMPLETE           TO TRUE.

           PERFORM 3410-READ-SEGMENT         THRU 3410-EXIT
               WITH TEST AFTER
               UNTIL SEGMENTS-COMPLETE OR SEGMENTS-FAILED.

           IF  SEGMENTS-SUCCESSFUL
               IF  GET-CA-NO-DELIM
                   SET ADDRESS OF ZFAM-MESSAGE TO LENGTH-ADDRESS
                   MOVE RECORD-LENGTH        TO ZFAM-MESSAGE(1:7)
                   MOVE RECORD-LENGTH-DIGITS TO FIELD-LENGTH
                   PERFORM 5000-ASCII        THRU 5000-EXIT
               END-IF
               ADD  RECORD-LENGTH            TO ROW-LENGTH
               PERFORM 3600-COMMIT-ROW       THRU 3600-EXIT
           END-IF.

       3400-EXIT.
           EXIT.

      *****************************************************************
      * Read one FILE store segment and append it to the row.         *
      *****************************************************************
       3410-READ-SEGMENT.
           MOVE LENGTH OF FF-RECORD          TO FF-LENGTH.

           EXEC CICS READ FILE(FF-FCT)
                INTO(FF-RECORD)
                RIDFLD(FF-KEY-16)
                LENGTH(FF-LENGTH)
                NOHANDLE
           END-EXEC.

           IF  EIBRESP NOT EQUAL DFHRESP(NORMAL)
               SET SEGMENTS-FAILED           TO TRUE
           ELSE
               IF  FF-SEGMENT EQUAL ONE
                   PERFORM 3420-CHECK-LENGTH THRU 3420-EXIT
               END-IF
           END-IF.

           IF  SEGMENTS-SUCCESSFUL
               SET ADDRESS OF ZFAM-MESSAGE   TO CURRENT-ADDRESS
               SUBTRACT FF-PREFIX          FROM FF-LENGTH
               MOVE FF-DATA(1:FF-LENGTH) TO ZFAM-MESSAGE(1:FF-LENGTH)
               ADD  FF-LENGTH                TO CURRENT-ADDRESS-X
               ADD  FF-LENGTH                TO RECORD-LENGTH
               IF  FF-SEGMENT EQUAL FF-SEGMENTS
                   SET SEGMENTS-COMPLETE     TO TRUE
               ELSE
                   ADD ONE                   TO FF-SEGMENT
               END-IF
           END-IF.

       3410-EXIT.
           EXIT.

      *****************************************************************
      * Compare the logical record length with the remaining buffer   *
      * length.  When there's not enough buffer to hold the record,   *
      * set the BUFFER-FULL condition, which ends the browse and      *
      * returns HTTP status code 206.                                 *
      *****************************************************************
       3420-CHECK-LENGTH.
           MULTIPLY FF-SEGMENTS BY THIRTY-TWO-KB
               GIVING LOGICAL-LENGTH.

           SUBTRACT MESSAGE-LENGTH ROW-LENGTH FROM GETMAIN-LENGTH
               GIVING AVAILABLE-LENGTH.

           IF  LOGICAL-LENGTH GREATER THAN AVAILABLE-LENGTH
               SET SEGMENTS-FAILED           TO TRUE
               SET BUFFER-FULL               TO TRUE
               SET PROCESS-COMPLETE          TO TRUE
           END-IF.

       3420-EXIT.
           EXIT.

      *****************************************************************
      * Convert the FIELD-LENGTH bytes at CURRENT-ADDRESS and advance *
      * CURRENT-ADDRESS and ROW-LENGTH past them.                     *
      *****************************************************************
       3500-APPEND-FIELD.
           PERFORM 5000-ASCII                THRU 5000-EXIT.
           ADD  FIELD-LENGTH                 TO CURRENT-ADDRESS-X.
           ADD  FIELD-LENGTH                 TO ROW-LENGTH.
           SET ADDRESS OF ZFAM-MESSAGE       TO CURRENT-ADDRESS.

       3500-EXIT.
           EXIT.

      *****************************************************************
      * Commit the row built at START-ADDRESS to the response.        *
      * Only committed rows count toward the ROWS limit.              *
      *****************************************************************
       3600-COMMIT-ROW.
           ADD  ROW-LENGTH                   TO MESSAGE-LENGTH.
           ADD  ROW-LENGTH                   TO START-ADDRESS-X.
           ADD  1                            TO MESSAGE-COUNT.
           ADD  1                            TO ROWS-COUNT.

       3600-EXIT.
           EXIT.

      *****************************************************************
      * Send the response.                                            *
      *                                                               *
      * zFAM-LastKey is the key to continue the browse from:          *
      *   - buffer full or zFAM-RangeEnd exceeded: the key before the *
      *     one that ended the browse.                                *
      *   - otherwise: the last key read.                             *
      *****************************************************************
       4000-SEND-RESPONSE.
           IF  MESSAGE-COUNT EQUAL ZEROES
               PERFORM 9100-NOT-FOUND        THRU 9100-EXIT
           END-IF.

           SET ADDRESS OF ZFAM-MESSAGE       TO ORIGINAL-ADDRESS.

           MOVE '4000-01'                    TO T_46_M.
           PERFORM 9995-TRACE              THRU 9995-EXIT.

           IF  FORMAT-KEYS-ONLY OR FF-MEDIA EQUAL SPACES
               MOVE TEXT-PLAIN               TO WEB-MEDIA-TYPE
           ELSE
               MOVE FF-MEDIA                 TO WEB-MEDIA-TYPE
           END-IF.

           INSPECT WEB-MEDIA-TYPE
               REPLACING ALL SPACES BY LOW-VALUES.

           EVALUATE TRUE
               WHEN BUFFER-FULL
                   MOVE PREVIOUS-KEY         TO LAST-KEY
                   MOVE HTTP-STATUS-206      TO HTTP-STATUS
               WHEN RANGE-EXCEEDED
                   MOVE PREVIOUS-KEY         TO LAST-KEY
                   MOVE HTTP-STATUS-200      TO HTTP-STATUS
               WHEN OTHER
                   MOVE FK-KEY               TO LAST-KEY
                   MOVE HTTP-STATUS-200      TO HTTP-STATUS
           END-EVALUATE.

           MOVE ZEROES                       TO TRAILING-NULLS.
           INSPECT FUNCTION REVERSE(LAST-KEY)
               TALLYING TRAILING-NULLS FOR LEADING LOW-VALUES.

           SUBTRACT TRAILING-NULLS FROM LENGTH OF LAST-KEY
               GIVING STATUS-LENGTH.

           PERFORM 9600-HEADER             THRU 9600-EXIT.

           MOVE DFHVALUE(IMMEDIATE)          TO SEND-ACTION.

           IF  WEB-MEDIA-TYPE(1:04) EQUAL TEXT-ANYTHING
           OR  WEB-MEDIA-TYPE(1:15) EQUAL APPLICATION-XML
           OR  WEB-MEDIA-TYPE(1:16) EQUAL APPLICATION-JSON
               EXEC CICS WEB SEND
                    FROM      (ZFAM-MESSAGE)
                    FROMLENGTH(MESSAGE-LENGTH)
                    MEDIATYPE (WEB-MEDIA-TYPE)
                    STATUSCODE(HTTP-STATUS)
                    STATUSTEXT(LAST-KEY)
                    STATUSLEN (STATUS-LENGTH)
                    ACTION    (SEND-ACTION)
                    SRVCONVERT
                    NOHANDLE
               END-EXEC
           ELSE
               EXEC CICS WEB SEND
                    FROM      (ZFAM-MESSAGE)
                    FROMLENGTH(MESSAGE-LENGTH)
                    MEDIATYPE (WEB-MEDIA-TYPE)
                    STATUSCODE(HTTP-STATUS)
                    STATUSTEXT(LAST-KEY)
                    STATUSLEN (STATUS-LENGTH)
                    ACTION    (SEND-ACTION)
                    NOSRVCONVERT
                    NOHANDLE
               END-EXEC
           END-IF.

       4000-EXIT.
           EXIT.

      *****************************************************************
      * When the HTTP Header 'zFAM-Select' is not 'text*', convert    *
      * the FIELD-LENGTH bytes of ZFAM-MESSAGE from EBCDIC to ASCII.  *
      *****************************************************************
       5000-ASCII.
           IF  SELECT-TYPE(1:4) NOT EQUAL TEXT-ANYTHING
               MOVE FUNCTION
               DISPLAY-OF
               (FUNCTION NATIONAL-OF
               (ZFAM-MESSAGE(1:FIELD-LENGTH), EBCDIC-CCSID) ASCII-CCSID)
               TO  ZFAM-MESSAGE(1:FIELD-LENGTH)
           END-IF.

       5000-EXIT.
           EXIT.

      *****************************************************************
      * Return to CICS                                                *
      *****************************************************************
       9000-RETURN.
           EXEC CICS RETURN
           END-EXEC.

       9000-EXIT.
           EXIT.

      *****************************************************************
      * No rows found.  Send empty zFAM-LastKey and zFAM-Rows headers *
      * with status 204 and return to CICS.                           *
      *****************************************************************
       9100-NOT-FOUND.
           MOVE ZEROES                       TO STATUS-LENGTH.
           MOVE ZEROES                       TO MESSAGE-COUNT.
           PERFORM 9600-HEADER             THRU 9600-EXIT.
           PERFORM 9700-STATUS-204         THRU 9700-EXIT.
           PERFORM 9000-RETURN             THRU 9000-EXIT.

       9100-EXIT.
           EXIT.

      *****************************************************************
      * Write the zFAM-LastKey and zFAM-Rows HTTP headers.            *
      *****************************************************************
       9600-HEADER.
           EXEC CICS WEB WRITE
                HTTPHEADER (HEADER-LASTKEY)
                NAMELENGTH (HEADER-LASTKEY-LENGTH)
                VALUE      (LAST-KEY)
                VALUELENGTH(STATUS-LENGTH)
                NOHANDLE
           END-EXEC.

           EXEC CICS WEB WRITE
                HTTPHEADER (HEADER-ROWS)
                NAMELENGTH (HEADER-ROWS-LENGTH)
                VALUE      (MESSAGE-COUNT)
                VALUELENGTH(MESSAGE-COUNT-LENGTH)
                NOHANDLE
           END-EXEC.

       9600-EXIT.
           EXIT.

      *****************************************************************
      * Status 204 response.                                          *
      *****************************************************************
       9700-STATUS-204.
           EXEC CICS DOCUMENT CREATE DOCTOKEN(DOCUMENT-TOKEN)
                NOHANDLE
           END-EXEC.

           MOVE DFHVALUE(IMMEDIATE)          TO SEND-ACTION.

           EXEC CICS WEB SEND
                DOCTOKEN(DOCUMENT-TOKEN)
                MEDIATYPE(TEXT-PLAIN)
                SRVCONVERT
                NOHANDLE
                ACTION(SEND-ACTION)
                STATUSCODE(HTTP-STATUS-204)
                STATUSTEXT(HTTP-NOT-FOUND)
                STATUSLEN (HTTP-NOT-FOUND-LENGTH)
           END-EXEC.

       9700-EXIT.
           EXIT.

      *****************************************************************
      * Issue TRACE.                                                  *
      *****************************************************************
       9995-TRACE.
           EXEC CICS ENTER TRACENUM(T_46)
                FROM(T_46_M)
                FROMLENGTH(T_LEN)
                RESOURCE(T_RES)
                NOHANDLE
           END-EXEC.

       9995-EXIT.
           EXIT.
