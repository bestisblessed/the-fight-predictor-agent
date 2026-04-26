import os
import sys


PROJECT_DIR = "/home/bestisblessed/the-fight-predictor-agent/OPTIMIZED-PYTHONANYWHERE"

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ["OPTIMIZED_DISABLE_INPROCESS_WORKER"] = "1"

from app import create_app


application = create_app(start_worker=False)
