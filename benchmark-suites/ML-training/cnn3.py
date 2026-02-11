import tensorflow as tf
from tensorflow.keras import layers, models
import os
import time

# Disable GPU
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

# Set max CPU thread usage
num_cores = 32
tf.config.threading.set_intra_op_parallelism_threads(num_cores)
tf.config.threading.set_inter_op_parallelism_threads(num_cores)

# Parameters
input_shape = (224, 224, 3)
num_classes = 1000
num_samples = 50000
batch_size = 16
epochs = 10

# Generate synthetic training data (to avoid IO bottlenecks)
def generate_synthetic_data(samples, shape, classes):
    x = tf.random.uniform((samples,) + shape)
    y = tf.random.uniform((samples,), maxval=classes, dtype=tf.int32)
    return x, y

train_images, train_labels = generate_synthetic_data(num_samples, input_shape, num_classes)

# Build tf.data input pipeline with real-world preprocessing
train_ds = tf.data.Dataset.from_tensor_slices((train_images, train_labels))
train_ds = train_ds.shuffle(1000).map(
    lambda x, y: (tf.image.random_flip_left_right(x), y),
    num_parallel_calls=tf.data.AUTOTUNE
).batch(batch_size).prefetch(tf.data.AUTOTUNE)

# Build heavy CNN model with 7 MaxPooling2D layers
def create_heavy_model():
    model = models.Sequential()
    model.add(layers.Input(shape=input_shape))

    for _ in range(7):  # Stop at 7 to avoid shape < 2x2
        model.add(layers.Conv2D(256, (3, 3), activation='relu', padding='same'))
        model.add(layers.BatchNormalization())
        model.add(layers.Conv2D(256, (3, 3), activation='relu', padding='same'))
        model.add(layers.BatchNormalization())
        model.add(layers.MaxPooling2D((2, 2)))  # Reduces spatial dimensions

    model.add(layers.Flatten())
    model.add(layers.Dense(2048, activation='relu'))
    model.add(layers.Dropout(0.5))
    model.add(layers.Dense(num_classes))  # Output layer without softmax (using logits)

    return model

# Create and compile model
model = create_heavy_model()
model.compile(
    optimizer='adam',
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

# Train the model and measure time
start_time = time.time()
history = model.fit(train_ds, epochs=epochs, verbose=2)
end_time = time.time()

print(f"\n✅ Training completed in {end_time - start_time:.2f} seconds.")

