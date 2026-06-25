import time
import argparse
import sys

# Try importing serial and verify it is the correct pyserial package
try:
    import serial
    # A quick check to confirm this is the real pyserial module
    if not hasattr(serial, 'Serial'):
        raise ImportError
except ImportError:
    print("[ERROR] The correct serial library is not installed.")
    print("Please install it by running:")
    print("    pip uninstall serial")
    print("    pip install pyserial")
    sys.exit(1)

# ==============================================================================
# CONFIGURATION VARIABLES
# Edit these values directly in the script to match your hardware configuration.
# ==============================================================================
PORT = "COM5"
BAUDRATE = 115200     # e.g., 9600 or 115200 (as per irat.c settings)
STOPBITS = 1          # Options: 1, 1.5, 2
TIMEOUT = 1.0         # Timeout in seconds for reading serial responses
# ==============================================================================

def parse_response(cmd: str, response: bytes) -> str:
    """Parses and decodes raw byte responses from irat.c based on the Meade command type."""
    if not response:
        return "No response received (this is normal for commands like :RG#, :RS#)."

    resp_str = response.decode('ascii', errors='replace').strip()
    
    # Handshake ACK (0x06)
    if cmd == "\x06":
        if resp_str == "G#":
            return "SUCCESS: Mount handshaked as Equatorial (G#)"
        return f"RESPONSE: {resp_str} (Expected 'G#')"

    # Rate / Speed Change Commands
    elif cmd in [":RG#", ":RC#", ":RM#", ":RS#"]:
        if resp_str == "1":
            return "SUCCESS: Drive speed / tracking relay pulse engaged (1)"
        return f"RESPONSE: {resp_str} (Expected '1')"

    # Slew Command
    elif cmd == ":MS#":
        if resp_str == "0":
            return "SUCCESS: Slew operation initiated successfully (0)"
        return f"RESPONSE: {resp_str} (Expected '0')"

    # Manual Jog Motion Commands & Stop Commands
    elif cmd in [":Me#", ":Mw#", ":Mn#", ":Ms#", ":Q#", ":Qn#", ":Qs#", ":Qw#", ":Qe#"]:
        if resp_str == "1":
            return "SUCCESS: Motor drive or stop action acknowledged (1)"
        return f"RESPONSE: {resp_str} (Expected '1')"

    # Coordinate Queries
    elif cmd == ":GR#":
        if resp_str.endswith('#'):
            return f"TELEMETRY: Right Ascension (RA) = {resp_str[:-1]}"
        return f"RA Raw response: {resp_str}"
        
    elif cmd == ":GD#":
        if resp_str.endswith('#'):
            clean_dec = resp_str[:-1].replace('\xdf', '°').replace('*', '°')
            return f"TELEMETRY: Declination (Dec) = {clean_dec}"
        return f"Dec Raw response: {resp_str}"

    elif cmd == ":GA#":
        if resp_str.endswith('#'):
            clean_alt = resp_str[:-1].replace('\xdf', '°').replace('*', '°')
            return f"TELEMETRY: Altitude/Elevation = {clean_alt}"
        return f"Altitude Raw response: {resp_str}"

    elif cmd == ":GZ#":
        if resp_str.endswith('#'):
            clean_az = resp_str[:-1].replace('\xdf', '°').replace('*', '°')
            return f"TELEMETRY: Azimuth = {clean_az}"
        return f"Azimuth Raw response: {resp_str}"

    # Sync/Calibration Commands
    elif cmd in [":CM#", ":Cm#"]:
        if resp_str.lower().startswith(("abc", "abc#")):
            return f"SUCCESS: Alignment sync acknowledged ({resp_str})"
        return f"RESPONSE: {resp_str}"

    return f"Raw response: {resp_str} (Hex: {response.hex()})"


def run_interactive_shell(port: str, baudrate: int, stopbits: float, timeout: float):
    # pyserial stopbits parameter accepts numeric values directly (1, 1.5, 2)
    # which avoids relying on the serial module's stopbits constants.
    sb = stopbits

    print("=========================================================")
    print("      T1P2 Telescope Serial Diagnostic Shell             ")
    print("=========================================================")
    print(f"Connecting to {port} ({baudrate} bps, 8-N-{stopbits})...")

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=sb,
            timeout=timeout
        ) as ser:
            print("Connected! Type commands or 'exit' / 'quit' to close connection.\n")
            print("Common commands:")
            print("  ACK      - Handshake link status test")
            print("  :RG#     - Turn Tracking ON (Fine Guide Rate)")
            print("  :RS#     - Turn Tracking OFF (Switch to Slew Speed)")
            print("  :GR#     - Query Right Ascension (RA)")
            print("  :GD#     - Query Declination (Dec)")
            print("---------------------------------------------------------")

            while True:
                try:
                    # Prompt user for input
                    user_input = input("\nLX200 command > ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nExiting diagnostic shell...")
                    break

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    print("Closing connection and exiting...")
                    break

                # Prepare the command
                if user_input.upper() == "ACK" or user_input == "0x06":
                    cmd_str = "\x06"
                    cmd_bytes = b"\x06"
                else:
                    cmd_str = user_input
                    if not cmd_str.startswith(':'):
                        cmd_str = ':' + cmd_str
                    if not cmd_str.endswith('#'):
                        cmd_str = cmd_str + '#'
                    cmd_bytes = cmd_str.encode('ascii')

                # Flush buffers to ensure clean communication
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Send command bytes
                ser.write(cmd_bytes)
                ser.flush()

                # Wait briefly for response
                time.sleep(0.25)

                # Read response
                response = b""
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)

                # Display the parsed result
                print(parse_response(cmd_str, response))

    except serial.SerialException as e:
        print(f"[ERROR] Failed to communicate over serial port: {e}")
        print("\nPossible causes:")
        print("1. The COM port is wrong. Double-check Device Manager to confirm the correct port.")
        print("2. The port is already open by Skychart or another telemetry tool. Close those programs first.")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Persistent Interactive Meade LX200 Serial Diagnostic Shell")
    parser.add_argument("--port", default=PORT, help=f"Windows serial port (default: {PORT})")
    parser.add_argument("--baud", type=int, default=BAUDRATE, help=f"Baud rate (default: {BAUDRATE})")
    parser.add_argument("--stopbits", type=float, choices=[1, 1.5, 2], default=STOPBITS, help=f"Stop bits (default: {STOPBITS})")
    parser.add_argument("--timeout", type=float, default=TIMEOUT, help=f"Timeout in seconds (default: {TIMEOUT})")
    
    args = parser.parse_args()
    
    run_interactive_shell(
        port=args.port,
        baudrate=args.baud,
        stopbits=args.stopbits,
        timeout=args.timeout
    )
