import pandas as pd

# Load data
data = pd.read_csv('../data/training-data.csv')

# Identify NaNs in the dataset
nan_in_columns = data.isnull().sum()
nan_in_rows = data[data.isnull().any(axis=1)]

# Print columns with NaNs and their count
print("Columns with NaN values and their count:")
print(nan_in_columns[nan_in_columns > 0])

# Check if there are any rows with NaNs and remove them
if not nan_in_rows.empty:
    print("\nRows with NaN values before removal:")
    print(nan_in_rows)

    # Remove rows with NaN values
    data_cleaned = data.dropna()
    print("\nRows with NaN values have been removed.")

    # Optionally, save the cleaned data to a new CSV file
    data_cleaned.to_csv('../data/cleaned-training-data.csv', index=False)
    print("\nCleaned data saved to '../data/cleaned-training-data.csv'.")
else:
    print("\nNo NaN values found in rows.")

