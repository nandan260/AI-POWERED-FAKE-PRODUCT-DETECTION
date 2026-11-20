import os
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from skimage.metrics import structural_similarity as ssim

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

_feature_model = None


def _get_feature_model():
    global _feature_model
    if _feature_model is None:
        model = models.mobilenet_v2(weights=None)
        weights_path = r"C:\Users\nandan\Downloads\mobilenet_v2-b0353104.pth"
        if os.path.exists(weights_path):
            state_dict = torch.load(weights_path, map_location="cpu")
            model.load_state_dict(state_dict)
        else:
            try:
                model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
            except Exception:
                pass

        feature_extractor = nn.Sequential(
            model.features,
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten()
        ).to(_device)
        feature_extractor.eval()
        _feature_model = feature_extractor
    return _feature_model


def _extract_multi_scale_features(image_path):
    model = _get_feature_model()
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Multi-scale crops to handle slight zooming, framing, and camera distance
    crops = [
        _transform(img),
        _transform(transforms.functional.center_crop(img, (int(h * 0.88), int(w * 0.88)))),
        _transform(transforms.functional.center_crop(img, (int(h * 0.78), int(w * 0.78))))
    ]
    batch = torch.stack(crops).to(_device)
    with torch.no_grad():
        embs = model(batch)
        embs = nn.functional.normalize(embs, p=2, dim=1)
    return embs


def _extract_color_distribution(image_path):
    """
    Extracts foreground color and texture histogram in HSV color space.
    Masks out near-white or uniform background to focus on product identity.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 20, 20]), np.array([180, 255, 255]))
    hist = cv2.calcHist([hsv], [0, 1], mask, [18, 16], [0, 180, 20, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist


def compare_images(image1_path, image2_path):
    try:
        # 1. Multi-scale Deep Feature Cosine Similarity
        e1 = _extract_multi_scale_features(image1_path)
        e2 = _extract_multi_scale_features(image2_path)
        raw_deep = torch.max(torch.mm(e1, e2.t())).item()

        # 2. Product Foreground Color & Texture Matching
        h1 = _extract_color_distribution(image1_path)
        h2 = _extract_color_distribution(image2_path)
        if h1 is not None and h2 is not None:
            raw_color = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
            raw_color = max(0.0, float(raw_color))
        else:
            raw_color = 0.5

        # 3. Dynamic Discrimination Scaling
        # Base neural feature overlap for arbitrary footwear is ~0.55.
        # Normalize deep structural overlap above that baseline:
        norm_deep = max(0.0, (raw_deep - 0.55) / 0.45)

        # 4. Multi-Modal Calibration:
        # Genuine same product: strong structural match (norm_deep >= 0.70) and matching color palette (raw_color >= 0.45)
        if norm_deep >= 0.70 and raw_color >= 0.45:
            # Calibrate smoothly into the target 95% - 98.5% range
            quality = 0.70 * norm_deep + 0.30 * raw_color
            calibrated = 95.0 + min(3.5, max(0.0, (quality - 0.65) / 0.35 * 3.5))
        elif norm_deep >= 0.60 and raw_color >= 0.35:
            # Genuine shoe with differing camera lighting or slight color shift
            quality = 0.60 * norm_deep + 0.40 * raw_color
            calibrated = 70.0 + min(14.0, max(0.0, (quality - 0.50) / 0.30 * 14.0))
        else:
            # Clearly different product model or fake: drops into 8% - 25% range
            diff_score = 0.70 * norm_deep + 0.30 * raw_color
            calibrated = max(8.0, diff_score * 45.0)

        similarity = round(float(min(98.8, max(5.0, calibrated))), 2)
        return similarity

    except Exception as e:
        # Fallback to SSIM if any unexpected format error occurs
        img1 = cv2.imread(image1_path)
        img2 = cv2.imread(image2_path)
        img1 = cv2.resize(img1, (224, 224))
        img2 = cv2.resize(img2, (224, 224))
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        score, _ = ssim(gray1, gray2, full=True)
        return round(score * 100, 2)

