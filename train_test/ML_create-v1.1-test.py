##### This version is updated version via ChatGPT suggestions. I didn't verify the effectiveness yet. #####

import pandas as pd
import numpy as np
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error
from catboost import CatBoostRegressor, Pool
from joblib import dump
import os

# Load training and test data
train_data = pd.read_csv('../data/training-data.csv')
test_data = pd.read_csv('../data/test-data.csv')

# Define the feature columns
pca_columns = [col for col in train_data.columns if col != 'label']

# Check for NaNs and handle them in training data
if train_data[pca_columns].isnull().any().any() or train_data['label'].isnull().any():
    train_data[pca_columns] = train_data[pca_columns].fillna(train_data[pca_columns].mean())
    train_data['label'] = train_data['label'].fillna(train_data['label'].median())

# Prepare training data
features_train = train_data[pca_columns]
labels_train = train_data['label']

# Prepare test data (fill NaNs using training data statistics)
features_test = test_data[pca_columns].fillna(train_data[pca_columns].mean())
labels_test = test_data['label'].fillna(train_data['label'].median())

# Address imbalance by applying sample weighting (heavier weight to low-load samples)
threshold_low = labels_train.quantile(0.25)  # Adjust quantile threshold as needed
sample_weights = np.where(labels_train <= threshold_low, 3.0, 1.0)  # 3x weight to low-load

# Prepare CatBoost pool
train_pool = Pool(features_train, labels_train, weight=sample_weights)

os.makedirs("../MLs", exist_ok=True)


# Prepare CatBoost pool
train_pool = Pool(features_train, labels_train, weight=sample_weights)

os.makedirs("../MLs", exist_ok=True)

models = {
    'CatBoost': (
        CatBoostRegressor(verbose=0, loss_function='MAE'),
        {
            'iterations':        [100, 300, 500, 1000],
            'learning_rate':     [0.001, 0.01, 0.05, 0.1, 0.2],
            'depth':             [4, 6, 8, 10],
            'random_strength':   [1, 5, 10, 20],
            'l2_leaf_reg':       [1, 3, 5, 7, 10],
            'bagging_temperature':[0, 0.5, 1, 2],
            'border_count':      [32, 64, 128],
            'subsample':         [0.6, 0.8, 1.0],
            'rsm':               [0.7, 0.8, 1.0]
        }
    )
}


def perform_grid_search_safe(model, param_grid, pool):
    try:
        grid_search = GridSearchCV(estimator=model, param_grid=param_grid,
                                   scoring='neg_mean_absolute_error', cv=5)
        grid_search.fit(pool.get_features(), pool.get_label(), sample_weight=pool.get_weight())
        return grid_search.best_estimator_, grid_search.best_params_
    except Exception as e:
        print(f"Failed to fit model {model} with error: {str(e)}")
        return None, None

for model_name, (model, param_grid) in models.items():
    best_model, best_params = perform_grid_search_safe(model, param_grid, train_pool)

    if best_model is None:
        continue

    labels_pred = best_model.predict(features_test)
    dump(best_model, f'../MLs/{model_name}_model-v1.1.joblib')

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

