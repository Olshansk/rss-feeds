##########################
### Development Tools  ###
##########################

.PHONY: dev_setup
dev_setup: ## Install dev dependencies and pre-commit hooks
	$(call print_info_section,Setting up development environment)
	$(Q)uv sync --group dev
	$(Q)uv run pre-commit install
	$(call print_success,Dev environment ready)

.PHONY: dev_lint
dev_lint: ## Check code with ruff (lint + format check)
	$(call print_info_section,Checking code style)
	$(Q)uv run ruff check .
	$(Q)uv run ruff format --check .
	$(call print_success,Code style OK)

.PHONY: dev_lint_fix
dev_lint_fix: ## Auto-fix lint issues and format code
	$(call print_info_section,Fixing code style)
	$(Q)uv run ruff check --fix .
	$(Q)uv run ruff format .
	$(call print_success,Code formatted)

.PHONY: dev_format
dev_format: dev_lint_fix ## Alias for dev_lint_fix (backwards compatible)

.PHONY: dev_test_feed
dev_test_feed: ## Run a test feed generator (ollama)
	$(call print_info,Running ollama_blog.py as test feed)
	$(Q)uv run feed_generators/ollama_blog.py
	$(call print_success,Test feed completed)

.PHONY: dev_test_all
dev_test_all: ## Validate feeds, regenerate non-selenium feeds, then re-validate
	$(call print_info_section,Running full test suite)
	$(call print_info,Validating existing feeds)
	$(Q)uv run feed_generators/validate_feeds.py
	$(call print_info,Regenerating non-selenium feeds)
	$(Q)uv run feed_generators/run_all_feeds.py --skip-selenium
	$(call print_info,Re-validating feeds)
	$(Q)uv run feed_generators/validate_feeds.py
	$(call print_success,All tests passed)
