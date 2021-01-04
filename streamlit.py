import numpy as np
import pandas as pd
import re
from PIL import Image
import torch
import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import streamlit as st
from torch.utils.data import DataLoader, Dataset
from matplotlib import pyplot as plt
import cv2
from albumentations.pytorch.transforms import ToTensorV2
import albumentations as A
from pathlib import Path
class WheatTestDataset(Dataset):
    def __init__(self, image, transforms=None):
        super().__init__()
        self.transforms = transforms
        self.image = [image]
    def __getitem__(self, index):
        image = cv2.cvtColor(np.asarray(self.image[index]), cv2.COLOR_BGR2RGB).astype(np.float32)
        # st.write('image', image)
        # image = np.asarray(self.image[index]).astype(np.float32)
        image /= 255.0
        if self.transforms:
            sample = {
                'image': image,
            }
            sample = self.transforms(**sample)
            image = sample['image']
        return np.asarray(image)
    def __len__(self) -> int:
        return len(self.image)
# Albumentations
def get_test_transform():
    return A.Compose([
        # A.Resize(512, 512),
        ToTensorV2(p=1.0)
    ])
def collate_fn(batch):
    return tuple(zip(*batch))



import urllib.request

url = 'https://zenodo.org/api/files/7f9c262a-20d1-4b10-b8ca-2e109e384c19/fasterrcnn.pth'
urllib.request.urlretrieve(url, 'faster.pth')


# @functools.lru_cache()
# def create_download_progress_bar():
#     class DownloadProgressBar(tqdm.tqdm):
#         def update_to(self, b=1, bsize=1, tsize=None):
#             if tsize is not None:
#                 self.total = tsize
#             self.update(b * bsize - self.n)

#     return DownloadProgressBar


# @retry.retry((urllib.error.HTTPError, ConnectionResetError))
# def download_with_progress(url, filepath):
#     DownloadProgressBar = create_download_progress_bar()

#     with DownloadProgressBar(
#         unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
#     ) as t:
#         urllib.request.urlretrieve(url, filepath, reporthook=t.update_to)


# def get_data_dir():
#     data_dir = pmp_config.get_config_dir().joinpath("data")
#     data_dir.mkdir(exist_ok=True)

#     return data_dir






if __name__ == "__main__":
    st.header("""
    WELCOME TO GLOBAL WHEAT HEAD CHALLENGE!
    """)
    st.subheader('Please open this website with Google Chrome.')
    uploaded_file = st.file_uploader("Choose an image... (jpg only)", type="jpg")
    confidence_threshold = st.number_input('Please specify the confidence of a wheat head')
    button = st.button('Confirm')
    
    WEIGHTS_FILE = 'faster.pth'
    # load a model; pre-trained on COCO
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=False, pretrained_backbone=False)
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    num_classes = 2  # 1 class (wheat) + background
    # get number of input features for the classifier
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # replace the pre-trained head with a new one
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    # Load the trained weights
    model.load_state_dict(torch.load(WEIGHTS_FILE, map_location=device))
    model.eval()
    detection_threshold = confidence_threshold or 0.5
    results = []
    outputs = None
    images = None
    if button and uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Image', use_column_width=True)
        st.write("")
        st.write("Detecting...")
        test_dataset = WheatTestDataset(image, get_test_transform())
        test_data_loader = DataLoader(
            test_dataset,
            batch_size=1,
            shuffle=False,
            num_workers=4,
            drop_last=False,
            collate_fn=collate_fn
        )
        for images in test_data_loader:
            images = torch.Tensor([images[0][0], images[1][0], images[2][0]])
            images = torch.reshape(images, (3, 1024, 1024))
            images = (images,)
            images = list(image.to(device) for image in images)
            outputs = model(images)
            for i, image in enumerate(images):
                boxes = outputs[i]['boxes'].data.cpu().numpy()
                scores = outputs[i]['scores'].data.cpu().numpy()
                boxes = boxes[scores >= detection_threshold].astype(np.int32)
                scores = scores[scores >= detection_threshold]
                boxes[:, 2] = boxes[:, 2] - boxes[:, 0]
                boxes[:, 3] = boxes[:, 3] - boxes[:, 1]
                for j in zip(boxes, scores):
                    result = {
                        'Detected Boxes': "{} {} {} {}".format(j[0][0], j[0][1], j[0][2], j[0][3]),
                        'Confidence%': j[1]
                    }
                    results.append(result)
    if len(results) != 0:
        # print out results
        sample = images[0].permute(1, 2, 0).cpu().numpy()
        boxes = outputs[0]['boxes'].data.cpu().numpy()
        scores = outputs[0]['scores'].data.cpu().numpy()
        boxes = boxes[scores >= detection_threshold].astype(np.int32)
        fig, ax = plt.subplots(1, 1, figsize=(16, 8))
        sample = sample.copy()
        for box in boxes:
            x1, y1, x2, y2 = box
            cv2.rectangle(sample,
                          (x1, y1),
                          (x2, y2),
                          (220, 0, 0), 2)
    
        ax.set_axis_off()
        st.image(sample,clamp=True)
        st.write("# Results")
        st.dataframe(pd.DataFrame(results))
    else:
        st.write("")
        st.write("""
        No wheat heads detected in the image!
        """)
