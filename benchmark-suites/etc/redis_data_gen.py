import redis
import random
import time
import json

r = redis.Redis(host='localhost', port=6379, db=0)

print("Generating realistic analytics data...")

# simulate realistic user analytics data
for i in range(1, 100000):
    user_id = f"user:{i}"
    data = {
        'age': random.randint(18, 80),
        'location': random.choice(['US', 'EU', 'ASIA', 'AFRICA', 'AUS']),
        'activity': random.randint(0, 1000),
        'premium': random.choice(['yes', 'no']),
        'timestamp': time.time()
    }
    r.hmset(user_id, data)

print("Data generation completed.")

