import torch
import torchvision.transforms.functional as F
from facenet_pytorch import InceptionResnetV1
from .pdt import PDT
import os
from torch import Tensor
from onnx2torch import convert
import sys


def find_threshold(distance_metric):
    if distance_metric == "euclidean":
        return 1.1
    if distance_metric == "euclidean_l2":
        return 1.1
    elif distance_metric == "cosine":
        return 0.4
    else:
        raise ValueError(
            f"Distance metric must be one of: 'euclidean', 'euclidean_l2', 'cosine' but got {distance_metric} instead"
        )


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_all(model_name):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if model_name == "sface":
        mean = [0.0, 0.0, 0.0]
        std = [0.5, 0.5, 0.5]

        # path_to_encoder_checkpoint = os.path.join(os.getcwd(), 'src', 'models', 'checkpoints', 'face_recognition_sface_2021dec.onnx')
        relative_path = os.path.join(
            "checkpoints", "face_recognition_sface_2021dec.onnx"
        )

        path_to_encoder_checkpoint = resource_path(relative_path)

        face_recognizer = convert(path_to_encoder_checkpoint).eval()

        path_to_translator_checkpoint = os.path.join("checkpoints", "pdt_sface.pt")

    if model_name == "facenet":
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]

        face_recognizer = InceptionResnetV1(pretrained="vggface2").eval()
        path_to_translator_checkpoint = os.path.join("checkpoints", "pdt_facenet.pt")

    face_recognizer.requires_grad_(False)
    face_recognizer.to(device)

    def transform(img):
        if not isinstance(img, Tensor):
            img = F.to_tensor(img)
        img = F.normalize(img, mean=mean, std=std)
        img = F.resize(img, (112, 112), antialias=True)  ##just added must be cleaned
        return img.unsqueeze(0)

    relative_path = resource_path(path_to_translator_checkpoint)
    checkpoint = torch.load(relative_path, map_location=torch.device(device))
    translator = PDT(pool_features=6, use_se=False, use_bias=False, use_cbam=True)
    translator.load_state_dict(checkpoint["model_state_dict"])
    translator.eval()
    translator.requires_grad_(False)
    translator.to(device)

    return transform, translator, face_recognizer
