import json
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from datasets import load_dataset
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix

SEED = 42
MAX_VOCAB = 20000
MAX_LEN = 40
EMBED_DIM = 64
HIDDEN_DIM = 64
BATCH_SIZE = 64
EPOCHS = 8
LEARNING_RATE = 0.001
PAD_TOKEN, UNK_TOKEN = "<PAD>", "<UNK>"
LABELS = ["sadness", "joy", "love", "anger", "fear", "surprise"]
ROOT = Path(__file__).resolve().parent
MODEL_DIR, REPORT_DIR = ROOT / "models", ROOT / "reports"
MODEL_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def tokenize(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+|[!?.,]", str(text).lower())

def build_vocab(texts):
    counts = Counter()
    for text in texts:
        counts.update(tokenize(text))
    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for token, _ in counts.most_common(MAX_VOCAB - len(vocab)):
        vocab[token] = len(vocab)
    return vocab

def encode(text, vocab):
    ids = [vocab.get(t, vocab[UNK_TOKEN]) for t in tokenize(text)][:MAX_LEN]
    return ids + [vocab[PAD_TOKEN]] * (MAX_LEN - len(ids))

class EmotionDataset(Dataset):
    def __init__(self, split, vocab):
        self.texts = split["text"]
        self.labels = [int(x) for x in split["label"]]
        self.vocab = vocab
    def __len__(self):
        return len(self.texts)
    def __getitem__(self, i):
        return (torch.tensor(encode(self.texts[i], self.vocab), dtype=torch.long),
                torch.tensor(self.labels[i], dtype=torch.long))

class BiLSTMClassifier(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_classes):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(hidden_dim * 2, num_classes)
    def forward(self, input_ids):
        embedded = self.embedding(input_ids)
        _, (hidden, _) = self.lstm(embedded)
        final_hidden = torch.cat((hidden[-2], hidden[-1]), dim=1)
        return self.classifier(self.dropout(final_hidden))

def evaluate(model, loader, device):
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for inputs, labels in loader:
            logits = model(inputs.to(device))
            ps.extend(logits.argmax(1).cpu().tolist())
            ys.extend(labels.tolist())
    return ys, ps

def main():
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Training device:", device)
    print("Downloading/loading DAIR.AI Emotion dataset...")
    dataset = load_dataset("dair-ai/emotion", "split")
    print("Dataset sizes:", {s: len(dataset[s]) for s in dataset.keys()})

    # Vocabulary uses training data only to avoid test-data leakage.
    vocab = build_vocab(dataset["train"]["text"])
    (MODEL_DIR / "vocab.json").write_text(json.dumps(vocab, indent=2), encoding="utf-8")
    train_loader = DataLoader(EmotionDataset(dataset["train"], vocab), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(EmotionDataset(dataset["validation"], vocab), batch_size=BATCH_SIZE)
    test_loader = DataLoader(EmotionDataset(dataset["test"], vocab), batch_size=BATCH_SIZE)

    model = BiLSTMClassifier(len(vocab), EMBED_DIM, HIDDEN_DIM, len(LABELS)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    best_f1, best_state = -1.0, None

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * x.size(0)
        vy, vp = evaluate(model, val_loader, device)
        vf1 = f1_score(vy, vp, average="macro")
        print(f"Epoch {epoch}/{EPOCHS} | train_loss={total_loss / len(train_loader.dataset):.4f} | val_macro_f1={vf1:.4f}")
        if vf1 > best_f1:
            best_f1 = vf1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    ty, tp = evaluate(model, test_loader, device)
    metrics = {
        "test_accuracy": float(accuracy_score(ty, tp)),
        "test_macro_f1": float(f1_score(ty, tp, average="macro")),
        "labels": LABELS,
        "classification_report": classification_report(ty, tp, labels=list(range(len(LABELS))),
            target_names=LABELS, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(ty, tp, labels=list(range(len(LABELS)))).tolist(),
        "note": "Trained from random initialization; no pretrained emotion model used."
    }
    (REPORT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    torch.save({"state_dict": model.state_dict(), "vocab_size": len(vocab),
        "embed_dim": EMBED_DIM, "hidden_dim": HIDDEN_DIM, "num_classes": len(LABELS),
        "labels": LABELS, "max_len": MAX_LEN}, MODEL_DIR / "emotion_bilstm.pt")
    print(f"\nDone. Test accuracy: {metrics['test_accuracy']:.4f}; macro-F1: {metrics['test_macro_f1']:.4f}")
    print("Saved model to models/emotion_bilstm.pt")
    print("Saved evaluation to reports/metrics.json")

if __name__ == "__main__":
    main()
