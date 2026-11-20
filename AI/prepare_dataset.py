import os
import shutil
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Source: extracted Kaggle dataset (prashanthgolla/fake-brand-data), one
# folder per brand+label, e.g. "adidas_fake", "adidas_genuine".
SOURCE_PATH = os.path.join(BASE_DIR, "_download", "train")

# Destination
DESTINATION = os.path.join(BASE_DIR, "dataset")

TRAIN_RATIO = 0.8

# Create folders
folders = [
    "train/genuine",
    "train/fake",
    "test/genuine",
    "test/fake"
]

for folder in folders:
    os.makedirs(os.path.join(DESTINATION, folder), exist_ok=True)


genuine_images = []
fake_images = []

# Read every brand folder and collapse into genuine/fake regardless of brand
for folder in os.listdir(SOURCE_PATH):

    folder_path = os.path.join(SOURCE_PATH, folder)

    if not os.path.isdir(folder_path):
        continue

    # Decide Genuine or Fake
    if "genuine" in folder.lower():
        target_list = genuine_images
    elif "fake" in folder.lower():
        target_list = fake_images
    else:
        continue

    for image in os.listdir(folder_path):

        if image.lower().endswith((".jpg", ".jpeg", ".png")):

            target_list.append(os.path.join(folder_path, image))


# Shuffle
random.shuffle(genuine_images)
random.shuffle(fake_images)


def copy_images(images, class_name):

    split = int(len(images) * TRAIN_RATIO)

    train = images[:split]
    test = images[split:]

    # Training Images
    for i, img in enumerate(train, start=1):

        ext = os.path.splitext(img)[1]

        shutil.copy(
            img,
            os.path.join(
                DESTINATION,
                "train",
                class_name,
                f"{class_name}_{i}{ext}"
            )
        )

    # Testing Images
    for i, img in enumerate(test, start=1):

        ext = os.path.splitext(img)[1]

        shutil.copy(
            img,
            os.path.join(
                DESTINATION,
                "test",
                class_name,
                f"{class_name}_{i}{ext}"
            )
        )


if __name__ == "__main__":
    copy_images(genuine_images, "genuine")
    copy_images(fake_images, "fake")

    print("\nDataset Prepared Successfully!")
    print("Genuine Images :", len(genuine_images))
    print("Fake Images    :", len(fake_images))
