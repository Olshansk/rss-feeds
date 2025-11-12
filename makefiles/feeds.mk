##########################
### RSS Feed Generation ##
##########################

.PHONY: feeds_generate_all
feeds_generate_all: ## Generate all RSS feeds
	$(call check_venv)
	$(call print_info_section,Generating all RSS feeds)
	$(Q)python feed_generators/run_all_feeds.py
	$(call print_success,All feeds generated)

.PHONY: feeds_anthropic_news
feeds_anthropic_news: ## Generate RSS feed for Anthropic News
	$(call check_venv)
	$(call print_info,Generating Anthropic News feed)
	$(Q)python feed_generators/anthropic_news_blog.py
	$(call print_success,Anthropic News feed generated)

.PHONY: feeds_anthropic_engineering
feeds_anthropic_engineering: ## Generate RSS feed for Anthropic Engineering
	$(call check_venv)
	$(call print_info,Generating Anthropic Engineering feed)
	$(Q)python feed_generators/anthropic_eng_blog.py
	$(call print_success,Anthropic Engineering feed generated)

.PHONY: feeds_anthropic_research
feeds_anthropic_research: ## Generate RSS feed for Anthropic Research
	$(call check_venv)
	$(call print_info,Generating Anthropic Research feed)
	$(Q)python feed_generators/anthropic_research_blog.py
	$(call print_success,Anthropic Research feed generated)

.PHONY: feeds_anthropic_changelog_claude_code
feeds_anthropic_changelog_claude_code: ## Generate RSS feed for Anthropic Claude Code changelog
	$(call check_venv)
	$(call print_info,Generating Claude Code changelog feed)
	$(Q)python feed_generators/anthropic_changelog_claude_code.py
	$(call print_success,Claude Code changelog feed generated)

.PHONY: feeds_openai_research
feeds_openai_research: ## Generate RSS feed for OpenAI Research
	$(call check_venv)
	$(call print_info,Generating OpenAI Research feed)
	$(Q)python feed_generators/openai_research_blog.py
	$(call print_success,OpenAI Research feed generated)

.PHONY: feeds_ollama
feeds_ollama: ## Generate RSS feed for Ollama Blog
	$(call check_venv)
	$(call print_info,Generating Ollama Blog feed)
	$(Q)python feed_generators/ollama_blog.py
	$(call print_success,Ollama Blog feed generated)

.PHONY: feeds_paulgraham
feeds_paulgraham: ## Generate RSS feed for Paul Graham's articles
	$(call check_venv)
	$(call print_info,Generating Paul Graham feed)
	$(Q)python feed_generators/paulgraham_blog.py
	$(call print_success,Paul Graham feed generated)

.PHONY: feeds_blogsurgeai
feeds_blogsurgeai: ## Generate RSS feed for Surge AI Blog
	$(call check_venv)
	$(call print_info,Generating Surge AI Blog feed)
	$(Q)python feed_generators/blogsurgeai_feed_generator.py
	$(call print_success,Surge AI Blog feed generated)

.PHONY: feeds_xainews
feeds_xainews: ## Generate RSS feed for xAI News
	$(call check_venv)
	$(call print_info,Generating xAI News feed)
	$(Q)python feed_generators/xainews_blog.py
	$(call print_success,xAI News feed generated)

.PHONY: feeds_chanderramesh
feeds_chanderramesh: ## Generate RSS feed for Chander Ramesh's writing
	$(call check_venv)
	$(call print_info,Generating Chander Ramesh feed)
	$(Q)python feed_generators/chanderramesh_blog.py
	$(call print_success,Chander Ramesh feed generated)

.PHONY: clean_feeds
clean_feeds: ## Clean generated RSS feed files
	$(call print_warning,Removing generated RSS feeds)
	$(Q)rm -rf feeds/*.xml
	$(call print_success,RSS feeds removed)
