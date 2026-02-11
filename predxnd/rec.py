import socket
import json

HOST = "0.0.0.0"   # listen on all interfaces
PORT = 9999

def handle_connection(conn, addr):
    """Read lines until the client closes; parse each as JSON."""
    with conn:
        buf = ""
        while True:
            data = conn.recv(4096).decode("utf-8")
            if not data:
                break
            buf += data
            # Process complete lines only
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[{addr}] Received invalid JSON: {line!r}")
                    continue

                # Extract fields
                num = payload.get("num_cores")
                cpupower = payload.get("cpupower_fields", [])
                perf = payload.get("perf_counts", [])
                temps = payload.get("temperatures", [])

                # Print the actual data arrays
                print(f"[{addr}] num_cores = {num}")
                print(f"[{addr}] cpupower_fields = {cpupower}")
                print(f"[{addr}] perf_counts      = {perf}")
                print(f"[{addr}] temperatures     = {temps}")
                print()  # blank line for readability

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, PORT))
        listener.listen()
        print(f"Listening on {HOST}:{PORT} (awaiting monitor client)...")
        while True:
            conn, addr = listener.accept()
            print(f"Connection from {addr}")
            handle_connection(conn, addr)
            print(f"Disconnected {addr}")

if __name__ == "__main__":
    main()

