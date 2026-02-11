#!/usr/bin/env python3
import sys

def read_values(path):
    text = open(path, 'r').read().strip()
    if text.startswith('[') and text.endswith(']'):
        text = text[1:-1]
    parts = [p.strip() for p in text.split(',') if p.strip()]
    return [float(p) for p in parts]

def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} remote.dat local.dat")

    remote = read_values(sys.argv[1])
    local  = read_values(sys.argv[2])

    if len(remote) != len(local):
        sys.exit(f"Error: value counts differ ({len(remote)} vs {len(local)})")

    for i, (r, l) in enumerate(zip(remote, local)):
        if l != 0:
            diff = abs(r - l) / l * 100
            print(f"[{i:3d}] remote={r}, local={l}, diff={diff:.2f}%")
        else:
            print(f"[{i:3d}] remote={r}, local={l}, diff=undefined (local=0)")

if __name__ == '__main__':
    main()

