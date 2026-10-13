"""Run Giana Lex locally without a login screen for an explicit testing session."""
import argparse

from app import app
from local_testing import enable_local_testing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    enable_local_testing(app)
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
