import json
import re
import sys
from pathlib import Path
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
PAD_TOKEN, UNK_TOKEN = "<PAD>", "<UNK>"

def tokenize(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+|[!?.,]", str(text).lower())

class BiLSTMClassifier(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, num_classes):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True, bidirectional=True)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(hidden_dim * 2, num_classes)
    def forward(self, ids):
        _, (hidden, _) = self.lstm(self.embedding(ids))
        return self.classifier(self.dropout(torch.cat((hidden[-2], hidden[-1]), dim=1)))

def main():
    if len(sys.argv) < 2:
        print('Usage: python predict_emotion.py "Your text here"')
        raise SystemExit(2)
    model_path, vocab_path = MODEL_DIR / "emotion_bilstm.pt", MODEL_DIR / "vocab.json"
    if not model_path.exists() or not vocab_path.exists():
        print("Trained model not found. Run train_emotion.py first.")
        raise SystemExit(1)
    text = " ".join(sys.argv[1:])
    ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    ids = [vocab.get(t, vocab[UNK_TOKEN]) for t in tokenize(text)][:ckpt["max_len"]]
    ids += [vocab[PAD_TOKEN]] * (ckpt["max_len"] - len(ids))
    model = BiLSTMClassifier(ckpt["vocab_size"], ckpt["embed_dim"], ckpt["hidden_dim"], ckpt["num_classes"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    with torch.no_grad():
        probs = torch.softmax(model(torch.tensor([ids], dtype=torch.long)), dim=1)[0]
    idx = int(probs.argmax().item())
    print("Predicted emotion:", ckpt["labels"][idx])
    print(f"Model confidence (not a guarantee): {probs[idx].item():.1%}")
    print("Experimental estimate only; not a diagnosis.")

if __name__ == "__main__":
    main()
