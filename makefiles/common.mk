# Strict shell + sane make defaults

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# VERBOSE=1 to show commands

ifdef VERBOSE
	Q :=
else
	Q := @
endif

# Timestamp & common dirs

TIMESTAMP := $(shell date '+%Y-%m-%d %H:%M:%S')
ROOT_DIR := $(shell pwd)
BUILD_DIR := $(ROOT_DIR)/build
DIST_DIR := $(ROOT_DIR)/dist
DOCS_DIR := $(ROOT_DIR)/docs
TMP_DIR := $(ROOT_DIR)/tmp
FEEDS_DIR := $(ROOT_DIR)/feeds
GENERATORS_DIR := $(ROOT_DIR)/feed_generators

$(BUILD_DIR) $(DIST_DIR) $(TMP_DIR):
	$(Q)mkdir -p $@

# Guards & checks

define check_command
	@command -v $(1) >/dev/null 2>&1 || { \
		printf "$(RED)Missing tool: $(1)$(RESET)\n"; \
		exit 1; \
	}
endef

# Kept as a compatibility shim for existing feed targets. `uv run` manages the
# project environment, so manual activation is neither required nor checked.
define check_venv
	@:
endef

.PHONY: prompt_confirm
prompt_confirm: ## Prompt before continuing
	@printf "$(YELLOW)Continue? [y/N] $(RESET)"; read ans; [ $${ans:-N} = y ]

.PHONY: debug_vars
debug_vars: ## Print key variables
	$(call print_info_section,Debug variables)
	$(Q)printf "ROOT_DIR=%s\nFEEDS_DIR=%s\nGENERATORS_DIR=%s\n" "$(ROOT_DIR)" "$(FEEDS_DIR)" "$(GENERATORS_DIR)"
