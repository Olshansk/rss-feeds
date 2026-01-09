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
feeds_anthropic_news: ## Generate RSS feed for Anthropic News (incremental)
	$(call check_venv)
	$(call print_info,Generating Anthropic News feed)
	$(Q)python feed_generators/anthropic_news_blog.py
	$(call print_success,Anthropic News feed generated)

.PHONY: feeds_anthropic_news_full
feeds_anthropic_news_full: ## Generate RSS feed for Anthropic News (full reset)
	$(call check_venv)
	$(call print_info,Generating Anthropic News feed - FULL RESET)
	$(Q)python feed_generators/anthropic_news_blog.py --full
	$(call print_success,Anthropic News feed generated - full reset)

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

.PHONY: feeds_anthropic_red
feeds_anthropic_red: ## Generate RSS feed for Anthropic Frontier Red Team
	$(call check_venv)
	$(call print_info,Generating Anthropic Red Team feed)
	$(Q)python feed_generators/anthropic_red_blog.py
	$(call print_success,Anthropic Red Team feed generated)

.PHONY: feeds_google_ai
feeds_google_ai: ## Generate RSS feed for Google AI Blog
	$(call check_venv)
	$(call print_info,Generating Google AI feed)
	$(Q)python feed_generators/google_ai_blog.py
	$(call print_success,Google AI feed generated)

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

.PHONY: feeds_thinkingmachines
feeds_thinkingmachines: ## Generate RSS feed for Thinking Machines Lab blog
	$(call check_venv)
	$(call print_info,Generating Thinking Machines Lab feed)
	$(Q)python feed_generators/thinkingmachines_blog.py
	$(call print_success,Thinking Machines Lab feed generated)

.PHONY: feeds_hamel
feeds_hamel: ## Generate RSS feed for Hamel Husain's Blog
	$(call check_venv)
	$(call print_info,Generating Hamel Husain Blog feed)
	$(Q)python feed_generators/hamel_blog.py
	$(call print_success,Hamel Husain Blog feed generated)

.PHONY: feeds_cursor
feeds_cursor: ## Generate RSS feed for Cursor Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Cursor Blog feed)
	$(Q)python feed_generators/cursor_blog.py
	$(call print_success,Cursor Blog feed generated)

.PHONY: feeds_cursor_full
feeds_cursor_full: ## Generate RSS feed for Cursor Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Cursor Blog feed - FULL RESET)
	$(Q)python feed_generators/cursor_blog.py --full
	$(call print_success,Cursor Blog feed generated - full reset)

.PHONY: feeds_windsurf_blog
feeds_windsurf_blog: ## Generate RSS feed for Windsurf Blog
	$(call check_venv)
	$(call print_info,Generating Windsurf Blog feed)
	$(Q)python feed_generators/windsurf_blog.py
	$(call print_success,Windsurf Blog feed generated)

.PHONY: feeds_windsurf_changelog
feeds_windsurf_changelog: ## Generate RSS feed for Windsurf Changelog
	$(call check_venv)
	$(call print_info,Generating Windsurf Changelog feed)
	$(Q)python feed_generators/windsurf_changelog.py
	$(call print_success,Windsurf Changelog feed generated)

.PHONY: feeds_windsurf_next_changelog
feeds_windsurf_next_changelog: ## Generate RSS feed for Windsurf Next Changelog
	$(call check_venv)
	$(call print_info,Generating Windsurf Next Changelog feed)
	$(Q)python feed_generators/windsurf_next_changelog.py
	$(call print_success,Windsurf Next Changelog feed generated)

.PHONY: feeds_the_batch
feeds_the_batch: ## Generate RSS feed for The Batch by DeepLearning.AI
	$(call check_venv)
	$(call print_info,Generating The Batch feed)
	$(Q)python feed_generators/deeplearningai_the_batch.py
	$(call print_success,The Batch feed generated)

.PHONY: feeds_dagster
feeds_dagster: ## Generate RSS feed for Dagster Blog
	$(call check_venv)
	$(call print_info,Generating Dagster Blog feed)
	$(Q)python feed_generators/dagster_blog.py
	$(call print_success,Dagster Blog feed generated)

.PHONY: clean_feeds
clean_feeds: ## Clean generated RSS feed files
	$(call print_warning,Removing generated RSS feeds)
	$(Q)rm -rf feeds/*.xml
	$(call print_success,RSS feeds removed)
