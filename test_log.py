import time
import sys

print("Test script started", flush=True)
for i in range(10):
    print(f"Log message {i}", flush=True)
    time.sleep(1)
