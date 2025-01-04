import os
import subprocess
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_all_feeds():
    """Run all Python scripts in the feed_generators directory."""
    feed_generators_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(feed_generators_dir):
        if filename.endswith(".py") and filename != os.path.basename(__file__):
            script_path = os.path.join(feed_generators_dir, filename)
            logger.info(f"Running script: {script_path}")
            result = subprocess.run(["python", script_path], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully ran script: {script_path}")
            else:
                logger.error(f"Error running script: {script_path}\n{result.stderr}")

if __name__ == "__main__":
    run_all_feeds()
