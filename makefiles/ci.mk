##########################
### CI/CD Workflows    ###
##########################

.PHONY: ci_test_workflow_local
ci_test_workflow_local: ## Run the test_feed.yml workflow locally using act
	$(call check_command,act)
	$(call print_info_section,Running test_feed workflow locally)
	$(Q)act --container-architecture linux/amd64 -W .github/workflows/test_feed.yml
	$(call print_success,Workflow completed)

.PHONY: ci_run_feeds_workflow_local
ci_run_feeds_workflow_local: ## Run the run_feeds.yml workflow locally using act
	$(call check_command,act)
	$(call print_info_section,Running run_feeds workflow locally)
	$(Q)act --container-architecture linux/amd64 -W .github/workflows/run_feeds.yml
	$(call print_success,Workflow completed)

.PHONY: ci_trigger_feeds_workflow
ci_trigger_feeds_workflow: ## Trigger the run_feeds.yml workflow on GitHub using gh
	$(call check_command,gh)
	$(call print_info,Triggering run_feeds workflow on GitHub)
	$(Q)gh workflow run run_feeds.yml
	$(call print_success,Workflow triggered)

.PHONY: ci_trigger_selenium_feeds_workflow
ci_trigger_selenium_feeds_workflow: ## Trigger the run_selenium_feeds.yml workflow on GitHub using gh
	$(call check_command,gh)
	$(call print_info,Triggering selenium feeds workflow on GitHub)
	$(Q)gh workflow run run_selenium_feeds.yml
	$(call print_success,Workflow triggered)

.PHONY: ci_trigger_validate_feeds_workflow
ci_trigger_validate_feeds_workflow: ## Trigger the validate_feeds.yml workflow on GitHub using gh
	$(call check_command,gh)
	$(call print_info,Triggering validate feeds workflow on GitHub)
	$(Q)gh workflow run validate_feeds.yml
	$(call print_success,Workflow triggered)

.PHONY: ci_trigger_test_feed_workflow
ci_trigger_test_feed_workflow: ## Trigger the test_feed.yml workflow on GitHub using gh
	$(call check_command,gh)
	$(call print_info,Triggering test feed workflow on GitHub)
	$(Q)gh workflow run test_feed.yml
	$(call print_success,Workflow triggered)

.PHONY: ci_run_selenium_feeds_workflow_local
ci_run_selenium_feeds_workflow_local: ## Run the run_selenium_feeds.yml workflow locally using act
	$(call check_command,act)
	$(call print_info_section,Running selenium feeds workflow locally)
	$(Q)act --container-architecture linux/amd64 -W .github/workflows/run_selenium_feeds.yml
	$(call print_success,Workflow completed)
