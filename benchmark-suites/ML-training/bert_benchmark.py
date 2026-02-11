# bert_benchmark.py — PyTorch/Transformers CPU benchmark (version-agnostic args)
import os
import time
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

# Stay on CPU and avoid TF pathways
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

cpu_count = os.cpu_count() or 1
#torch.set_num_threads(min(20, cpu_count))
torch.set_num_threads(min(60, cpu_count))

def load_and_preprocess_data():
    dataset = load_dataset("imdb")
    train = dataset["train"].shuffle(seed=42).select(range(1000))
    test  = dataset["test"].shuffle(seed=42).select(range(1000))

    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

    def tok(examples):
        return tokenizer(examples["text"], padding=False, truncation=True, max_length=128)

    train = train.map(tok, batched=True, num_proc=cpu_count)
    test  = test.map(tok,  batched=True, num_proc=cpu_count)

    keep = {"input_ids", "attention_mask", "label"}
    train = train.remove_columns([c for c in train.column_names if c not in keep])
    test  = test.remove_columns([c for c in test.column_names  if c not in keep])
    train.set_format("torch")
    test.set_format("torch")
    return tokenizer, train, test

def compute_metrics(eval_pred):
    # Works across transformers versions
    if isinstance(eval_pred, tuple):
        logits, labels = eval_pred
    else:
        logits, labels = eval_pred.predictions, eval_pred.label_ids
    preds = np.argmax(logits, axis=-1)
    return {"accuracy": (preds == labels).mean().item()}

def main():
    tokenizer, train_ds, test_ds = load_and_preprocess_data()

    model = AutoModelForSequenceClassification.from_pretrained(
        "bert-base-uncased", num_labels=2
    )

    # Build TrainingArguments with only supported kwargs (handles older versions)
    possible_kwargs = dict(
        output_dir="./bert_out",
        num_train_epochs=1,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        logging_steps=50,
        no_cuda=True,
        disable_tqdm=True,
        seed=42,
        # Newer versions (silently filtered if unsupported):
        evaluation_strategy="no",
        save_strategy="no",
        report_to=[],
        dataloader_num_workers=0,
    )
    supported = set(inspect.signature(TrainingArguments.__init__).parameters.keys())
    filtered_kwargs = {k: v for k, v in possible_kwargs.items() if k in supported}
    args = TrainingArguments(**filtered_kwargs)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
    )

    t0 = time.time()
    trainer.train()
    train_time = time.time() - t0

    metrics = trainer.evaluate()
    print(f"Training Time: {train_time:.2f} seconds")
    print(f"Test Loss: {metrics.get('eval_loss'):.4f}")
    print(f"Test Accuracy: {metrics.get('eval_accuracy'):.4f}")

if __name__ == "__main__":
    main()


