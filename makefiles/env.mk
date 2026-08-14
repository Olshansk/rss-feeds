##########################
### Environment Setup  ###
##########################

.PHONY: env_setup
env_setup: ## Sync project dependencies with uv
	$(call print_info_section,Setting up environment)
	$(Q)uv sync
	$(call print_success,Environment ready)

.PHONY: clean_env
clean_env: ## Remove uv's project environment
	$(call print_warning,Removing uv project environment)
	$(Q)rm -rf .venv
	$(call print_success,uv project environment removed)
