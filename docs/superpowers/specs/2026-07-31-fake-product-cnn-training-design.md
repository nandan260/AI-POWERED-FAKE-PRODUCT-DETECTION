# Fake Product Detection: Dataset + Training Pipeline

## Problem

`AI/prepare_dataset.py` and `AI/train_cnn.py` exist but are non-functional in this
repo: both hard-code paths to a different machine (`C:\Users\nandan\...`), no
dataset is checked in, no `requirements.txt` exists, and the machine's default
Python (3.14) has no TensorFlow build available.

## Decisions

- **Dataset**: Kaggle `prashanthgolla/fake-brand-data` — real product photos
  labeled fake/genuine by brand (Adidas, Nike, Gucci, Puma, etc.), ~285MB.
  Chosen over `aimlveera/counterfeit-product-detection-dataset` because that
  one is tabular CSVs, incompatible with the existing CNN approach.
- **Environment**: dedicated `.venv311` built from the Python 3.11 already
  installed on this machine (via the `py` launcher), since TensorFlow has no
  Python 3.14 build yet. Existing Keras/TensorFlow code in `train_cnn.py` is
  kept, not rewritten in PyTorch.

## Plan

1. **Acquire data** — download the Kaggle dataset via the already-configured
   `kaggle` CLI into a scratch location, extract it.
2. **Rewrite `AI/prepare_dataset.py`** — walk the extracted `<brand>_fake` /
   `<brand>_genuine` folders, collapse all brands into two classes
   (`genuine`, `fake`), 80/20 train/test split, write into
   `AI/dataset/train/{genuine,fake}` and `AI/dataset/test/{genuine,fake}`,
   all paths relative to the repo root (no more hardcoded `nandan` paths).
3. **Cross-verify** — after prep, confirm: both classes present and roughly
   balanced; a sample of images per class opens as valid images (catches
   corrupt/truncated files); final folder layout matches what
   `flow_from_directory` in `train_cnn.py` expects.
4. **Requirements** — write `requirements.txt` (tensorflow, pillow, numpy,
   scipy — versions compatible with Python 3.11).
5. **Environment setup** — create `.venv311`, install `requirements.txt` into it.
6. **Fix `AI/train_cnn.py`** — replace hardcoded dataset paths with the
   relative `AI/dataset/train` / `AI/dataset/test` paths; keep the existing
   CNN architecture (2 conv blocks, dense 128, dropout 0.5, sigmoid output)
   and training config (10 epochs, batch size 32) unchanged.
7. **Train** — run `train_cnn.py` inside `.venv311`, in the background (CPU
   training over a few hundred/thousand images can take a while); report
   final train/validation accuracy and the saved `fake_product_model.keras`.

## Out of scope

- Wiring the trained model into `app.py` (the Flask app currently doesn't
  call the CNN at all — it's a separate QR-code verification flow). Not
  requested; can be a follow-up.
- Hyperparameter tuning / architecture changes — keeping the existing model
  as-is per the "start training it" ask.

## Risks / notes

- 285MB download + CPU-only training of a CNN over potentially thousands of
  224×224 images may take a long time (could be 30+ minutes for 10 epochs).
  Will run training in the background and report back rather than blocking.
- Dataset has multiple brands folded into 2 classes; no dedup/near-duplicate
  check across brands is planned (out of scope, would need explicit ask).
