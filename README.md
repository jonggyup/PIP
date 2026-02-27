# PIP: Prediction-Informed Power Management for General-Purpose Compute Servers

This artifact provides the source code and a complete experimental framework for PIP (Prediction-Informed Power), a novel power management system presented in the EuroSys'26 paper "Prediction-Informed Power Management for General-Purpose Compute Servers" (Paper ID: 743).

This document provides a complete guide to reproducing the results, including system setup, model training, running experiments, and plotting figures.

## Evaluation Environment

The evaluation for this paper was performed on the **CloudLab Clemson cluster**, using the **`c6420` server type**. It is **highly recommended to use an identical type of machine** to ensure faithful reproduction of the results. If you do not have access to the CloudLab Clemson cluster, please feel free to reach out to the authors for assistance.

---

## How to Reproduce the Results: A 3-Phase Workflow

The entire process, from a fresh machine to the final plots, is broken down into three phases.
Running the following command performs all 3-phase workflow automatically, making it easy to reproduce the results and creates the figures in './plots'.

```bash
sudo su
./artifact.sh
```

### Phase 1: Full System Setup and Model Training

This crucial first phase prepares the entire environment from scratch. It installs dependencies, configures the system, collects fresh training data by stress-testing the CPU, and trains the power models.

**Action:**
Run the master setup script. This process is fully automated but can take a significant amount of time (est. 1-2 hours).

```bash
sudo ./setting.sh
```

**For a detailed explanation of this process, see "Deep Dive: The Model Training Process" below.**

### Phase 2: Run Evaluation Experiments

This phase uses the environment and models prepared in Phase 1 to run the three main experiments that validate the paper's claims. **It is recommended to run each experiment in a separate, clean shell.**

-   **Experiment 1: Power Estimation Accuracy (Table 2)**
    -   Validates the accuracy of the newly trained power model against baselines.
    -   Estimated time: ~30 minutes.
    -   ```bash
        sudo ./run-bench-estimation.sh
        ```
    -   Results are stored in `results-comp/`.

-   **Experiment 2: Oversubscription Performance (Figure 3 and 4)**
    -   Evaluates PIP's performance under power oversubscription.
    -   Estimated time: ~30 hours.
    -   ```bash
        sudo ./run-bench-oversubscription.sh
        ```
    -   Results are stored in `results-oversub-fluc/`.

-   **Experiment 3: Colocation Performance (Figures 7)**
    -   Evaluates PIP's priority-aware control with co-located workloads.
    -   Estimated time: ~3 hours.
    -   ```bash
        sudo ./run-bench-colocation.sh
        ```
    -   Results are stored in `results-qos-cap/`.

**For a detailed explanation of what these scripts do, see "Deep Dive: The Evaluation Experiments" below.**

### Phase 3: Generate Plots and Tables

This final phase generates the figures and tables from the raw data produced in Phase 2.

**Action:**
Run the plotting scripts corresponding to the experiments you ran. The output plots will be saved in the `plots/` directory.

-   To generate the data for **Table 2**: `python3 plot_table2.py`
-   To generate **Figure 3**: `python3 plot_figure3.py`
-   To generate **Figures 4 & 7**: `python3 plot_figure4.py` and `python3 plot_figure7.py`

---

## Major Code Components

The core of the evaluation lies in comparing two power control systems, both located in the `control/` directory.

### 1. PIP Controller (`control/powercap_CPU_powertrace-final.py`)

This is the implementation of our paper's proposed system, PIP. It is a **predictive** controller that works as follows:
-   **ML-based Prediction**: It uses the pre-trained CatBoost model (`MLs/CatBoost_model.joblib`) to predict the power consumption of a given CPU configuration *before* applying it.
-   **Proactive Control**: When the power budget changes or is violated, PIP uses the model to simulate the outcome of different throttling levels (adjusting CPU bandwidth via the cgroup `cpu.max` file). It then chooses the optimal configuration that maximizes performance while staying within the budget.
-   **Priority-Aware**: It distinguishes between a `critical` (high-priority) and a `user` (low-priority) cgroup, prioritizing the `critical` group during both throttling and recovery phases.
-   **Online Calibration**: It includes a calibration mechanism that continuously adjusts for prediction errors based on the difference between predicted and actual measured power.

### 2. Thunderbolt Controller (`control/powercap_CPU_google-ALL-v1.2.py`)

This script is our implementation of the Google Thunderbolt system, which serves as the primary baseline for comparison. It is a **reactive** controller based on the RUMD (Randomized Unthrottling / Multiplicative Decrease) algorithm.
-   **Reactive Throttling**: It does not predict the outcome of its actions. Instead, it reacts to measured power.
    -   If power exceeds a high threshold (98% of budget), it applies a drastic **multiplicative decrease** to the CPU throttle (e.g., `throttle *= 0.01`).
    -   If power is between a low (96%) and high (98%) threshold, it applies a gentler multiplicative decrease (e.g., `throttle *= 0.75`).
-   **Randomized Recovery**: When power is below the budget, it waits for a **randomized period** of time (1-10 seconds) before incrementally increasing the CPU throttle by a fixed step (5%). This slower, reactive recovery is a key difference from PIP's proactive approach.
-   **Priority**: Like our PIP implementation, it throttles the `user` cgroup before the `critical` cgroup.

---

## Benchmark Descriptions

All benchmarks are located in the `benchmark-suites/` directory. They are categorized as either User-Facing (latency-sensitive) or Best-Effort (throughput-oriented).

### User-Facing (UF) Benchmarks
-   **Social Network**: A broadcast-style social network service from DeathStarBench, composed of 36 microservices.
    -   *Location:* `benchmark-suites/DeathStarBench/socialNetwork/`
