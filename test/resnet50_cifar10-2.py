import tensorflow as tf
from tensorflow.keras import layers, models
import numpy as np

# Generate a large synthetic dataset
num_samples = 1000000
image_size = 64  # Larger images for more computation per step

x_train = np.random.random((num_samples, image_size, image_size, 3))
y_train = np.random.randint(10, size=(num_samples,))
x_test = np.random.random((num_samples // 10, image_size, image_size, 3))
y_test = np.random.randint(10, size=(num_samples // 10,))

# Convert class vectors to binary class matrices (one-hot encoding)
y_train = tf.keras.utils.to_categorical(y_train, 10)
y_test = tf.keras.utils.to_categorical(y_test, 10)

# Define the ResNet-50 model
base_model = tf.keras.applications.ResNet50(weights=None, include_top=False, input_shape=(image_size, image_size, 3))
model = models.Sequential([
    base_model,
    layers.GlobalAveragePooling2D(),
    layers.Dense(1024, activation='relu'),
    layers.Dropout(0.5),
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

