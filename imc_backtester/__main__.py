import sys

from .calibrate import main as calibrate_main
from .metrics import main as metrics_main
from .round3_csv_runner import main as round3csv_main
from .runner import main as runner_main
from options_backtester.runner import main as options_main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "calibrate":
        raise SystemExit(calibrate_main(argv[1:]))
    if argv and argv[0] == "metrics":
        raise SystemExit(metrics_main(argv[1:]))
    if argv and argv[0] == "round3csv":
        raise SystemExit(round3csv_main(argv[1:]))
    if argv and argv[0] in {"options", "vev", "round3"}:
        raise SystemExit(options_main(argv[1:]))

    raise SystemExit(runner_main(argv))
