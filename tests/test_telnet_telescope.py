from telnetlib import Telnet
from time import sleep
import time
import threading
import queue
import numpy as np
from astropy.time import Time

from astropy.utils.iers import conf
conf.auto_max_age = None
# The desired url may change in the future
conf.iers_auto_url = 'ftp://cddis.gsfc.nasa.gov/pub/products/iers/finals2000A.all'
#conf.iers_auto_url = 'https://maia.usno.navy.mil/ser7/finals2000A.all'
conf.auto_download = False

log_file_update_time = time.time()

telnet_thread_lock_1 = threading.Lock()
telnet_thread_lock_2 = threading.Lock()
telnet_q= queue.Queue(maxsize=1)
def telnet_function(name):
    global telnet_thread_output,telnet_thread_input
    telnet_init = False
    telnet_data_present = False
    dome_status_update_time = time.time()
    def telnet_setup():
        HOST="172.16.20.221"
        tn = Telnet(HOST,"7280")
        k = tn.read_until(b"\r\n")
        print(k)
        tn.write(b"unalias tndata_target\r\n")
        k = tn.read_until(b"\r\n")
        print(k)
        tn.write(b"alias tndata_target targetra targetdec targetframe currentra currentdec\r\n")
        k = tn.read_until(b"\r\n")
        print(k)
        tn.write(b"monitor tndata_target interval=2000\r\n")
        return tn

    while True:
        try:
            if telnet_init == False:
                telnet_conn = telnet_setup()
                telnet_init = True
            else:
                k = b""
                k = telnet_conn.read_until(b"\r\n" , timeout = 5)
                if k != b"":
                    telnet_data_present = True
                else:
                    telnet_data_present = False
                raw_string = k.decode("utf-8")
                if len(raw_string.split(" ")) < 3:
                    telnet_init = False                  
                
        except Exception as e:
            telnet_init = False
        else:
            if telnet_data_present == True:
               # print(raw_string)
                t_data = raw_string.split(" ")
                if len(t_data) > 7:
                    print(f'TARGET RA [DEG]:{float(t_data[3])*15}        TARGET DEC [DEG]:{t_data[4]}        CURRENT RA [DEG]:{float(t_data[6])*15}        CURRENT DEC [DEG]:{t_data[7]}')

        finally:
            pass


telnet_thread = threading.Thread(target=telnet_function, args=(2,), daemon=True)
telnet_thread.start()
telnet_data = ""
while True:
    pass