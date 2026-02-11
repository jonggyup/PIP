from catboost import CatBoostRegressor
import pandas as pd
from sklearn.metrics import mean_squared_error
from joblib import load

# Load the previously trained model
model = CatBoostRegressor()
model = load('../MLs/CatBoost_model.joblib')

# Function to update the model with new data 

def update_model(new_data, model, learning_rate=0.1, new_data_weight=2):
    # Create a new model with the updated learning rate
    updated_model = CatBoostRegressor(learning_rate=learning_rate)

    features_new = new_data.drop('label', axis=1)
    labels_new = new_data['label']
    sample_weight = [new_data_weight] * len(new_data)

    # Continue training from the previous model's state
    updated_model.fit(features_new, labels_new, init_model=model, sample_weight=sample_weight)

    return updated_model


# Load new data
new_data = pd.read_csv('../data/new-data-chunk.csv')

# Update the model with new data using default values
model = update_model(new_data, model)

# Evaluate the updated model on the new data
features_new = new_data.drop('label', axis=1)
labels_new = new_data['label']
predictions = model.predict(features_new)
mse = mean_squared_error(labels_new, predictions)
print(f'Updated Model - Mean Squared Error: {mse:.2f}')

# Save the updated model, replacing the old one
model.save_model('../MLs/CatBoost_model-new.joblib')

