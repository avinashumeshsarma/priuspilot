import zmq
import capnp
import time

# Load Cap'n Proto schema
capnp.remove_import_hook()
# log = capnp.load('/home/avinashumeshsarma/openpilot/cereal/log.capnp')
log = capnp.load('/home/carpc/Software/saurabh/priuspilot/cereal/log.capnp')

services = ["carState", "carControl", "pandaStates"]

def fnv1a_hash(s):
    h = 0xcbf29ce484222325
    for c in s:
        h ^= ord(c)
        h *= 0x100000001b3
        h &= 0xFFFFFFFFFFFFFFFF
    return h

def get_port(service):
    return 8023 + (fnv1a_hash(service) % (65535 - 8023))

context = zmq.Context()
sockets = {}

for service in services:
    port = get_port(service)
    sock = context.socket(zmq.SUB)
    sock.connect(f"tcp://127.0.0.1:{port}")
    sock.setsockopt_string(zmq.SUBSCRIBE, "")
    sockets[service] = sock
    print(f"Connected to {service} on port {port}")

poller = zmq.Poller()
for sock in sockets.values():
    poller.register(sock, zmq.POLLIN)

while True:
    for service, sock in sockets.items():
        try:
            if sock in dict(poller.poll(100)):
                msg = sock.recv()
                with log.Event.from_bytes(msg) as evt:
                    pass

                if service == "carState":
                    try:
                        if evt.which()==service:
                            cs = getattr(evt,service)
                            print(f"[carState] Speed: {cs.vEgo:.2f}, Angle: {cs.steeringAngleDeg:.2f}")
                    except Exception as e:
                        print(f"[carState] Error: {e}")

                elif service == "carControl":
                    try:
                        cc = evt.carControl
                        print(f"[carControl] Steer: {cc.actuators.steeringAngleDeg:.2f}, Accel: {cc.actuators.accel:.2f}")
                    except Exception as e:
                        print(f"[carControl] Error: {e}")

                elif service == "pandaStates":
                    try:
                        if len(evt.pandaStates) > 0:
                            ps = evt.pandaStates[0]
                            print(f"[pandaStates] Voltage: {ps.voltage}")
                    except Exception as e:
                        print(f"[pandaStates] Error: {e}")

        except Exception as e:
            print(f"[{service}] Socket error: {e}")
    time.sleep(0.01)
