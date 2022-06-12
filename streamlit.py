import numpy as np
import pandas as pd
import re
from PIL import Image
import torch
import urllib.error
from pathlib import Path
import urllib.request

import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
import streamlit as st
from torch.utils.data import DataLoader, Dataset
from matplotlib import pyplot as plt
import cv2
from albumentations.pytorch.transforms import ToTensorV2
import albumentations as A

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


device = torch.device('cpu')

@st.cache(allow_output_mutation=True, ttl=120000, max_entries=1)
def load_model():
    save_dest = Path('model')
    save_dest.mkdir(exist_ok=True)
    f_checkpoint = Path("model/fasterrcnn.pth")
    url = "https://github.com/Anubhav1107/streamlit/releases/download/fasterrcnn.pth/fasterrcnn.pth"
    if not f_checkpoint.exists():
        #filename = url.split('/')[-1]
        urllib.request.urlretrieve(url, f_checkpoint)
    WEIGHTS_FILE = Path("model/fasterrcnn.pth")
    # load a model; pre-trained on COCO
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=False, pretrained_backbone=False)
    num_classes = 2  # 1 class (wheat) + background
    # get number of input features for the classifier
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    # replace the pre-trained head with a new one
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    # Load the trained weights
    model.load_state_dict(torch.load(WEIGHTS_FILE, map_location=device))
    model.eval()
    return model


if __name__ == "__main__":
    st.header("""
    WELCOME TO Batch 7 Final Year Project!
    """)
    st.subheader('The images required for this project is in https://github.com/Anubhav1107/streamlit.')
    uploaded_file = st.file_uploader("Choose an image... (jpg only)", type="jpg")
    confidence_threshold = st.number_input('Please specify the confidence of a wheat head')
    button = st.button('Confirm')
    

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
            num_workers=0,
            drop_last=False,
            collate_fn=collate_fn
        )

        for images in test_data_loader:
            images = torch.Tensor([images[0][0], images[1][0], images[2][0]])
            images = torch.reshape(images, (3, 1024, 1024))
            images = (images,)
            images = list(image.to(device) for image in images)
            model=load_model()
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
