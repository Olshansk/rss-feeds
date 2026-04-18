##########################
### RSS Feed Generation ##
##########################

.PHONY: feeds_generate_all
feeds_generate_all: ## Generate all RSS feeds
	$(call check_venv)
	$(call print_info_section,Generating all RSS feeds)
	$(Q)uv run feed_generators/run_all_feeds.py
	$(call print_success,All feeds generated)

.PHONY: feeds_ai_first_podcast
feeds_ai_first_podcast: ## Generate RSS feed for AI FIRST Podcast (incremental)
	$(call check_venv)
	$(call print_info,Generating AI FIRST Podcast feed)
	$(Q)uv run feed_generators/ai_first_podcast.py
	$(call print_success,AI FIRST Podcast feed generated)

.PHONY: feeds_ai_first_podcast_full
feeds_ai_first_podcast_full: ## Generate RSS feed for AI FIRST Podcast (full reset)
	$(call check_venv)
	$(call print_info,Generating AI FIRST Podcast feed - FULL RESET)
	$(Q)uv run feed_generators/ai_first_podcast.py --full
	$(call print_success,AI FIRST Podcast feed generated - full reset)

.PHONY: feeds_anthropic_news
feeds_anthropic_news: ## Generate RSS feed for Anthropic News (incremental)
	$(call check_venv)
	$(call print_info,Generating Anthropic News feed)
	$(Q)uv run feed_generators/anthropic_news_blog.py
	$(call print_success,Anthropic News feed generated)

.PHONY: feeds_anthropic_news_full
feeds_anthropic_news_full: ## Generate RSS feed for Anthropic News (full reset)
	$(call check_venv)
	$(call print_info,Generating Anthropic News feed - FULL RESET)
	$(Q)uv run feed_generators/anthropic_news_blog.py --full
	$(call print_success,Anthropic News feed generated - full reset)

.PHONY: feeds_anthropic_engineering
feeds_anthropic_engineering: ## Generate RSS feed for Anthropic Engineering
	$(call check_venv)
	$(call print_info,Generating Anthropic Engineering feed)
	$(Q)uv run feed_generators/anthropic_eng_blog.py
	$(call print_success,Anthropic Engineering feed generated)

.PHONY: feeds_anthropic_research
feeds_anthropic_research: ## Generate RSS feed for Anthropic Research
	$(call check_venv)
	$(call print_info,Generating Anthropic Research feed)
	$(Q)uv run feed_generators/anthropic_research_blog.py
	$(call print_success,Anthropic Research feed generated)

.PHONY: feeds_anthropic_red
feeds_anthropic_red: ## Generate RSS feed for Anthropic Frontier Red Team
	$(call check_venv)
	$(call print_info,Generating Anthropic Red Team feed)
	$(Q)uv run feed_generators/anthropic_red_blog.py
	$(call print_success,Anthropic Red Team feed generated)

.PHONY: feeds_google_ai
feeds_google_ai: ## Generate RSS feed for Google AI Blog
	$(call check_venv)
	$(call print_info,Generating Google AI feed)
	$(Q)uv run feed_generators/google_ai_blog.py
	$(call print_success,Google AI feed generated)

.PHONY: feeds_ollama
feeds_ollama: ## Generate RSS feed for Ollama Blog
	$(call check_venv)
	$(call print_info,Generating Ollama Blog feed)
	$(Q)uv run feed_generators/ollama_blog.py
	$(call print_success,Ollama Blog feed generated)

.PHONY: feeds_paulgraham
feeds_paulgraham: ## Generate RSS feed for Paul Graham's articles
	$(call check_venv)
	$(call print_info,Generating Paul Graham feed)
	$(Q)uv run feed_generators/paulgraham_blog.py
	$(call print_success,Paul Graham feed generated)

