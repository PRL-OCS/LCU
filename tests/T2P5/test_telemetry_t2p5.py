import os
import sys
import time
import argparse

# Add project root to Python path
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )
)

from Plugins.telescope.T2P5.telescope_telemetry import TelescopeTelemetry


# Optional command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="172.16.20.221")
parser.add_argument("--port", type=int, default=7280)
args = parser.parse_args()


def main():
    telemetry = TelescopeTelemetry(
        host=args.host,
        port=args.port,
    )

    print("Starting telemetry...")
    telemetry.start()

    try:
        print("Waiting for first telemetry packet...")
        if telemetry.first_fetch_event.wait(timeout=30):
            print("Connected successfully.\n")
        else:
            print("Timed out waiting for telemetry.\n")

        while True:
            data = telemetry.get_telemetry()

            print("-" * 60)
            print(f"Current RA : {data['ra']:.6f}°")
            print(f"Current Dec: {data['dec']:.6f}°")
            print(f"Target RA  : {data['target_ra']:.6f}°")
            print(f"Target Dec : {data['target_dec']:.6f}°")
            print(f"Slewing    : {data['slewing']}")
            print(f"Tracking   : {data['tracking']}")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping telemetry...")

    finally:
        telemetry.stop()


if __name__ == "__main__":
    main()