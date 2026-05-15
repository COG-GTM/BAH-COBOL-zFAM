# Makefile for zFAM COBOL programs
#
# Compiles COBOL source files using GnuCOBOL with CICS preprocessing.
# The CICS preprocessor replaces EXEC CICS blocks with stubs so the
# COBOL syntax and data-division logic can be validated on Linux.
#
# Usage:
#   make all         - Preprocess and compile all COBOL programs
#   make syntax      - Syntax-check only (no object code)
#   make clean       - Remove build artifacts
#   make test        - Run tests
#   make check       - Run syntax check + tests

COBC       := cobc
PREPROCESS := ./build/preprocess-cics.sh

SRC_DIR    := Source
BUILD_DIR  := build/preprocessed
CPY_DIR    := build/copybooks
OBJ_DIR    := build/obj
TEST_DIR   := tests
TEST_BUILD := build/tests

COPYBOOK_DIRS := -I $(CPY_DIR) -I build/cics-stubs

# COBOL source files (programs that produce modules)
COBOL_SRCS := ZFAM000 ZFAM002 ZFAM003 ZFAM004 ZFAM005 \
              ZFAM007 ZFAM008 ZFAM009 ZFAM011 ZFAM031 \
              ZFAM090 ZFAM101 ZFAM102 ZFAMPLT

# Copybook source files
COPYBOOKS := ZFAMFKC ZFAMFFC ZFAMHEX ZFAMCIC HANDLE

PREPROCESSED     := $(addprefix $(BUILD_DIR)/, $(addsuffix .cbl, $(COBOL_SRCS)))
CLEAN_COPYBOOKS  := $(addprefix $(CPY_DIR)/, $(addsuffix .cpy, $(COPYBOOKS)))
OBJECTS          := $(addprefix $(OBJ_DIR)/, $(addsuffix .o, $(COBOL_SRCS)))

COBC_FLAGS := -x -std=default -w $(COPYBOOK_DIRS)

.PHONY: all syntax clean test check help copybooks

help:
	@echo "zFAM Build System (GnuCOBOL)"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Preprocess and compile all COBOL programs"
	@echo "  syntax   - Syntax-check only (no object code generated)"
	@echo "  clean    - Remove all build artifacts"
	@echo "  test     - Run unit tests"
	@echo "  check    - Run syntax check + tests"
	@echo "  help     - Show this help message"

all: $(OBJECTS)
	@echo ""
	@echo "Build complete: $(words $(OBJECTS)) programs compiled successfully."

# Strip CRLF from copybooks
copybooks: $(CLEAN_COPYBOOKS)

$(CPY_DIR)/%.cpy: $(SRC_DIR)/%.cpy | $(CPY_DIR)
	@tr -d '\r' < $< > $@

# Preprocess CICS source to GnuCOBOL-compatible source
$(BUILD_DIR)/%.cbl: $(SRC_DIR)/%.cbl $(PREPROCESS) | $(BUILD_DIR) copybooks
	@$(PREPROCESS) $< $@

# Compile preprocessed source to object
$(OBJ_DIR)/%.o: $(BUILD_DIR)/%.cbl | $(OBJ_DIR)
	$(COBC) $(COBC_FLAGS) -c -o $@ $<

# Syntax-check only
syntax: $(PREPROCESSED)
	@echo "Running syntax check on all COBOL programs..."
	@PASS=0; FAIL=0; \
	for src in $(PREPROCESSED); do \
		prog=$$(basename $$src .cbl); \
		if $(COBC) -fsyntax-only -std=default -w $(COPYBOOK_DIRS) $$src 2>/dev/null; then \
			echo "  PASS  $$prog"; \
			PASS=$$((PASS + 1)); \
		else \
			echo "  FAIL  $$prog"; \
			$(COBC) -fsyntax-only -std=default -w $(COPYBOOK_DIRS) $$src 2>&1 | head -5; \
			FAIL=$$((FAIL + 1)); \
		fi; \
	done; \
	echo ""; \
	echo "Syntax check complete: $$PASS passed, $$FAIL failed."; \
	if [ $$FAIL -gt 0 ]; then exit 1; fi

# Run tests
test: $(PREPROCESSED) copybooks | $(TEST_BUILD)
	@echo "Running tests..."
	@bash $(TEST_DIR)/run_tests.sh

# Combined check
check: syntax test

# Create build directories
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(CPY_DIR):
	mkdir -p $(CPY_DIR)

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

$(TEST_BUILD):
	mkdir -p $(TEST_BUILD)

clean:
	rm -rf $(BUILD_DIR) $(CPY_DIR) $(OBJ_DIR) $(TEST_BUILD)
	@echo "Build artifacts cleaned."