.PHONY: feeds_blogsurgeai
feeds_blogsurgeai: ## Generate RSS feed for Surge AI Blog
	$(call check_venv)
	$(call print_info,Generating Surge AI Blog feed)
	$(Q)uv run feed_generators/blogsurgeai_feed_generator.py
	$(call print_success,Surge AI Blog feed generated)

.PHONY: feeds_xainews
feeds_xainews: ## Generate RSS feed for xAI News
	$(call check_venv)
	$(call print_info,Generating xAI News feed)
	$(Q)uv run feed_generators/xainews_blog.py
	$(call print_success,xAI News feed generated)

.PHONY: feeds_chanderramesh
feeds_chanderramesh: ## Generate RSS feed for Chander Ramesh's writing
	$(call check_venv)
	$(call print_info,Generating Chander Ramesh feed)
	$(Q)uv run feed_generators/chanderramesh_blog.py
	$(call print_success,Chander Ramesh feed generated)

.PHONY: feeds_claude
feeds_claude: ## Generate RSS feed for Claude Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Claude Blog feed)
	$(Q)uv run feed_generators/claude_blog.py
	$(call print_success,Claude Blog feed generated)

.PHONY: feeds_claude_full
feeds_claude_full: ## Generate RSS feed for Claude Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Claude Blog feed - FULL RESET)
	$(Q)uv run feed_generators/claude_blog.py --full
	$(call print_success,Claude Blog feed generated - full reset)

.PHONY: feeds_thinkingmachines
feeds_thinkingmachines: ## Generate RSS feed for Thinking Machines Lab blog
	$(call check_venv)
	$(call print_info,Generating Thinking Machines Lab feed)
	$(Q)uv run feed_generators/thinkingmachines_blog.py
	$(call print_success,Thinking Machines Lab feed generated)

.PHONY: feeds_cursor
feeds_cursor: ## Generate RSS feed for Cursor Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Cursor Blog feed)
	$(Q)uv run feed_generators/cursor_blog.py
	$(call print_success,Cursor Blog feed generated)

.PHONY: feeds_cursor_full
feeds_cursor_full: ## Generate RSS feed for Cursor Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Cursor Blog feed - FULL RESET)
	$(Q)uv run feed_generators/cursor_blog.py --full
	$(call print_success,Cursor Blog feed generated - full reset)

.PHONY: feeds_windsurf_blog
feeds_windsurf_blog: ## Generate RSS feed for Windsurf Blog
	$(call check_venv)
	$(call print_info,Generating Windsurf Blog feed)
	$(Q)uv run feed_generators/windsurf_blog.py
	$(call print_success,Windsurf Blog feed generated)

.PHONY: feeds_windsurf_changelog
feeds_windsurf_changelog: ## Generate RSS feed for Windsurf Changelog
	$(call check_venv)
	$(call print_info,Generating Windsurf Changelog feed)
	$(Q)uv run feed_generators/windsurf_changelog.py
	$(call print_success,Windsurf Changelog feed generated)

.PHONY: feeds_windsurf_next_changelog
feeds_windsurf_next_changelog: ## Generate RSS feed for Windsurf Next Changelog
	$(call check_venv)
	$(call print_info,Generating Windsurf Next Changelog feed)
	$(Q)uv run feed_generators/windsurf_next_changelog.py
	$(call print_success,Windsurf Next Changelog feed generated)

.PHONY: feeds_the_batch
feeds_the_batch: ## Generate RSS feed for The Batch by DeepLearning.AI
	$(call check_venv)
	$(call print_info,Generating The Batch feed)
	$(Q)uv run feed_generators/deeplearningai_the_batch.py
	$(call print_success,The Batch feed generated)

.PHONY: feeds_dagster
feeds_dagster: ## Generate RSS feed for Dagster Blog
	$(call check_venv)
	$(call print_info,Generating Dagster Blog feed)
	$(Q)uv run feed_generators/dagster_blog.py
	$(call print_success,Dagster Blog feed generated)

