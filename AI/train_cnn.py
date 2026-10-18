import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from model import FakeProductCNN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.join(BASE_DIR, "dataset", "train")
TEST_DIR = os.path.join(BASE_DIR, "dataset", "test")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("Current Working Directory:", os.getcwd())
print("Train folder exists:", os.path.exists(TRAIN_DIR))
print("Test folder exists:", os.path.exists(TEST_DIR))
print("Device:", DEVICE)


def make_loader(root, batch_size=32, shuffle=True, augment=False):
    if augment:
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
        ])
    else:
        transform = transforms.Compose([
           transforms.Resize((224,224)),
           transforms.ToTensor(),
           transforms.Normalize(
           mean=[0.485,0.456,0.406],
           std=[0.229,0.224,0.225]
),
        ])
    dataset = datasets.ImageFolder(root, transform=transform)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)
    return dataset, loader


def run_epoch(model, loader, criterion, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)

    total_loss = 0.0
    correct = 0
    total = 0

    context = torch.enable_grad() if is_train else torch.no_grad()
    with context:
        for images, labels in loader:
            images = images.to(DEVICE)
            labels = labels.float().unsqueeze(1).to(DEVICE)

            if is_train:
                optimizer.zero_grad()

            outputs = model(images)
            loss = criterion(outputs, labels)

            if is_train:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * images.size(0)
            preds = (torch.sigmoid(outputs) >= 0.5).float()
            correct += (preds == labels).sum().item()
            total += images.size(0)

    return total_loss / total, correct / total


if __name__ == "__main__": 
    train_dataset, train_loader = make_loader(TRAIN_DIR, shuffle=True, augment=True)
    test_dataset, test_loader = make_loader(TEST_DIR, shuffle=False, augment=False)

    # ImageFolder assigns class indices alphabetically: fake=0, genuine=1
    print("Class mapping:", train_dataset.class_to_idx)

    model = FakeProductCNN().to(DEVICE)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(
    model.model.classifier.parameters(),
    lr=0.0001
)   

    max_epochs = 15
    patience = 4
    best_val_loss = float("inf")
    epochs_without_improvement = 0
    best_state = None

    for epoch in range(1, max_epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = run_epoch(model, test_loader, criterion)
        print(
            f"Epoch {epoch}/{max_epochs} - "
            f"loss: {train_loss:.4f} - accuracy: {train_acc:.4f} - "
            f"val_loss: {val_loss:.4f} - val_accuracy: {val_acc:.4f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(
                    f"Early stopping at epoch {epoch} "
                    f"(no val_loss improvement for {patience} epochs)"
                )
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    model_path = os.path.join(BASE_DIR, "..", "fake_product_model.pt")
    torch.save(model.state_dict(), model_path)
    print("Model saved to", os.path.abspath(model_path))
    print("Best val_loss:", best_val_loss)
