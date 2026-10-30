# Echo Journal — Emotion Classifier Starter

This is a separate starter folder for the first AI milestone. It does not modify your original Milestone 1 website.

## What it includes
- A BiLSTM emotion classifier with randomly initialized weights (no pretrained classifier).
- Training and evaluation using the DAIR.AI Emotion dataset.
- A prediction script that works after training.
- Saved metrics and model outputs.

The dataset has six labels: sadness, joy, love, anger, fear, and surprise. It consists mainly of short social-media messages, so journal-style performance must be evaluated separately. Check dataset usage terms before submitting or redistributing.

## Windows PowerShell steps
1. Extract this ZIP.
2. Open PowerShell in the extracted `echo-journal-emotion-starter` folder.
3. Create a separate environment:
   `py -m venv .venv`
4. Install dependencies:
   `.\.venv\Scripts\python.exe -m pip install --upgrade pip`
   `.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt`
5. Train:
   `.\.venv\Scripts\python.exe train_emotion.py`
6. Predict:
   `.\.venv\Scripts\python.exe predict_emotion.py "I feel nervous about my exam but I am trying my best."`

Training downloads the dataset on the first run, so an internet connection is required. CPU is supported; CUDA is used automatically if available. Free GPU access is not guaranteed.

## Outputs
- `models/emotion_bilstm.pt`
- `models/vocab.json`
- `reports/metrics.json`

This is a standalone prototype and is not yet integrated into Flask. Predictions are estimates, not medical diagnoses.
