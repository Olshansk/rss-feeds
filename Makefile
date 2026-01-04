#########################
### Makefile (root)   ###
#########################

.DEFAULT_GOAL := help

# Patterns for classified help categories
HELP_PATTERNS := \
	'^help:' \
	'^env_.*:' \
	'^feeds_.*:' \
	'^dev_.*:' \
	'^ci_.*:' \
	'^clean_.*:' \
	'^debug_vars:'

.PHONY: help
help: ## Show all available targets with descriptions
	@printf "\n"
	@printf "$(BOLD)$(CYAN)📋 RSS Feed Generator - Makefile Targets$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)=== 📋 Information & Discovery ===$(RESET)\n"
	@grep -h -E '^(help|help-unclassified):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}'
	@printf "\n"
	@printf "$(BOLD)=== 🐍 Environment Setup ===$(RESET)\n"
	@grep -h -E '^env_.*:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}' | sort -u
	@printf "\n"
	@printf "$(BOLD)=== 📡 RSS Feed Generation ===$(RESET)\n"
	@grep -h -E '^feeds_.*:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}' | sort -u
	@printf "\n"
	@printf "$(BOLD)=== 🛠️ Development ===$(RESET)\n"
	@grep -h -E '^dev_.*:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}' | sort -u
	@printf "\n"
	@printf "$(BOLD)=== 🚀 CI/CD ===$(RESET)\n"
	@grep -h -E '^ci_.*:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}' | sort -u
	@printf "\n"
	@printf "$(BOLD)=== 🧹 Cleaning ===$(RESET)\n"
	@grep -h -E '^clean_.*:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}' | sort -u
	@printf "\n"
	@printf "$(YELLOW)Usage:$(RESET) make <target>\n"
	@printf "\n"

.PHONY: help-unclassified
help-unclassified: ## Show all unclassified targets
	@printf "\n"
	@printf "$(BOLD)$(CYAN)📦 Unclassified Targets$(RESET)\n"
	@printf "\n"
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | sed 's/:.*//g' | sort -u > /tmp/all_targets.txt
	@( \
		for pattern in $(HELP_PATTERNS); do \
			grep -h -E "$pattern.*?## .*\$$" $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null || true; \
		done \
	) | sed 's/:.*//g' | sort -u > /tmp/classified_targets.txt
	@comm -23 /tmp/all_targets.txt /tmp/classified_targets.txt | while read target; do \
		grep -h -E "^$$target:.*?## .*\$$" $(MAKEFILE_LIST) ./makefiles/*.mk 2>/dev/null | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-40s$(RESET) %s\n", $$1, $$2}'; \
	done
	@rm -f /tmp/all_targets.txt /tmp/classified_targets.txt
	@printf "\n"

################
### Imports  ###
################

include ./makefiles/colors.mk
include ./makefiles/common.mk
include ./makefiles/env.mk
include ./makefiles/feeds.mk
include ./makefiles/dev.mk
include ./makefiles/ci.mk

############################
### Legacy Target Aliases ##
############################

# Maintain backwards compatibility with existing targets

.PHONY: check-env
check-env: ## (Legacy) Check if virtual environment is activated
	$(call check_venv)

.PHONY: env_create
env_create: ## (Legacy) Create virtual environment

.PHONY: uvx_install
uvx_install: env_install ## (Legacy) Install dependencies

.PHONY: clean
clean: clean_env clean_feeds ## (Legacy) Clean all generated files

.PHONY: py_format
py_format: dev_format ## (Legacy) Format Python code

.PHONY: generate_all_feeds
generate_all_feeds: feeds_generate_all ## (Legacy) Generate all RSS feeds

.PHONY: generate_anthropic_news_feed
generate_anthropic_news_feed: feeds_anthropic_news ## (Legacy) Generate Anthropic News feed

.PHONY: generate_anthropic_engineering_feed
generate_anthropic_engineering_feed: feeds_anthropic_engineering ## (Legacy) Generate Anthropic Engineering feed

.PHONY: generate_anthropic_research_feed
generate_anthropic_research_feed: feeds_anthropic_research ## (Legacy) Generate Anthropic Research feed

.PHONY: generate_anthropic_changelog_claude_code_feed
generate_anthropic_changelog_claude_code_feed: feeds_anthropic_changelog_claude_code ## (Legacy) Generate Claude Code changelog feed

.PHONY: generate_openai_research_feed
generate_openai_research_feed: feeds_openai_research ## (Legacy) Generate OpenAI Research feed

.PHONY: generate_ollama_feed
generate_ollama_feed: feeds_ollama ## (Legacy) Generate Ollama feed

.PHONY: generate_paulgraham_feed
generate_paulgraham_feed: feeds_paulgraham ## (Legacy) Generate Paul Graham feed

.PHONY: generate_blogsurgeai_feed
generate_blogsurgeai_feed: feeds_blogsurgeai ## (Legacy) Generate Surge AI Blog feed

.PHONY: generate_xainews_feed
generate_xainews_feed: feeds_xainews ## (Legacy) Generate xAI News feed

.PHONY: generate_thinkingmachines_feed
generate_thinkingmachines_feed: feeds_thinkingmachines ## (Legacy) Generate Thinking Machines Lab feed

.PHONY: test_feed_workflow
test_feed_workflow: ci_test_workflow_local ## (Legacy) Test feed workflow locally

.PHONY: test_feed_generate
test_feed_generate: dev_test_feed ## (Legacy) Run test feed generator

.PHONY: act_run_feeds_workflow
act_run_feeds_workflow: ci_run_feeds_workflow_local ## (Legacy) Run feeds workflow locally

.PHONY: gh_run_feeds_workflow
gh_run_feeds_workflow: ci_trigger_feeds_workflow ## (Legacy) Trigger feeds workflow on GitHub

.PHONY: generate_the_batch_feed
generate_the_batch_feed: feeds_the_batch ## (Legacy) Generate The Batch feed
