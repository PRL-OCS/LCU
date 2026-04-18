from telnetlib import Telnet
from time import sleep
import time
import threading
import queue

# Removed astropy/numpy imports for brevity, keep them in your actual script

telnet_q = queue.Queue() # Using the queue for thread communication

def telnet_function(name):
    telnet_init = False
    
    def telnet_setup():
        HOST = "172.16.20.221"
        tn = Telnet(HOST, "7281")
        print(tn.read_until(b"\r\n").decode('utf-8', errors='ignore'))
        
        tn.write(b"unalias tndata_target\r\n")
        print(tn.read_until(b"\r\n").decode('utf-8', errors='ignore'))
        
        tn.write(b"alias tndata_target targetra targetdec targetframe currentra currentdec\r\n")
        print(tn.read_until(b"\r\n").decode('utf-8', errors='ignore'))
        
        tn.write(b"monitor tndata_target interval=2000\r\n")
        return tn

    while True:
        try:
            if not telnet_init:
                telnet_conn = telnet_setup()
                telnet_init = True
            else:
                # 1. CHECK FOR NEW COMMANDS FROM MAIN THREAD
                try:
                    # get_nowait() checks the queue without pausing the loop
                    new_command = telnet_q.get_nowait() 
                    cmd_bytes = new_command.encode("utf-8") + b"\r\n"
                    telnet_conn.write(cmd_bytes)
                    print(f">>> Sent custom command: {new_command}")
                except queue.Empty:
                    pass # Queue is empty, just carry on

                # 2. READ INCOMING DATA
                # Lowered timeout to 1 second so it checks the queue more frequently
                k = telnet_conn.read_until(b"\r\n", timeout=1) 
                
                if k != b"":
                    raw_string = k.decode("utf-8").strip()
                    t_data = raw_string.split(" ")
                    
                    if len(t_data) > 7:
                        try:
                            # Added basic try/except here in case the split data isn't a float
                            print(f'TARGET RA [DEG]:{float(t_data[3])*15}        TARGET DEC [DEG]:{t_data[4]}        CURRENT RA [DEG]:{float(t_data[6])*15}        CURRENT DEC [DEG]:{t_data[7]}')
                        except ValueError:
                            pass 

        except Exception as e:
            print(f"Telnet Error: {e}")
            telnet_init = False
            time.sleep(2) # Pause briefly before attempting to reconnect

# Start the background thread
telnet_thread = threading.Thread(target=telnet_function, args=(2,), daemon=True)
telnet_thread.start()

# --- MAIN THREAD ---
# Instead of `pass`, we now take user input and feed it to the thread!
print("Type a command and press Enter to send it to the Telnet server.")
print("Type 'quit' or 'exit' to stop the script.\n")

while True:
    try:
        user_input = input()
        if user_input.lower() in ['quit', 'exit']:
            break
        if user_input.strip():
            telnet_q.put(user_input) # Put the command in the queue!
    except KeyboardInterrupt:
        break