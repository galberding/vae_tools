#!/usr/bin/python
import matplotlib.pyplot as plt
import numpy as np
from skimage.transform import resize
from PIL import Image
import sys
import os
import os.path
from glob import glob
import keras
import random
import requests

class GoogleDriveDownloader():
    def __init__(self):
        pass

    def download_file_from_google_drive(self, id, destination):
        URL = "https://docs.google.com/uc?export=download"
        if os.path.isfile(destination):
            #print("File already available")
            return
        session = requests.Session()

        response = session.get(URL, params = { 'id' : id }, stream = True)
        token = get_confirm_token(response)

        if token:
            params = { 'id' : id, 'confirm' : token }
            response = session.get(URL, params = params, stream = True)

        save_response_content(response, destination) 
        #print("Done")

    def get_confirm_token(self, response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value

        return None

    def save_response_content(self, response, destination):
        CHUNK_SIZE = 32768

        with open(destination, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    
def mnist(new_shape = (28, 28, 1), kind='digit', get_single_label = None):
    '''
    digit (str): digit or fashion
    get_single_label (int): lable between 0 .. 9
    '''
    if kind == 'digit':
        (train, train_label), (test, test_label) = keras.datasets.mnist.load_data()
    elif kind == 'fashion':
        (train, train_label), (test, test_label) = keras.datasets.fashion_mnist.load_data()
    else:
        raise
    train = train.astype('float32') / 255.
    train = train.reshape((train.shape[0],) + new_shape)
    test = test.astype('float32') / 255.
    test = test.reshape((test.shape[0],) + new_shape)
    if get_single_label is not None:
        label = get_single_label
        train = train[train_label == label, :]
        test = test[test_label == label, :]
        train_label = train_label[train_label == label]
        test_label = test_label[test_label == label]
    return train, train_label, test, test_label

def camera_lidar(filename, folder_sets, filename_camera, filename_lidar, measurements_per_file, image_shape_old, image_shape_new, lidar_shape_old, lidar_shape_new, lidar_range_max = 5., overwrite = False):
    # filename(str): Filename to store or load from
    # folder_sets(str): Folders containing npz files to load from
    filename_npz = filename + ".npz"
    if not os.path.isfile(filename_npz) or overwrite:
        # Traverse the sets of folders, while every set get one label
        num_folder_sets = len(folder_sets)
        numFolder = 0
        for idx_set in range(0, num_folder_sets):
            numFolder = numFolder + len(glob(folder_sets[idx_set]))
        measurementsPerFile = measurements_per_file
        numMeasurements = measurements_per_file * numFolder
        X = np.zeros(shape=(numMeasurements, np.prod(image_shape_old)), dtype = 'uint8')
        Y = np.zeros(shape=(numMeasurements, np.prod(lidar_shape_old)), dtype = 'float')
        label_idx = np.zeros(shape=(numMeasurements, ), dtype = 'uint8')
        label_str = list()

        # Load the raw data
        label_counter = 0
        idx = 0
        for idx_set in range(0, num_folder_sets):
            folder = glob(folder_sets[idx_set])
            num_folder_per_set = len(folder)
            for idx_folder in range(0, num_folder_per_set):
                # camera data
                tmp = np.load(folder[idx_folder] + filename_camera)
                X[idx*measurementsPerFile:(idx+1)*measurementsPerFile,:] = np.asarray( tmp['x'], dtype = 'uint8').transpose()
                # lidar data
                tmp = np.load(folder[idx_folder] + filename_lidar)
                tmp = np.asarray( tmp['x'], dtype = 'float')
                Y[idx*measurementsPerFile:(idx+1)*measurementsPerFile,:] = np.squeeze(tmp[0,:,:]).transpose()
                # label
                label_idx[idx*measurementsPerFile:(idx+1)*measurementsPerFile] = label_counter
                label_str.append(folder_sets[idx_set])
                idx = idx + 1
            label_counter = label_counter + 1

        # Resize, strip the green/blue channel ( it is alrady scaled to [0, 1] when casting to float)
        X_c = np.zeros(shape=(len(X), np.prod(image_shape_new)))
        for idx in range(0, len(X)):
            img = Image.fromarray(X[idx,:].reshape(image_shape_old))
            img = np.asarray( img.resize((image_shape_new[1], image_shape_new[0]), Image.ANTIALIAS), dtype="uint8" )
            X_c[idx,:] = img[:,:,0:image_shape_new[2]].astype('float32').reshape((np.prod(image_shape_new))) / 255.
        # Flip, strip lidar measurement which are not in the frustum of the camera, and scale to [0, 1]
        X_l = np.fliplr(Y[:,lidar_shape_new-1:2*lidar_shape_new-1]).astype('float32') / lidar_range_max
        X_l[X_l == np.inf] = 0
        np.savez_compressed(filename, X_l=X_l, X_c=X_c, label_idx=label_idx, label_str=label_str)
    else:
        loaded = np.load(filename_npz)
        X_l = loaded["X_l"]
        X_c = loaded["X_c"]
        label_idx = loaded["label_idx"]
        label_str = loaded["label_str"]
    return X_l, X_c, label_idx, label_str


def image_lidar_pair(filename_image, filename_lidar, sample):
    # tmp = np.load("2018-06-02/box_r_0.world.2018-06-02_02-16-31.bag.npz/_amiro1_sync_front_camera_image_raw-X-pixeldata.npz")
    tmp = np.load(filename_image)
    X_c = np.asarray( tmp['x'], dtype = 'uint8').transpose()
    # tmp = np.load("2018-06-02/box_r_0.world.2018-06-02_02-16-31.bag.npz/_amiro1_sync_laser_scan-X-ranges_intensities_angles.npz")
    tmp = np.load(filename_lidar)
    tmp = np.asarray( tmp['x'], dtype = 'float').transpose()
    X_l = np.squeeze(tmp[sample,:,0])
    X_l[X_l == np.inf] = 0
    return X_c[sample,:], X_l

def get_steps_around_hokuyo_center(degree_around_center = 80.):
    # The Hokuyo scans from 2.0944rad@120° to -2.0944rad@-120° with 683 steps (s.t. ~0.36°(360°/1,024 steps))
    # The camera has a hor. FoV of 80deg
    fov_hokuyo = 240
    steps_hokuyo = 683
    factor = fov_hokuyo / degree_around_center
    steps_around_center = np.int(steps_hokuyo / factor)
    angles_around_center = np.arange(start=-(steps_around_center-1)/2, stop=(steps_around_center-1)/2+1, step=1, dtype=float) * degree_around_center / steps_around_center
    return steps_around_center, angles_around_center

def overlay_sets(x_set_input, w_set_input, x_set_label_input, w_set_label_input):
    '''Overlay two data sets by their labels'''
    # reorder
    x_set_label_input_argument = np.argsort(x_set_label_input)
    w_set_label_input_argument = np.argsort(w_set_label_input)
    x_set = x_set_input[x_set_label_input_argument,:]
    w_set = w_set_input[w_set_label_input_argument,:]
    x_set_label_input = x_set_label_input[x_set_label_input_argument]
    w_set_label_input = w_set_label_input[w_set_label_input_argument]
    # cut each class to the same lenght
    x_set_idx = np.array([], dtype=np.int)
    w_set_idx = np.array([], dtype=np.int)
    for idx in np.arange(0,np.min([len(x_set), len(w_set)]), dtype=np.int):
        if x_set_label_input[idx] == w_set_label_input[idx]:
            x_set_idx = np.concatenate((x_set_idx, [idx]))
            w_set_idx = np.concatenate((w_set_idx, [idx]))
    x_set = x_set[x_set_idx,:]
    w_set = w_set[w_set_idx,:]
    x_set_label_input = x_set_label_input[x_set_idx]
    w_set_label_input = w_set_label_input[w_set_idx]
    # Check if the labels overlay
    if np.all(x_set_label_input != w_set_label_input):
        raise Exception("Labels do not overlay with each other")
    label_set = x_set_label_input
    return x_set, w_set, label_set

def mnist_digit_fashion(new_shape = (28, 28, 1), flatten = False):
    ''' Load the mnist digit and fashion data set 
    new_shape   : Desired shape of the mnist images
    flatten     : Flatten the images
    shuffle     : Shuffle the data set
    '''
    
    # Load the data
    digit_train, digit_train_label, digit_test, digit_test_label = mnist(new_shape, 'digit')
    fashion_train, fashion_train_label, fashion_test, fashion_test_label = mnist(new_shape, 'fashion')
    # Overlay train and test set
    x_train, w_train, label_train = overlay_sets(digit_train, fashion_train, digit_train_label, fashion_train_label)
    x_test, w_test, label_test = overlay_sets(digit_test, fashion_test, digit_test_label, fashion_test_label)
    
    if flatten:
        x_train = x_train.reshape((len(x_train), np.prod(x_train.shape[1:])))
        w_train = w_train.reshape((len(w_train), np.prod(w_train.shape[1:])))
        x_test = x_test.reshape((len(x_test), np.prod(x_test.shape[1:])))
        w_test = w_test.reshape((len(w_test), np.prod(w_test.shape[1:])))
    # Shuffle the training set
    shuffle_idx = np.arange(0,len(x_train))
    random.shuffle(shuffle_idx)
    x_train = x_train[shuffle_idx]
    w_train = w_train[shuffle_idx]
    return x_train, w_train, label_train, x_test, w_test, label_test
        

def emnist(flatten = False, split = 0.99):
    ''' Load the eMnist digit and fashion data set 
    flatten     : Flatten the images
    split       : Percentage of the training set
    '''
    # Download the data
    gdd = GoogleDriveDownloader()
    file_id = '1vHTjzlr6vm5rPk1BQaTnijzGzxmOxbcZ'
    destination = '/tmp/eMNSIT_CVAE_latent_dim-2_beta-4.0_epochs-100.npz'
    gdd.download_file_from_google_drive(file_id, destination)
    
    # Load the data from drive
    loaded = np.load(destination)
    x_digits = loaded['x_digits']
    x_fashion = loaded['x_fashion']
    x_label = loaded['x_label']
    x_set = x_digits
    w_set = x_fashion
    label_set = x_label
    if flatten:
        x_set = x_set.reshape((len(x_set), np.prod(x_set.shape[1:])))
        w_set = w_set.reshape((len(w_set), np.prod(w_set.shape[1:])))

    # Shuffel and define training and test sets
    shuffel_index = np.arange(len(label_set))
    random.shuffle(shuffel_index)
    w_set = w_set[shuffel_index,:]
    x_set = x_set[shuffel_index,:]
    label_set = label_set[shuffel_index]
    train_size = np.int(len(w_set) * split)
    w_train = w_set[:train_size,:]
    w_test = w_set[train_size:,:]
    x_train = x_set[:train_size,:]
    x_test = x_set[train_size:,:]
    label_train = label_set[:train_size]
    label_test = label_set[train_size:]

    return x_train, w_train, label_train, x_test, w_test, label_test
