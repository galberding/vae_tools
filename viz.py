#!/usr/bin/python
import matplotlib.pyplot as plt
import numpy as np
from skimage.transform import resize

# Show channels of unit8 RGB image
def image_channels(C, as_float = True):
    fig, (ax1, ax2, ax3) = plt.subplots(ncols=3)
    C = resize(C, (64, 64))
    if as_float:
        C = C.astype('float32') / 255.
    ax1.imshow(C[:,:,0])
    ax1.set_title('R')
    ax2.imshow(C[:,:,1])
    ax2.set_title('G')
    ax3.imshow(C[:,:,2])
    ax3.set_title('B')
    plt.show()


# Show image/lidar pais
def image_lidar_pair(C, L_dist, L_angle):
    fig, (ax, ax2) = plt.subplots(ncols=2)
    ax.imshow(C)
    ax.set_title('Image')
    ax2.plot(L_angle, L_dist, 'b.-')
    ax2.set_title('LiDAR')
    ax2.set_xlabel('angle (°)')
    ax2.set_ylabel('distance (m)')
    # set the aspect ratio
    asp = np.diff(ax2.get_xlim())[0] / np.diff(ax2.get_ylim())[0]
    ax2.set_aspect(asp)
    plt.show()

def get_image_dec_enc_samples(grid_x, grid_y, model_obj, image_size):
    # grid_x: latent grid vector in x direction
    # grid_y: latent grid vector in y direction
    # image_size: The image dimensions from the decoder
    nx = grid_x.shape[0]
    ny = grid_y.shape[0]
    encoder_mean = model_obj.get_encoder_mean()
    encoder_log_var = model_obj.get_encoder_logvar()
    decoder = model_obj.get_decoder()
    Dz = model_obj.latent_dim
    
    image_width = image_size[0]
    image_height = image_size[1]
    image_depth = image_size[2]
    if image_depth == 1:
        figure = np.zeros((image_height * ny, image_width * nx, 1), dtype='uint8')
    else:
        figure = np.zeros((image_height * ny, image_width * nx, 3), dtype='uint8')
    z_reencoded_mean = np.zeros(shape=(ny,nx,Dz))
    z_reencoded_std = np.zeros(shape=(ny,nx))
    # Sample  from the latent space
    for i, yi in enumerate(grid_x):
        for j, xi in enumerate(grid_y):
            z_sample = np.array([[xi, yi]])
            x_decoded = decoder.predict(z_sample)
            z_reencoded_mean[i,j,:] = encoder_mean.predict(x_decoded)
            z_reencoded_std[i,j] = np.sum(np.exp(encoder_log_var.predict(x_decoded) / 2.0))
            x_decoded_reshaped = x_decoded[0].reshape(image_width, image_height, image_depth)
            if image_depth == 1 or image_depth == 3:
                digit = 255. - x_decoded_reshaped * 255.
            elif image_depth == 2:
                digit = 255. - np.concatenate((x_decoded_reshaped, np.ones((image_width,image_height,1))), axis=2) * 255.
            else:
                assert False, "Cannot handle image depth!"
            i_corrected = nx-1-i
            figure[i_corrected * image_height: (i_corrected + 1) * image_height,
                j * image_width: (j + 1) * image_width] = digit.astype('uint8')
    return figure, z_reencoded_mean, z_reencoded_std

def random_images_from_set(X_set, image_rows_cols_chns, n):
    # n(int): how many samples are shown (it is actually nxn)
    sampleArray = np.zeros((n, n), dtype='int')
    figure = np.zeros((image_rows_cols_chns[0] * n, image_rows_cols_chns[1] * n, 3), dtype='uint8')
    for i in np.arange(0, n):
        for j in np.arange(0, n):
            sampleArray[i,j] = np.random.randint(0, high=len(X_set))
            X = X_set[sampleArray[i,j],:,:,0:2]
            if image_rows_cols_chns[2] == 1 or image_rows_cols_chns[2] == 3:
                digit = 255. - X * 255.
            else:
                digit = 255. - np.concatenate((X, np.ones((image_rows_cols_chns[0],image_rows_cols_chns[1],1))), axis=2) * 255.
            figure[i * image_rows_cols_chns[0]: (i + 1) * image_rows_cols_chns[0],
                   j * image_rows_cols_chns[1]: (j + 1) * image_rows_cols_chns[1]] = digit.astype('uint8')

    plt.figure(figsize=(15, 15))
    plt.imshow(figure)
    # plt.imshow(figure, cmap='Greys_r')
    plt.show()
    return sampleArray


