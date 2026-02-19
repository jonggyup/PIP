# bert_benchmark.py — PyTorch/Transformers CPU benchmark with intensity knob
import os

# Set env BEFORE importing transformers/torch to avoid optional TF/JAX pathways
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import time
import math
import argparse
import numpy as np
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding,
)
import inspect

cpu_count = os.cpu_count() or 1
torch.set_num_threads(min(20, cpu_count))
if hasattr(torch, "set_num_interop_threads"):
    torch.set_num_interop_threads(min(8, max(2, cpu_count // 4)))

BASE_TRAIN = 1000
BASE_TEST  = 10000
BASE_SEQ   = 64

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--intensity", type=float, default=1.0,
                   help="Compute multiplier ≥1. Increases seq length & grad accumulation while reducing dataset size to keep runtime ~constant. 1.0 = baseline.")
    p.add_argument("--epochs", type=float, default=1.0, help="Training epochs (float ok).")
    p.add_argument("--train-bsz", type=int, default=8, help="Per-device train batch size.")
    p.add_argument("--eval-bsz", type=int, default=8, help="Per-device eval batch size.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--time-cut", type=float, default=1.0,
                   help="Divide training epochs by this factor (e.g., 3.0 ⇒ ~1/3 wall time).")
    return p.parse_args()

def plan_from_intensity(intensity: float):
    """
    Attention cost ~ O(L^2). Increase L by ~sqrt(intensity) and add
    grad accumulation by ~sqrt(intensity). To keep wall-time ~constant,
    reduce dataset size by ~intensity.
    """
    intensity = max(1.0, float(intensity))
    seq_factor = max(1.0, math.sqrt(intensity))
    seq_len = int(min(512, BASE_SEQ * seq_factor))
    grad_accum = max(1, int(round(seq_factor)))

    scale = intensity
    train_n = max(100, int(BASE_TRAIN / scale))
    test_n  = max(200, int(BASE_TEST  / scale))
    return seq_len, grad_accum, train_n, test_n

def load_and_preprocess_data(seq_len: int, seed: int, train_n: int, test_n: int):
    dataset = load_dataset("imdb")

    # IMPORTANT: subset BEFORE tokenization so runtime actually tracks train_n/test_n
    train_raw = dataset["train"].shuffle(seed=seed).select(range(train_n))
    test_raw  = dataset["test"].shuffle(seed=seed).select(range(test_n))

    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

    def tok(examples):
        return tokenizer(examples["text"], padding=False, truncation=True, max_length=seq_len)

    # num_proc can add overhead for tiny subsets; keep it moderate
    procs = min(8, cpu_count)

    train_tok = train_raw.map(tok, batched=True, num_proc=procs)
    test_tok  = test_raw.map(tok, batched=True, num_proc=procs)

    def finalize(ds):
        keep = {"input_ids", "attention_mask", "label"}
        ds = ds.remove_columns([c for c in ds.column_names if c not in keep])
        ds.set_format("torch")
        return ds

    return tokenizer, finalize(train_tok), finalize(test_tok)

def compute_metrics(eval_pred):
    if isinstance(eval_pred, tuple):
        logits, labels = eval_pred
    else:
        logits, labels = eval_pred.predictions, eval_pred.label_ids
    preds = np.argmax(logits, axis=-1)
    return {"accuracy": (preds == labels).mean().item()}

def filtered_kwargs_for(callable_obj, kwargs: dict):
    params = set(inspect.signature(callable_obj).parameters.keys())
    return {k: v for k, v in kwargs.items() if k in params}

def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    seq_len, grad_accum, train_n, test_n = plan_from_intensity(args.intensity)

    tokenizer, train_ds, test_ds = load_and_preprocess_data(seq_len, args.seed, train_n, test_n)

    model = AutoModelForSequenceClassification.from_pretrained(
        "bert-base-uncased", num_labels=2
    )
    # NOTE: The "UNEXPECTED/MISSING" load report you saw is normal for bert-base-uncased
    # because the classification head is newly initialized.

    possible_targs = dict(
        output_dir="./bert_out",
        num_train_epochs=max(0.01, float(args.epochs) / float(args.time_cut)),
        per_device_train_batch_size=args.train_bsz,
        per_device_eval_batch_size=args.eval_bsz,
        gradient_accumulation_steps=grad_accum,
        logging_steps=50,
        disable_tqdm=True,
        seed=args.seed,
        dataloader_num_workers=0,
        evaluation_strategy="no",
        save_strategy="no",
        report_to=[],
        # CPU-only flags vary by version; include both and filter by signature
        no_cuda=True,
        use_cpu=True,
    )
    train_args = TrainingArguments(**filtered_kwargs_for(TrainingArguments.__init__, possible_targs))

    trainer_kwargs = dict(
        model=model,
        args=train_args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
        tokenizer=tokenizer,  # only passed if supported
    )
    trainer = Trainer(**filtered_kwargs_for(Trainer.__init__, trainer_kwargs))

    t0 = time.time()
    trainer.train()
    train_time = time.time() - t0

    metrics = trainer.evaluate()
    print(f"Intensity: {args.intensity:.2f} | SeqLen: {seq_len} | GradAccum: {grad_accum} | Train/Eval: {len(train_ds)}/{len(test_ds)}")
    print(f"Epochs: {args.epochs:.3f} / TimeCut: {args.time_cut:.3f} -> EffectiveEpochs: {float(args.epochs)/float(args.time_cut):.3f}")
    print(f"Training Time: {train_time:.2f} seconds")
    print(f"Test Loss: {metrics.get('eval_loss'):.4f}")
    if 'eval_accuracy' in metrics:
        print(f"Test Accuracy: {metrics.get('eval_accuracy'):.4f}")

if __name__ == "__main__":
    main()

