import time
import subprocess
import random
import multiprocessing

def run_single_ab_instance():
    """Runs a single instance of Apache Benchmark."""
    command = ["ab", "-n", "10000000", "-c", "30", "http://localhost/"]
    subprocess.run(command)
    # Short sleep to simulate fluctuation in requests
#    time.sleep(random.uniform(0.1, 0.5))

def run_apache_benchmark(duration, num_processes):
    """Runs multiple Apache Benchmark instances in parallel for a given duration."""
    start_time = time.time()
    processes = []
    
    while time.time() - start_time < duration:
        for _ in range(num_processes):
            p = multiprocessing.Process(target=run_single_ab_instance)
            p.start()
            processes.append(p)
        
        for p in processes:
            p.join()
        
        # Clear the list of processes
        processes = []

if __name__ == "__main__":
    duration = 600  # Duration in seconds
    num_processes = multiprocessing.cpu_count()  # Number of processes = number of CPU cores
    run_apache_benchmark(duration, num_processes)