.PHONY: feeds_cohere
feeds_cohere: ## Generate RSS feed for Cohere Blog
	$(call check_venv)
	$(call print_info,Generating Cohere Blog feed)
	$(Q)uv run feed_generators/cohere_blog.py
	$(call print_success,Cohere Blog feed generated)

.PHONY: feeds_groq
feeds_groq: ## Generate RSS feed for Groq Blog
	$(call check_venv)
	$(call print_info,Generating Groq Blog feed)
	$(Q)uv run feed_generators/groq_blog.py
	$(call print_success,Groq Blog feed generated)

.PHONY: feeds_meta_ai
feeds_meta_ai: ## Generate RSS feed for AI at Meta Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Meta AI Blog feed)
	$(Q)uv run feed_generators/meta_ai_blog.py
	$(call print_success,Meta AI Blog feed generated)

.PHONY: feeds_meta_ai_full
feeds_meta_ai_full: ## Generate RSS feed for AI at Meta Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Meta AI Blog feed - FULL RESET)
	$(Q)uv run feed_generators/meta_ai_blog.py --full
	$(call print_success,Meta AI Blog feed generated - full reset)

.PHONY: feeds_mistral
feeds_mistral: ## Generate RSS feed for Mistral AI News (incremental)
	$(call check_venv)
	$(call print_info,Generating Mistral AI News feed)
	$(Q)uv run feed_generators/mistral_blog.py
	$(call print_success,Mistral AI News feed generated)

.PHONY: feeds_mistral_full
feeds_mistral_full: ## Generate RSS feed for Mistral AI News (full reset)
	$(call check_venv)
	$(call print_info,Generating Mistral AI News feed - FULL RESET)
	$(Q)uv run feed_generators/mistral_blog.py --full
	$(call print_success,Mistral AI News feed generated - full reset)

.PHONY: feeds_perplexity_hub
feeds_perplexity_hub: ## Generate RSS feed for Perplexity Hub (incremental)
	$(call check_venv)
	$(call print_info,Generating Perplexity Hub feed)
	$(Q)uv run feed_generators/perplexity_hub.py
	$(call print_success,Perplexity Hub feed generated)

.PHONY: feeds_perplexity_hub_full
feeds_perplexity_hub_full: ## Generate RSS feed for Perplexity Hub (full reset)
	$(call check_venv)
	$(call print_info,Generating Perplexity Hub feed - FULL RESET)
	$(Q)uv run feed_generators/perplexity_hub.py --full
	$(call print_success,Perplexity Hub feed generated - full reset)

.PHONY: feeds_pinecone
feeds_pinecone: ## Generate RSS feed for Pinecone Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Pinecone Blog feed)
	$(Q)uv run feed_generators/pinecone_blog.py
	$(call print_success,Pinecone Blog feed generated)

.PHONY: feeds_pinecone_full
feeds_pinecone_full: ## Generate RSS feed for Pinecone Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Pinecone Blog feed - FULL RESET)
	$(Q)uv run feed_generators/pinecone_blog.py --full
	$(call print_success,Pinecone Blog feed generated - full reset)

.PHONY: feeds_weaviate
feeds_weaviate: ## Generate RSS feed for Weaviate Blog (incremental)
	$(call check_venv)
	$(call print_info,Generating Weaviate Blog feed)
	$(Q)uv run feed_generators/weaviate_blog.py
	$(call print_success,Weaviate Blog feed generated)

.PHONY: feeds_weaviate_full
feeds_weaviate_full: ## Generate RSS feed for Weaviate Blog (full reset)
	$(call check_venv)
	$(call print_info,Generating Weaviate Blog feed - FULL RESET)
	$(Q)uv run feed_generators/weaviate_blog.py --full
	$(call print_success,Weaviate Blog feed generated - full reset)

.PHONY: clean_feeds
clean_feeds: ## Clean generated RSS feed files
	$(call print_warning,Removing generated RSS feeds)
	$(Q)rm -rf feeds/*.xml
	$(call print_success,RSS feeds removed)
