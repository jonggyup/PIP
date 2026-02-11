import multiprocessing
import time

def cpu_and_cache_intensive_task(_):
    start_time = time.time()
    iterations = 0
    large_list = [0] * 1000000  # Create a large list to stress the cache
    while time.time() - start_time < 30:  # Run for 10 seconds
        # Perform computations and memory access
        for i in range(len(large_list)):
            large_list[i] += 1
        iterations += 1
    return iterations

if __name__ == '__main__':
    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    results = pool.map_async(cpu_and_cache_intensive_task, range(multiprocessing.cpu_count()))
    pool.close()
    pool.join()

    total_iterations = sum(results.get())
    print(f"Total iterations: {total_iterations}")

