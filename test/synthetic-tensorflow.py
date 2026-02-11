import tensorflow as tf
from tensorflow.keras import layers, models
import numpy as np

# Generate a large synthetic dataset
num_samples = 1000000
feature_size = 1024  # Increase the feature size to make the computation more intensive

x_train = np.random.random((num_samples, feature_size))
y_train = np.random.randint(10, size=(num_samples,))
x_test = np.random.random((num_samples // 10, feature_size))
y_test = np.random.randint(10, size=(num_samples // 10,))

# Convert class vectors to binary class matrices (one-hot encoding)
y_train = tf.keras.utils.to_categorical(y_train, 10)
y_test = tf.keras.utils.to_categorical(y_test, 10)

# Define a deep dense neural network model
model = models.Sequential([
    layers.Dense(4096, activation='relu', input_shape=(feature_size,)),
    layers.Dense(2048, activation='relu'),
    layers.Dense(1024, activation='relu'),
    layers.Dense(512, activation='relu'),
    layers.Dense(256, activation='relu'),
    layers.Dense(128, activation='relu'),
    layers.Dense(64, activation='relu'),
    layers.Dense(10, activation='softmax')
])

# Compile the model
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# Train the model
model.fit(x_train, y_train, batch_size=256, epochs=20, validation_data=(x_test, y_test))

# Evaluate the model
loss, accuracy = model.evaluate(x_test, y_test)
print(f'Test loss: {loss}')
print(f'Test accuracy: {accuracy}')

