import tensorflow as tf
from tensorflow.keras import layers, models
import numpy as np

# Generate a small synthetic dataset quickly
num_samples = 10000  # Smaller dataset for faster preparation
image_size = 32  # Smaller image size for quicker generation

x_train = np.random.random((num_samples, image_size, image_size, 3)).astype(np.float32)
y_train = np.random.randint(10, size=(num_samples,)).astype(np.int32)
x_test = np.random.random((num_samples // 10, image_size, image_size, 3)).astype(np.float32)
y_test = np.random.randint(10, size=(num_samples // 10,)).astype(np.int32)

# Convert class vectors to binary class matrices (one-hot encoding)
y_train = tf.keras.utils.to_categorical(y_train, 10)
y_test = tf.keras.utils.to_categorical(y_test, 10)

# Define a complex CNN model with high parallelism
model = models.Sequential([
    layers.Conv2D(128, kernel_size=(3, 3), activation='relu', input_shape=(image_size, image_size, 3)),
    layers.Conv2D(128, kernel_size=(3, 3), activation='relu'),
    layers.Conv2D(256, kernel_size=(3, 3), activation='relu'),
    layers.Conv2D(256, kernel_size=(3, 3), activation='relu'),
    layers.Conv2D(512, kernel_size=(3, 3), activation='relu'),
    layers.Conv2D(512, kernel_size=(3, 3), activation='relu'),
    layers.MaxPooling2D(pool_size=(2, 2)),
    layers.Flatten(),
    layers.Dense(4096, activation='relu'),
    layers.Dense(2048, activation='relu'),
    layers.Dense(1024, activation='relu'),
    layers.Dense(512, activation='relu'),
    layers.Dense(256, activation='relu'),
    layers.Dense(128, activation='relu'),
    layers.Dense(10, activation='softmax')
])

# Compile the model
model.compile(optimizer='adam',
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# Train the model with a larger batch size
model.fit(x_train, y_train, batch_size=512, epochs=5, validation_data=(x_test, y_test))

# Evaluate the model
loss, accuracy = model.evaluate(x_test, y_test)
print(f'Test loss: {loss}')
print(f'Test accuracy: {accuracy}')

