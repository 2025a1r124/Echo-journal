ECHO JOURNAL — COMPLETE PACKAGE SO FAR

WHAT IS INCLUDED
1. echo-journal/ — the latest Milestone 2 Flask project. It contains the Milestone 1 journaling website features plus the optional on-demand sentiment/emotion analysis implementation included in the Milestone 2 source.
2. previous-milestone-snapshot/echo-journal-milestone-1-baseline.zip — the original Milestone 1 project snapshot, kept for reference.
3. emotion-classifier-starter/ — separate code to train a custom BiLSTM emotion classifier from randomly initialized weights (no pretrained classifier weights).

IMPORTANT STATUS NOTE
The custom classifier starter is NOT integrated into the Flask website yet. It is source code only; no trained model is included. Run its training script separately after following its README. The Milestone 2 app's optional AI analysis code and the custom-from-scratch training starter are separate at this stage.

RUN THE MILESTONE 2 WEBSITE
Open a terminal in the echo-journal folder. Follow echo-journal/README.md. On Windows, use a separate virtual environment for this project. Do not copy a .venv from another folder.

TRAIN THE CUSTOM EMOTION CLASSIFIER
Open a separate terminal in emotion-classifier-starter/ and follow its README.md. This requires internet access to download the dataset and compatible ML packages.

NOT INCLUDED
- A trained custom emotion model (training has not yet been run here).
- Online deployment, hosted database, or hosted LLM integration.
- Any personal .env secrets or virtual-environment folders.
