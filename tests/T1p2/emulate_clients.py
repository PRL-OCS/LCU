import serial
import socket
import threading
import time
import sys

# Configurations
SKYCHART_PORT = "COM10"  # Connected to COM11 (Proxy) via VSPE
PROXY_TCP_HOST = "127.0.0.1"
PROXY_TCP_PORT = 5001

# Global flag to control execution lifetime
running = True

def run_skychart_emulation():
    print("[Skychart Thread] Attempting to connect to virtual serial port COM10...")
    try:
        with serial.Serial(
            port=SKYCHART_PORT,
            baudrate=115200,
            timeout=1.0
        ) as ser:
            print("[Skychart Thread] Connected to COM10! Constantly querying coordinates...")
            
            # Flush buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            toggle = True
            while running:
                # Alternate between Right Ascension (:GR#) and Declination (:GD#) queries
                cmd = b":GR#" if toggle else b":GD#"
                toggle = not toggle
                
                try:
                    ser.write(cmd)
                    ser.flush()
                    
                    # Read response until '#'
                    response = bytearray()
                    start_time = time.time()
                    while time.time() - start_time < 0.5:
                        if ser.in_waiting > 0:
                            char = ser.read(1)
                            if not char:
                                break
                            response.extend(char)
                            if char == b'#':
                                break
                        else:
                            time.sleep(0.01)
                    
                    # Print coordinates in one line to prevent console flood
                    sys.stdout.write(f"\r[Skychart Thread] Polled {cmd.decode()} -> Received: {response.decode(errors='replace'):<15}")
                    sys.stdout.flush()
                    
                except Exception as ex:
                    print(f"\n[Skychart Thread ERROR] Serial transmission error: {ex}")
                    break
                
                # Constant polling: query 5 times a second
                time.sleep(0.2)
                
            print("\n[Skychart Thread] Thread finished.")
            
    except serial.SerialException as e:
        print(f"[Skychart Thread ERROR] Failed to access COM10: {e}")
        print("Please ensure VSPE is running and the COM10 <-> COM11 pair is created.")

def run_lcu_emulation():
    print("[LCU Thread] Started. Will inject a tracking command every 5 seconds...")
    # Give Skychart thread a headstart to show constant polling first
    time.sleep(1.0)
    
    # Alternate between Enable (:RG#) and Disable (:RS#)
    is_tracking_enabled = True
    
    while running:
        cmd = b":RG#" if is_tracking_enabled else b":RS#"
        action_name = "Enable Tracking" if is_tracking_enabled else "Disable Tracking"
        is_tracking_enabled = not is_tracking_enabled
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((PROXY_TCP_HOST, PROXY_TCP_PORT))
                
                # Carriage return print to avoid overlapping with Skychart's active polling
                print(f"\n[LCU Thread] Injecting: {action_name} ({cmd.decode()})")
                s.sendall(cmd)
                
                # Read response
                response = s.recv(1024)
                print(f"[LCU Thread] Response received: {response.decode(errors='replace')}")
                
        except Exception as e:
            print(f"\n[LCU Thread ERROR] TCP connection error: {e}")
            
        # Wait 5 seconds before sending the next command
        for _ in range(50):
            if not running:
                break
            time.sleep(0.1)
            
    print("[LCU Thread] Thread finished.")

if __name__ == "__main__":
    print("=========================================================")
    print("        T1P2 Dual Client Serial Sharing Emulator         ")
    print("=========================================================")
    print(f"Skychart Virtual Port: {SKYCHART_PORT}")
    print(f"LCU Proxy Address:     {PROXY_TCP_HOST}:{PROXY_TCP_PORT}")
    print("Testing for 20 seconds. Press Ctrl+C to terminate early.")
    print("---------------------------------------------------------")
    
    # Create client threads
    t_skychart = threading.Thread(target=run_skychart_emulation, daemon=True)
    t_lcu = threading.Thread(target=run_lcu_emulation, daemon=True)
    
    # Start threads
    t_skychart.start()
    t_lcu.start()
    
    # Let it run for 20 seconds
    try:
        run_duration = 20.0
        start_time = time.time()
        while time.time() - start_time < run_duration:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nTermination requested by user.")
    finally:
        running = False
        time.sleep(0.5)
        
    print("\n---------------------------------------------------------")
    print("Emulation script finished.")
    print("=========================================================")
