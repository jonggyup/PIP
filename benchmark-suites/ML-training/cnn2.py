#!/usr/bin/env python3
import os, time, math, argparse
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, losses, optimizers, metrics

# -------- Args --------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--intensity", type=float, default=1.0,
                   help="Compute multiplier (>=1). Scales H,W and channels; keeps per-step cost ~constant vs base.")
    p.add_argument("--epochs", type=int, default=40, help="Baseline epochs (will be divided by speedup).")
    p.add_argument("--batch", type=int, default=512, help="Batch size.")
    p.add_argument("--num-cores", type=int, default=max(30, os.cpu_count()),
                   help="CPU threads for TF intra/inter op.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speedup", type=int, default=10, help="Target runtime speedup (e.g., 10 => ~1/10 steps).")
    return p.parse_args()

# -------- Planning logic --------
BASE_IMG   = 32
BASE_TRAIN = 50_000
BASE_TEST  = 10_000

def plan(intensity: float):
    """
    Per-step compute ~ intensity via resizing and width multiplier.
    Do NOT reduce dataset for speedup; we control total steps via epochs.
    """
    I = max(1.0, float(intensity))
    sqrtI = math.sqrt(I)

    target_size = int(min(96, BASE_IMG * sqrtI))
    target_size = max(32, (target_size // 2) * 2)
    width_mult = max(1, int(round(sqrtI)))
    extra_blocks = max(0, int(round(math.log2(I))))

    # Keep full dataset for stable convergence at reduced epochs
    train_n = BASE_TRAIN
    test_n  = BASE_TEST

    return target_size, width_mult, extra_blocks, train_n, test_n

# -------- Data pipeline --------
def make_datasets(img_size, train_n, test_n, batch, seed):
    (xtr, ytr), (xte, yte) = tf.keras.datasets.cifar10.load_data()
    xtr = xtr.astype("float32") / 255.0
    xte = xte.astype("float32") / 255.0

    rng = np.random.default_rng(seed)
    train_idx = rng.permutation(len(xtr))[:train_n]
    test_idx  = rng.permutation(len(xte))[:test_n]
    xtr, ytr = xtr[train_idx], ytr[train_idx]
    xte, yte = xte[test_idx],  yte[test_idx]

    def augment(img, label):
        img = tf.image.resize(img, (img_size, img_size), method="bilinear")
        img = tf.image.random_flip_left_right(img, seed=seed)
        pad = 4
        img = tf.pad(img, [[pad, pad], [pad, pad], [0, 0]], mode="REFLECT")
        img = tf.image.random_crop(img, size=[img_size, img_size, 3], seed=seed)
        return img, label

    def preprocess(img, label):
        img = tf.image.resize(img, (img_size, img_size), method="bilinear")
        return img, label

    autotune = tf.data.AUTOTUNE
    ds_train = (tf.data.Dataset.from_tensor_slices((xtr, ytr))
                .shuffle(buffer_size=min(10_000, train_n), seed=seed, reshuffle_each_iteration=True)
                .map(augment, num_parallel_calls=autotune)
                .batch(batch, drop_remainder=True)
                .prefetch(autotune))

    ds_test = (tf.data.Dataset.from_tensor_slices((xte, yte))
               .map(preprocess, num_parallel_calls=autotune)
               .batch(batch, drop_remainder=False)
               .prefetch(autotune))
    return ds_train, ds_test

# -------- Model --------
def conv_block(x, filters, extra_convs: int):
    for _ in range(1 + extra_convs):
        x = layers.Conv2D(filters, 3, padding="same", use_bias=False)(x)
        x = layers.BatchNormalization()(x)
        x = layers.ReLU()(x)
    return x

def create_model(img_size, width_mult, extra_blocks):
    inputs = layers.Input(shape=(img_size, img_size, 3))
    x = inputs
    x = conv_block(x, 32 * width_mult, extra_blocks); x = layers.MaxPooling2D(2)(x)
    x = conv_block(x, 64 * width_mult, extra_blocks); x = layers.MaxPooling2D(2)(x)
    x = conv_block(x, 128 * width_mult, extra_blocks); x = layers.MaxPooling2D(2)(x)
    if extra_blocks >= 2:
        x = conv_block(x, 128 * width_mult, extra_blocks - 1); x = layers.MaxPooling2D(2)(x)
    x = layers.Flatten()(x)
    x = layers.Dense(256 * max(1, width_mult // 2), activation="relu")(x)
    x = layers.Dense(128 * max(1, width_mult // 2), activation="relu")(x)
    outputs = layers.Dense(10)(x)
    return models.Model(inputs, outputs)

# -------- Main --------
def main():
    args = parse_args()
    tf.config.threading.set_intra_op_parallelism_threads(args.num_cores)
    tf.config.threading.set_inter_op_parallelism_threads(args.num_cores)
    tf.random.set_seed(args.seed)

    img_size, width_mult, extra_blocks, train_n, test_n = plan(args.intensity)

    # Derive epochs for ~1/speedup total steps, keeping steps/epoch ~ baseline
    epochs = max(1, args.epochs // args.speedup)

    ds_train, ds_test = make_datasets(img_size, train_n, test_n, args.batch, args.seed)
    model = create_model(img_size, width_mult, extra_blocks)
    model.compile(
        optimizer=optimizers.Adam(),
        loss=losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[metrics.SparseCategoricalAccuracy(name="acc")]
    )

    # Diagnostics: planned steps
    steps_per_epoch = int(np.ceil(train_n / args.batch))
    baseline_steps_per_epoch = int(np.ceil(BASE_TRAIN / args.batch))
    baseline_total_steps = baseline_steps_per_epoch * args.epochs
    total_steps = steps_per_epoch * epochs

    print(f"[Plan] intensity={args.intensity:.2f} | img={img_size} | width×={width_mult} "
          f"| extra_blocks={extra_blocks} | train_n={train_n} | test_n={test_n} "
          f"| batch={args.batch} | epochs={epochs}")
    print(f"[Steps] baseline_steps/epoch={baseline_steps_per_epoch} "
          f"| baseline_total≈{baseline_total_steps} | steps/epoch={steps_per_epoch} "
          f"| total≈{total_steps} (target≈baseline/ {args.speedup})")

    t0 = time.time()
    model.fit(ds_train, epochs=epochs, validation_data=ds_test, verbose=2)
    t1 = time.time()
    print(f"Training completed in {t1 - t0:.2f} seconds.")
    eval_res = model.evaluate(ds_test, verbose=2)
    print(f"Test accuracy: {eval_res[1]:.4f}")

if __name__ == "__main__":
    main()
