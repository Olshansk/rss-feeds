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
	$(Q)uv run ruff format --check feed_generators/
	$(call print_success,Code style OK)

.PHONY: dev_lint_fix
dev_lint_fix: ## Auto-fix lint issues and format code
	$(call print_info_section,Fixing code style)
	$(Q)uv run ruff check --fix .
	$(Q)uv run ruff format feed_generators/
	$(call print_success,Code formatted)

.PHONY: dev_format
dev_format: dev_lint_fix ## Alias for dev_lint_fix (backwards compatible)

.PHONY: dev_test_feed
dev_test_feed: ## Run a test feed generator (ollama)
	$(call print_info,Running ollama_blog.py as test feed)
	$(Q)uv run feed_generators/ollama_blog.py
	$(call print_success,Test feed completed)

.PHONY: dev_test_opml
dev_test_opml: ## Run focused Make-based tests for OPML generation
	$(call print_info,Running OPML generation tests)
	$(Q)uv run feed_generators/run_generate_opml.py
	$(call print_info,Test and check OPML unchanged)
	$(Q)uv run feed_generators/run_generate_opml.py 2>&1 | grep -q 'OPML content is unchanged'
	$(call print_info,Check feeds links no anchor)
	$(Q)! grep -q '#force_feed' feeds/feeds.opml
	$(call print_info,Add new feeds)
	$(Q)printf '%s\n' '<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>Atom Self Feed</title><atom:link href="https://feeds.example.com/atom-self.xml" rel="self" /></channel></rss>' > feeds/feed_atom_self.xml
	$(Q)printf '%s\n' '<rss><channel><title>Missing Self Feed</title></channel></rss>' > feeds/feed_missing_self.xml
	$(call print_info,Test new feeds OPML generation)
	$(Q)uv run feed_generators/run_generate_opml.py --xml-url-anchor "#force_feed"
	$(call print_info,Check new feeds links exists)
	$(Q)grep -q 'xmlUrl="https://feeds.example.com/atom-self.xml#force_feed"' feeds/feeds.opml
	$(Q)grep -q 'xmlUrl="https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_missing_self.xml#force_feed"' feeds/feeds.opml
	$(call print_info,Clean new feeds)
	$(Q)rm -f feeds/feed_atom_self.xml feeds/feed_missing_self.xml
	$(Q)uv run feed_generators/run_generate_opml.py
	$(call print_success,OPML tests completed)

.PHONY: dev_test_all
dev_test_all: ## Validate feeds, test OPML, regenerate non-selenium feeds, then re-validate
	$(call print_info_section,Running full test suite)
	$(call print_info,Validating existing feeds)
	$(Q)uv run feed_generators/validate_feeds.py
	$(call print_info,Regenerating non-selenium feeds)
	$(Q)uv run feed_generators/run_all_feeds.py --skip-selenium
	$(call print_info,Re-validating feeds)
	$(Q)uv run feed_generators/validate_feeds.py
	$(call print_success,All tests passed)
