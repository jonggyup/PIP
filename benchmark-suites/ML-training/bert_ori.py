import os
import time
import tensorflow as tf
from datasets import load_dataset
from transformers import BertTokenizer, TFBertForSequenceClassification

# Set TensorFlow to use all available CPUs
os.environ['TF_NUM_INTRAOP_THREADS'] = "20"

tf.config.threading.set_intra_op_parallelism_threads(os.cpu_count())

# Load and preprocess a subset of the IMDb dataset using all available cores
def load_and_preprocess_data():
    dataset = load_dataset("imdb")
    small_train_dataset = dataset["train"].shuffle(seed=42).select(range(1000))  # Use only 1,000 samples for training
    small_test_dataset = dataset["test"].shuffle(seed=42).select(range(1000))    # Use only 1,000 samples for testing

    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=128)

    tokenized_train_dataset = small_train_dataset.map(tokenize_function, batched=True, num_proc=os.cpu_count())
    tokenized_test_dataset = small_test_dataset.map(tokenize_function, batched=True, num_proc=os.cpu_count())

    tokenized_train_dataset.set_format("tensorflow")
    tokenized_test_dataset.set_format("tensorflow")
    return tokenized_train_dataset, tokenized_test_dataset

# Define the BERT model for sequence classification
def create_model():
    model = TFBertForSequenceClassification.from_pretrained("bert-base-uncased")
    optimizer = tf.keras.optimizers.SGD(learning_rate=5e-5)
    loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    model.compile(optimizer=optimizer, loss=loss, metrics=["accuracy"])
    return model

# Train and evaluate the model
def train_and_evaluate_model(model, train_dataset, test_dataset):
    train_tf_dataset = train_dataset.to_tf_dataset(
        columns=["attention_mask", "input_ids", "token_type_ids"],
        label_cols=["label"],
        shuffle=True,
        batch_size=8,
    )

    test_tf_dataset = test_dataset.to_tf_dataset(
        columns=["attention_mask", "input_ids", "token_type_ids"],
        label_cols=["label"],
        shuffle=False,
        batch_size=8,
    )

    start_time = time.time()
    model.fit(train_tf_dataset, epochs=1)  # Reduce the number of epochs to 1
    training_time = time.time() - start_time

    test_loss, test_accuracy = model.evaluate(test_tf_dataset)
    return training_time, test_loss, test_accuracy

if __name__ == "__main__":
    train_dataset, test_dataset = load_and_preprocess_data()
    bert_model = create_model()
    training_time, test_loss, test_accuracy = train_and_evaluate_model(bert_model, train_dataset, test_dataset)

    print(f"Training Time: {training_time} seconds")
    print(f"Test Loss: {test_loss}")
    print(f"Test Accuracy: {test_accuracy}")

