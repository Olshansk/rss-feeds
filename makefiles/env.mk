##########################
### Environment Setup  ###
##########################

.PHONY: env_setup
env_setup: ## Create virtual environment and install dependencies
	$(call print_info_section,Setting up environment)
	$(Q)uv sync
	$(call print_success,Environment ready)

.PHONY: env_source
env_source: ## Source the env; must be executed like: $$(make env_source)
	@echo 'source .venv/bin/activate'

.PHONY: clean_env
clean_env: ## Clean virtual environment
	$(call print_warning,Removing virtual environment)
	$(Q)rm -rf venv .venv
	$(call print_success,Virtual environment removed)
