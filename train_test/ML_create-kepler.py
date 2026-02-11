import pandas as pd
import numpy as np
import os
from joblib import dump

from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor

# 1. Optimized Data Loading
# Peek at header to map indices to names
header = pd.read_csv('../data/training-data.csv', nrows=0)

with open('../estimation/topol_metric_size.dat', 'r') as file:
    values = file.read().split()
    perf_metric_index = int(values[1])

selected_indices = {perf_metric_index+3, perf_metric_index+4, perf_metric_index+5, perf_metric_index+6}
pca_columns = [header.columns[i] for i in selected_indices if header.columns[i] != 'label']

# Load only required columns to save memory
data = pd.read_csv('../data/training-data.csv', usecols=pca_columns + ['label'])

# Split data
train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)

# Handle NaNs (Required for standard GradientBoostingRegressor)
train_data[pca_columns] = train_data[pca_columns].fillna(train_data[pca_columns].mean())
train_data['label'] = train_data['label'].fillna(train_data['label'].median())

features_train = train_data[pca_columns]
labels_train = train_data['label']

features_test = test_data[pca_columns].fillna(train_data[pca_columns].mean())
labels_test = test_data['label'].fillna(train_data['label'].median())

os.makedirs("../MLs", exist_ok=True)

# 2. Define Model and Hyperparameters
models = {
    'GradientBoosting': (GradientBoostingRegressor(), {
        'n_estimators': [100, 300],        # Increased for better fit
        'learning_rate': [0.1, 0.5], 
        'max_depth': [1, 5],              # Deep trees to overfit the specific sample
    })
}

def perform_grid_search_safe(model, param_grid, features, labels):
    try:
        grid_search = GridSearchCV(
            estimator=model, 
            param_grid=param_grid, 
            scoring='neg_mean_squared_error', 
            cv=5, 
            n_jobs=-1,
        )
        grid_search.fit(features, labels)
        return grid_search.best_estimator_, grid_search.best_params_
    except Exception as e:
        print(f"Failed to fit model {model} with error: {str(e)}")
        return None, None

# 3. Evaluation Loop (Original Format Preserved)
for model_name, (model, param_grid) in models.items():
    best_model, best_params = perform_grid_search_safe(model, param_grid, features_train, labels_train)

    if best_model is None:
        continue

    labels_pred = best_model.predict(features_test)
    dump(best_model, f'../MLs/{model_name}_model-kepler.joblib')

    errors = np.abs(labels_test - labels_pred)
    mse = mean_squared_error(labels_test, labels_pred)
    mae = mean_absolute_error(labels_test, labels_pred)
    std_dev_mae = np.std(errors)

    percentage_errors = (errors / labels_test) * 100
    mean_percentage_error = np.mean(percentage_errors)
    std_dev_percentage_error = np.std(percentage_errors)

    average_ground_truth = np.mean(labels_test)
    average_error_percentage = (np.mean(errors) / average_ground_truth) * 100

    print(f"Model: {model_name}")
    print(f"Best Configuration: {best_params}")
    print(f"Test Set Mean Squared Error: {mse:.2f}")
    print(f"Test Set Mean Absolute Error: {mae:.2f}")
    print(f"Standard Deviation of Mean Absolute Error: {std_dev_mae:.2f}")
    print(f"Mean Percentage of Absolute Difference: {mean_percentage_error:.2f}%")
    print(f"Standard Deviation of Mean Percentage of Absolute Difference: {std_dev_percentage_error:.2f}%")
    print(f"Simple Average Error Percentage (Relative to Average Ground Truth): {average_error_percentage:.2f}%")

