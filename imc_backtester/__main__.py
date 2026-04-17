import sys

from .metrics import main as metrics_main
from .runner import main as runner_main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "metrics":
        raise SystemExit(metrics_main(argv[1:]))

    raise SystemExit(runner_main(argv))
