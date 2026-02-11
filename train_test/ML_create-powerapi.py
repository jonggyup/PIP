import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor
from sklearn.svm import SVR
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor
from sklearn.neighbors import KNeighborsRegressor

from joblib import dump
import os

# Load data
data = pd.read_csv('../data/training-data.csv')

# Read the second value from the topol.dat file
with open('../estimation/topol_metric_size.dat', 'r') as file:
    values = file.read().split()  # Assuming the file contains space-separated or newline-separated values
    perf_metric_index = int(values[1])  # Get the second value and convert to an integer

selected_indices = {perf_metric_index,perf_metric_index+1, perf_metric_index+2, perf_metric_index+3}

# Adjust the condition in your list comprehension
pca_columns = [col for col_index, col in enumerate(data.columns) 
               if col_index in selected_indices and col != 'label']



## Define the columns to be included
#pca_columns = [col for col_index, col in enumerate(data.columns) if (col_index >= 448 and col_index < 478) and col != 'label']

# Split the data into training and test sets
train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)

# Check for NaNs and handle them
if train_data[pca_columns].isnull().any().any() or train_data['label'].isnull().any():
    # Fill NaNs in features and labels (You can adjust the method of filling as needed)
    train_data[pca_columns] = train_data[pca_columns].fillna(train_data[pca_columns].mean())
    train_data['label'] = train_data['label'].fillna(train_data['label'].median())

# Assign the original data to the variables
features_train = train_data[pca_columns]
labels_train = train_data['label']

features_test = test_data[pca_columns].fillna(train_data[pca_columns].mean())  # Filling NaNs in test features similarly
labels_test = test_data['label'].fillna(train_data['label'].median())  # Filling NaNs in test labels

os.makedirs("../MLs", exist_ok=True)

# Define Ridge Regression model and hyperparameter grid
models = {
    'Ridge': (Ridge(), {
        'alpha': [0.1, 1.0, 10.0],  # Regularization strength
        'solver': ['auto', 'svd', 'cholesky', 'lsqr']  # Different solvers for optimization
    })
}

# Function to perform grid search and return best model
def perform_grid_search_safe(model, param_grid, features, labels):
    try:
        grid_search = GridSearchCV(estimator=model, param_grid=param_grid, scoring='neg_mean_squared_error', cv=5)
        grid_search.fit(features, labels)
        return grid_search.best_estimator_, grid_search.best_params_
    except Exception as e:
        print(f"Failed to fit model {model} with error: {str(e)}")
        return None, None

# Run grid search and evaluate each model
for model_name, (model, param_grid) in models.items():
    best_model, best_params = perform_grid_search_safe(model, param_grid, features_train, labels_train)

    if best_model is None:
        continue  # If the model couldn't be fit, skip to the next

    # Evaluate on the test set
    labels_pred = best_model.predict(features_test)
    dump(best_model, f'../MLs/{model_name}_model-powerapi.joblib')

    # Calculate the errors
    errors = np.abs(labels_test - labels_pred)

    # Mean Squared Error and Mean Absolute Error
    mse = mean_squared_error(labels_test, labels_pred)
    mae = mean_absolute_error(labels_test, labels_pred)

    # Standard Deviation of Absolute Errors
    std_dev_mae = np.std(errors)

    # Percentage of Absolute Difference
    percentage_errors = (errors / labels_test) * 100
    mean_percentage_error = np.mean(percentage_errors)
    std_dev_percentage_error = np.std(percentage_errors)

    # Simple Average Error Percentage relative to the Average of Ground Truth
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

