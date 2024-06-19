import os
import json
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset
import timm

class CUFED(Dataset):
    event_labels = ['Architecture', 'BeachTrip', 'Birthday', 'BusinessActivity',
                    'CasualFamilyGather', 'Christmas', 'Cruise', 'Graduation',
                    'GroupActivity', 'Halloween', 'Museum', 'NatureTrip',
                    'PersonalArtActivity', 'PersonalMusicActivity', 'PersonalSports',
                    'Protest', 'ReligiousActivity', 'Show', 'Sports', 'ThemePark',
                    'UrbanTrip', 'Wedding', 'Zoo']

    def get_album(self, album_path, album_importance, album_clip_length, img_size, transforms):
        img_score_dict = {}
        for _, image, score in album_importance:
            img_score_dict[image] = score
        album_name = os.path.basename(album_path)
        files = os.listdir(album_path)
        n_files = len(files)
        idx_fetch = np.linspace(0, n_files-1, album_clip_length, dtype=int)
        tensor_batch = []
        importance_scores = torch.zeros(len(idx_fetch))
        for i, id in enumerate(idx_fetch):
            img_name = album_name + '/' + os.path.splitext(files[id])[0]
            im = Image.open(os.path.join(album_path, files[id]))
            if transforms is not None:
                tensor_batch.append(transforms(im))
            else:
                im_resize = im.resize((img_size, img_size))
                np_img = np.array(im_resize, dtype=np.uint8)
                tensor_batch.append(torch.from_numpy(np_img).float() / 255.0)
            importance_scores[i] = img_score_dict[img_name]
        tensor_batch = torch.stack(tensor_batch)
        if transforms is None:
            tensor_batch = tensor_batch.permute(0, 3, 1, 2)   # HWC to CHW
        return tensor_batch, importance_scores

    def __init__(self, root_dir, split_dir, is_train=True, img_size=224, album_clip_length=32, ext_model=None):
        self.img_size = img_size
        self.album_clip_length = album_clip_length
        self.root_dir = root_dir

        if is_train:
            self.phase = 'train' 
        else:
            self.phase = 'test'

        if ext_model is not None:
            # get model specific transforms (normalization, resize)
            data_config = timm.data.resolve_model_data_config(ext_model)
            transforms = timm.data.create_transform(**data_config, is_training=False)
            self.transforms = transforms
        else:
            self.transforms = None

        if self.phase == 'train':
            split_path = os.path.join(split_dir, 'train_split.txt')
        else:
            split_path = os.path.join(split_dir, 'test_split.txt')

        with open(split_path, 'r') as f:
            album_names = f.readlines()
        vidname_list = [name.strip() for name in album_names]

        if '33_65073328@N00' in vidname_list:
            vidname_list.remove('33_65073328@N00') # remove weird album

        label_path = os.path.join(root_dir, "event_type.json")
        with open(label_path, 'r') as f:
            album_labels = json.load(f)

        importance_path = os.path.join(root_dir, "image_importance.json")
        with open(importance_path, 'r') as f:
            album_importance = json.load(f)

        labels_np = np.zeros((len(vidname_list), len(self.event_labels)), dtype=np.float32)
        for i, vidname in enumerate(vidname_list):
            for lbl in album_labels[vidname]:
                idx = self.event_labels.index(lbl)
                labels_np[i, idx] = 1

        self.labels = labels_np
        self.importance = album_importance
        self.videos = vidname_list
    
    def __len__(self):
        return len(self.videos)
    
    def __getitem__(self, idx):
        dataset_path = os.path.join(self.root_dir, 'images')
        album_path = os.path.join(dataset_path, self.videos[idx])
        album_importance = self.importance[self.videos[idx]]
        album_tensor, importance_scores = self.get_album(album_path, album_importance, self.album_clip_length, self.img_size, self.transforms)
        return album_tensor, self.labels[idx], importance_scores