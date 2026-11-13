import time
from datetime import datetime

from database import initialize_database
from agent import run_betsy


CHECK_INTERVAL_SECONDS = 10


def main():
    initialize_database()

    print("=" * 60)
    print("BETSY AUTONOMOUS PROCUREMENT AGENT")
    print("=" * 60)

    print(
        f"Monitoring inventory every "
        f"{CHECK_INTERVAL_SECONDS} seconds."
    )

    print("Press Ctrl+C to stop Betsy.\n")

    while True:
        try:
            result = run_betsy()

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            status = result.get(
                "status",
                "UNKNOWN"
            )

            message = result.get(
                "message",
                "Monitoring cycle completed."
            )

            print(
                f"[{timestamp}] {status}"
            )

            print(
                f"{message}\n"
            )

            time.sleep(
                CHECK_INTERVAL_SECONDS
            )

        except KeyboardInterrupt:
            print(
                "\nBetsy monitoring stopped."
            )

            break

        except Exception as error:
            print(
                f"\nBetsy encountered an error: {error}"
            )

            time.sleep(
                CHECK_INTERVAL_SECONDS
            )


if __name__ == "__main__":
    main()

