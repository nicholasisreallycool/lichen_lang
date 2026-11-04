import sys

def main():
    args = sys.argv[1:]
    if not args:
        print("lichen 0.1.0 (REPL coming soon)")
    else:
        print(f"Would run: {args[0]}")
