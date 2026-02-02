from pathlib import Path

# root project (folder paling luar)
BASE_DIR = Path(__file__).resolve().parents[2]

CONFIG_DIR = BASE_DIR / "config"
FEEDS_DIR = CONFIG_DIR / "feeds"
