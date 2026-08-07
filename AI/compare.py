import cv2
from skimage.metrics import structural_similarity as ssim


def compare_images(image1_path, image2_path):

    img1 = cv2.imread(image1_path)
    img2 = cv2.imread(image2_path)

    img1 = cv2.resize(img1, (224, 224))
    img2 = cv2.resize(img2, (224, 224))

    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    score, _ = ssim(gray1, gray2, full=True)

    similarity = round(score * 100, 2)

    return similarity