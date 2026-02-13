import os
import time
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import xgboost as xgb

# Load the IMDb dataset
dataset = load_dataset("imdb")
X, y = dataset["train"]["text"], dataset["train"]["label"]

# For demonstration, we'll use a subset of the data
X, y = X[:100000], y[:100000]

# Convert text data to numerical features using TF-IDF
vectorizer = TfidfVectorizer(max_features=100000)
X_tfidf = vectorizer.fit_transform(X)

# Split the data into training and test sets
X_train, X_test, y_train, y_test = train_test_split(X_tfidf, y, test_size=0.2, random_state=42)

# Convert the data to DMatrix format for XGBoost
dtrain = xgb.DMatrix(X_train, label=y_train)
dtest = xgb.DMatrix(X_test, label=y_test)

# Set XGBoost parameters to use all available CPU cores
params = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "nthread": 32 #os.cpu_count()
}

# Train the XGBoost model
start_time = time.time()
bst = xgb.train(params, dtrain, num_boost_round=3000)
training_time = time.time() - start_time

# Make predictions on the test set
preds = bst.predict(dtest)
predictions = [round(value) for value in preds]

# Calculate accuracy
accuracy = accuracy_score(y_test, predictions)

print(f"Training Time: {training_time} seconds")
print(f"Test Accuracy: {accuracy}")

