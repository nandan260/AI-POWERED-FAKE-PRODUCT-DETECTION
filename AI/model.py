import torch
import torch.nn as nn
from torchvision import models


class FakeProductCNN(nn.Module):

    def __init__(self):
        super().__init__()

        self.model = models.mobilenet_v2(weights=None)

        # Load downloaded pretrained weights
        weights_path = r"C:\Users\nandan\Downloads\mobilenet_v2-b0353104.pth"

        state_dict = torch.load(weights_path, map_location="cpu")
        self.model.load_state_dict(state_dict)

        # Freeze feature extractor
        for param in self.model.features.parameters():
            param.requires_grad = False

        # Replace classifier
        self.model.classifier[1] = nn.Linear(
            self.model.last_channel,
            1
        )

    def forward(self, x):
        return self.model(x)