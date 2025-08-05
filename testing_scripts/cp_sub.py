# random_carstate_sub.py
import cereal.messaging as messaging

def main():
    # Subscriber: connects to publisher's TCP port
    sub_sock = messaging.sub_sock("carParams")#, addr="tcp://127.0.0.1:8001")
    
    while True:
        msg = messaging.recv_one_or_none(sub_sock)
        if msg is not None:
            #print(f"[Subscriber] Received vEgo: {msg.carState.vEgo:.2f} m/s, steering: {msg.carState.steeringAngleDeg:.2f}°")
            print(msg.carParams)

if __name__ == "__main__":
    main()