-   **Hotel Reservation**: A microservice application with 17 services that simulates a hotel booking system, also from DeathStarBench.
    -   *Location:* `benchmark-suites/DeathStarBench/hotelReservation/`
-   **CNN Inference (`cnninf`)**: An online object detection application using a pre-trained CNN model.
    -   *Location:* `benchmark-suites/etc/cnninf.py`
-   **Fileserver**: An in-memory file server workload from Filebench that handles metadata and small I/O operations.
    -   *Location:* `benchmark-suites/filebench/`

### Best-Effort (BE) Benchmarks
-   **BERT Training (`bert`)**: A PyTorch/Transformers implementation for fine-tuning a BERT-base model on the IMDB dataset.
    -   *Location:* `benchmark-suites/ML-training/bert.py`
-   **CNN Training (`cnn`)**: A PyTorch script for training a CNN model on the CIFAR-10 dataset.
    -   *Location:* `benchmark-suites/ML-training/cnn.py`
-   **ML Preprocessing (`tfidfvec`)**: A CPU-heavy batch job that performs a TF-IDF text-to-vector transformation on a dataset.
    -   *Location:* `benchmark-suites/ML-training/tfidfvec.py`

---

## Deep Dive: The Model Training Process (`setting.sh`)

The `setting.sh` script automates a comprehensive workflow to generate a robust power model tailored to your specific hardware.

#### Step 1: System Stressing & Data Collection
-   **Orchestrator:** `scripts/collect_data.sh`
-   **Logger:** `train_test/feature_extract.py` (runs in the background)
-   **Workload Generators:** `scripts/stressor.sh`, `scripts/cgroup_possible_runs.py`, `scripts/ctl_test.sh`

The process begins by launching the `feature_extract.py` logger, which samples a wide range of system metrics (CPU C/P-states, performance counters via `perf`) and the ground-truth CPU power (via RAPL) every second, writing each snapshot as a row to `data/training-data.csv`.

While the logger runs, the orchestrator executes a multi-stage stress-testing routine to generate diverse system states:
1.  **Workload Diversity (`stressor.sh`):** This script runs hundreds of `stress-ng` configurations, varying the type of stress (CPU, memory, I/O), the number of threads, and the CPU topology (e.g., packing threads onto one core vs. spreading them out).
2.  **Resource Constraint Diversity (`cgroup_possible_runs.py`):** A heavy `stress-ng` workload is started, and this script systematically sweeps through different resource constraints by iterating through all possible numbers of active cores (`cpuset`) and all possible CPU bandwidth limits (`cpu.max`).
3.  **Co-location Diversity (`ctl_test.sh`):** Two `stress-ng` workloads are run concurrently on different CPU sockets. A script then iterates through all combinations of CPU bandwidth limits for both workloads.

#### Step 2: Model Training & Hyperparameter Tuning
-   **Script:** `train_test/ML_create.py`

Once the `training-data.csv` is generated, this script trains the power model:
1.  **Data Loading:** It loads the collected dataset.
2.  **Train/Test Split:** The data is split into an 80% training set and a 20% test set.
3.  **Hyperparameter Tuning:** It uses `GridSearchCV` from scikit-learn to perform a 5-fold cross-validation search for the best hyperparameters for the `CatBoostRegressor` model (testing different `iterations`, `learning_rate`, `depth`, etc.).
4.  **Final Training & Saving:** The CatBoost model is trained using the best parameters found, and the final model object is saved to `MLs/CatBoost_model.joblib`. This is the model used by the PIP controller in the evaluation experiments.

---

## Deep Dive: The Evaluation Experiments

The three main evaluation scripts orchestrate the benchmarks and the power controllers.

#### Experiment 1: `run-bench-estimation.sh`
This script iterates through the evaluation benchmarks (Filebench, Hotel Reservation, etc.). For each benchmark, it does two things in parallel:
1.  **Runs the benchmark application.**
2.  **Runs `estimation/estimate_CPU_power-compare-all.py` in the background.** This script continuously:
    -   Collects the same system metrics used for training.
    -   Uses the newly trained PIP model (`CatBoost_model.joblib`) to predict power.
    -   Uses the baseline Kepler (`GradientBoosting_model-kepler.joblib`) and PowerAPI (`Ridge_model-powerapi.joblib`) models to predict power.
    -   Measures the true power via RAPL.
    -   Logs all predictions and the true power to a `.dat` file in `results-comp/`.

#### Experiments 2 & 3: `run-bench-oversubscription.sh` & `run-bench-colocation.sh`
These scripts run the benchmarks under the control of the two power management systems to compare their performance. For each scenario, the script will:
1.  Set a specific power budget by writing to `control/budget`.
2.  Launch the benchmark workload(s).
3.  Launch one of the two controller scripts to manage the power:
    -   **For PIP:** It runs `control/powercap_CPU_powertrace-final.py`.
    -   **For the baseline:** It runs `control/powercap_CPU_google-ALL-v1.2.py`.
4.  The benchmark's performance and the controller's power logs are saved to the respective `results-oversub-fluc/` or `results-qos-cap/` directory.

## Helper Scripts
-   `artifact.sh`: A master script that performs all three phases in sequence: setup, evaluation, and plotting.
-   `setting.sh`: A setup script that installs necessary packages, collect traning data, and builds power models (Phase 1 only).
-   `run-bench-all.sh`: Runs only the three evaluation experiments (Phase 2 only).
-   `plot_all.sh`: Plots all graphs and saves them in `./plots` (Phase 3 only).
-   `./scripts/check_system.sh`: Verifies that your environment meets all critical requirements.
-   `./scripts/get_system_info.sh`: Gathers detailed system information into a log file for debugging.
-   `./scripts/show_versions.sh`: Displays the versions of all critical software components.

## Zenodo link
https://zenodo.org/records/18804291