def scatter_encoder(X, label, grid_x, grid_y, model_obj, batch_size = 128, figsize=(7.5, 7.5)):
    nx = grid_x.shape[0]
    ny = grid_y.shape[0]
    Z = model_obj.get_encoder_mean().predict(X, batch_size=batch_size)
    plt.figure(figsize=figsize)
    fig, (ax1, ax2) = plt.subplots(ncols=2)
    ax1.scatter(Z[:, 0], Z[:, 1], c=label)
    ax1.set_aspect("equal")
    ax2.scatter(Z[:, 0], Z[:, 1])
    ax2.scatter(np.flipud(np.matlib.repmat(grid_x,nx,1)), np.flipud(np.matlib.repmat(grid_y,ny,1).transpose()), c='r', marker='.')
    ax2.set_aspect("equal")
    plt.show()

    
    
def lidar_in_out(X_set, num_subplots, model_obj, title = "In- (blue) vs Output (red)"):
    f, axs = plt.subplots(1, num_subplots, figsize=(20,10), sharex=True, sharey=True)
    for i in np.arange(num_subplots):
        ax = axs[i]
        if not model_obj.use_conv:
            X = X_set[i,:]
        else:
            X = X_set[i,:,:]
        ax.plot(X, 'b')
        x_encoded = model_obj.get_encoder_mean().predict(np.expand_dims(X, axis=0))
        x_decoded = model_obj.get_decoder().predict(x_encoded)
        ax.plot(np.squeeze(x_decoded), 'r')
        ax.set_ylim([0.0,1.0])
        # plt.axis('off')
    f.subplots_adjust(wspace=0)
    f.suptitle(title)
    f.show()
    
def get_lidar_dec_enc_samples(grid_x, grid_y, model_obj, stride = 5, plot_mean = False):
    # grid_x: latent grid vector in x direction
    # grid_y: latent grid vector in y direction
    # model_obj: VAE network
    # stride(int): Stepsize, when to draw an decoding
    # plot_mean(bool): Plot the encoding every stride's sample
    nx = grid_x.shape[0]
    ny = grid_y.shape[0]
    encoder_mean = model_obj.get_encoder_mean()
    encoder_log_var = model_obj.get_encoder_logvar()
    decoder = model_obj.get_decoder()
    Dz = model_obj.latent_dim
    
    figures = []
    z_reencoded_mean = np.zeros(shape=(ny,nx,Dz))
    z_reencoded_std = np.zeros(shape=(ny,nx))
    # Sample  from the latent space and show the means
    figure = plt.figure()
    for y_idx, y_val in enumerate(grid_y):
        figures.append([])
        for x_idx, x_val in enumerate(grid_x):
            z_sample = np.array([[x_val, y_val]])
            x_decoded = decoder.predict(z_sample)
            z_reencoded_mean[y_idx,x_idx,:] = encoder_mean.predict(x_decoded)
            z_reencoded_std[y_idx,x_idx] = np.sum(np.exp(encoder_log_var.predict(x_decoded) / 2.0))
            figures[-1].append(x_decoded)
            if np.mod(x_idx,stride) == 0 and np.mod(y_idx,stride) == 0:
                idx = 1 + x_idx/stride + nx/stride * (ny/stride-1-y_idx/stride)
                figure.add_subplot(ny/stride, nx/stride, int(idx))
                plt.plot(x_decoded[0], 'b')
                plt.gca().set_ylim([.0,1.0])
                plt.axis('off')
    if plot_mean:
        plt.show()
    return figures, z_reencoded_mean, z_reencoded_std

def get_xy_min_max(ax):
    _ax = ax.flatten('C')
    num_axis = len(_ax)
    ylim = np.zeros((num_axis,2))
    xlim = np.zeros((num_axis,2))
    for axis_idx in np.arange(num_axis):
        ylim[axis_idx,:] = _ax[axis_idx].get_ylim()
        xlim[axis_idx,:] = _ax[axis_idx].get_xlim()
    return np.amin(ylim), np.amax(ylim), np.amin(xlim), np.amax(xlim)

def set_xy_equal_lim(ax, ylim = None, xlim = None,):
    _ax = ax.flatten('C')
    ymin, ymax, xmin, xmax = get_xy_min_max(ax)
    if ylim is None:
        ylim = (ymin, ymax) 
    if xlim is None:
        xlim = (xmin, xmax) 
    for axis in _ax:
        axis.set_xlim(xlim)
        axis.set_ylim(ylim)

def set_xy_aspect(ax):
    _ax = ax.flatten('C')
    for axis in _ax:
        asp = np.diff(axis.get_xlim())[0] / np.diff(axis.get_ylim())[0]
        axis.set_aspect(asp)

def remove_xy_ticks(ax):
    _ax = ax.flatten('C')
    # remove the x and y ticks
    for axis in _ax:
        axis.set_xticks([])
        axis.set_yticks([])