import redis
import random
import time

r = redis.Redis(host='localhost', port=6379, db=0)

queries = [
    lambda: r.keys('user:*'),                      # keys retrieval (moderate CPU)
    lambda: [r.hgetall(f"user:{random.randint(1,100000)}") for _ in range(1000)],  # batch fetch (high CPU)
    lambda: sum(int(r.hget(f"user:{random.randint(1,100000)}", 'activity') or 0) for _ in range(1000)),  # aggregation (very high CPU)
]

print("Running realistic analytics queries...")

while True:
    query = random.choice(queries)
    start = time.time()
    query()
    latency = time.time() - start
    print(f"Query latency: {latency:.4f} seconds")
    time.sleep(random.uniform(0.1, 1))  # realistic query intervals

