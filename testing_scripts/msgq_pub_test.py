# random_carstate_pub.py
import cereal.messaging as messaging
import time
import random

def random_carstate():
    msg = messaging.new_message("carState")
    cs = msg.carState
    # cs.enabled = True
    cs.leftBlinker = True
    cs.rightBlinker=False
    cs.vEgo=12.34
    return msg

def main():
    # Publisher: binds to 0.0.0.0 for external access (Docker to Host)
    pub_sock = messaging.pub_sock("carState")#, addr="tcp://0.0.0.0:8001")
    
    while True:
        msg = random_carstate()
        pub_sock.send(msg.to_bytes())
        print(f"[Published]")
        time.sleep(0.1)

if __name__ == "__main__":
    main()
