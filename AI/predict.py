import os
import sys

import torch
from PIL import Image
from torchvision import transforms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from model import FakeProductCNN

MODEL_PATH = os.path.join(BASE_DIR, "..", "fake_product_model.pt")

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

_model = None


def _load_model():
    global _model

    if _model is None:

        model = FakeProductCNN()

        state_dict = torch.load(MODEL_PATH, map_location=_device)

        model.load_state_dict(state_dict)

        model.to(_device)

        model.eval()

        _model = model

    return _model


def predict_image(image_path):

    model = _load_model()

    image = Image.open(image_path).convert("RGB")

    image = _transform(image).unsqueeze(0).to(_device)

    with torch.no_grad():

        output = model(image)

        probability = torch.sigmoid(output).item()

    if probability >= 0.5:
        return "genuine", probability
    else:
        return "fake", 1 - probability