##########################
### Development Tools  ###
##########################

.PHONY: dev_format
dev_format: ## Format Python code
	$(call check_venv)
	$(call print_info_section,Formatting Python code)
	$(Q)black .
	$(Q)isort .
	$(call print_success,Code formatted)

.PHONY: dev_test_feed
dev_test_feed: ## Run a test feed generator (ollama)
	$(call check_venv)
	$(call print_info,Running ollama_blog.py as test feed)
	$(Q)python feed_generators/ollama_blog.py
	$(call print_success,Test feed completed)

.PHONY: dev_test_all
dev_test_all: ## Validate feeds, regenerate non-selenium feeds, then re-validate
	$(call check_venv)
	$(call print_info_section,Running full test suite)
	$(call print_info,Validating existing feeds)
	$(Q)python feed_generators/validate_feeds.py
	$(call print_info,Regenerating non-selenium feeds)
	$(Q)python feed_generators/run_all_feeds.py --skip-selenium
	$(call print_info,Re-validating feeds)
	$(Q)python feed_generators/validate_feeds.py
	$(call print_success,All tests passed)
