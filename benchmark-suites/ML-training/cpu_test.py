import multiprocessing
import time

def cpu_intensive_task(_):
    start_time = time.time()
    iterations = 0
    while time.time() - start_time < 100000:  # Run for 10 seconds
        # Perform a simple computation
        a, b = 0, 1
        for _ in range(1000):
            a, b = b, a + b
        iterations += 1
    return iterations

if __name__ == '__main__':
    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    results = pool.map_async(cpu_intensive_task, range(multiprocessing.cpu_count()))
    pool.close()
    pool.join()

    total_iterations = sum(results.get())
    print(f"Total iterations: {total_iterations}")

