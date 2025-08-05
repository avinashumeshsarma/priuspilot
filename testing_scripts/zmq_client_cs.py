import zmq
import capnp

# Load schema
capnp.remove_import_hook()
log = capnp.load("/home/avinashumeshsarma/openpilot/cereal/log.capnp")

# Service name
service = "carState"

# Port hashing
def fnv1a_hash(s):
    h = 0xcbf29ce484222325
    for c in s:
        h ^= ord(c)
        h *= 0x100000001b3
        h &= 0xffffffffffffffff
    return h

port = 8023 + (fnv1a_hash(service) % (65535 - 8023))

# ZMQ setup
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect(f"tcp://127.0.0.1:{port}")
sock.setsockopt_string(zmq.SUBSCRIBE, "")
sock.RCVTIMEO = 5000

print(f"The port for {service} is {port}")

# The port for carState is 9041
# The port for carControl is 63225



# Listen loop
while True:
    try:
        msg = sock.recv()
        try:
            with log.Event.from_bytes_packed(msg) as evt:
                pass
        except Exception:
            with log.Event.from_bytes(msg) as evt:
                print("Which one") ##This got printed
                pass

        if evt.which() == service:
            cs = getattr(evt, service)
            print(f"vEgo: {cs.vEgo:.2f} m/s, steer: {cs.steeringAngleDeg:.2f}°")

    except Exception:
        continue
