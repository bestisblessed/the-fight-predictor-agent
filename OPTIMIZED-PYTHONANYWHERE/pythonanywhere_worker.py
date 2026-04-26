import argparse
import json

from settings import Config
from service import FightAgentRuntime, build_runtime_bundle, run_checkpoint_worker, run_worker_forever


def main() -> None:
    parser = argparse.ArgumentParser(description="Always-on task worker for PythonAnywhere")
    parser.add_argument("--once", action="store_true", help="Process new inbox records once and exit")
    parser.add_argument("--sleep-seconds", type=float, default=2.0, help="Poll interval for forever mode")
    args = parser.parse_args()

    config = Config.from_env()
    config.require_runtime()
    runtime = FightAgentRuntime(build_runtime_bundle(config), start_worker=False)

    if args.once:
        processed = run_checkpoint_worker(runtime)
        print(json.dumps({"processed_records": processed}, indent=2), flush=True)
        return

    run_worker_forever(runtime, sleep_seconds=args.sleep_seconds)


if __name__ == "__main__":
    main()
