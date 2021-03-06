import numpy as np
import cv2
import glob
import time
from skimage.feature import hog
from sklearn.svm import LinearSVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.externals import joblib

# Define a function to return HOG features and visualization
def get_hog_features(img, orient, pix_per_cell, cell_per_block,
                     vis=False, feature_vec=True):
    # Call with two outputs if vis==True
    if vis == True:
        features, hog_image = hog(img, orientations=orient,
                                  pixels_per_cell=(pix_per_cell, pix_per_cell),
                                  cells_per_block=(cell_per_block, cell_per_block),
                                  transform_sqrt=True,
                                  visualise=vis, feature_vector=feature_vec)
        return features, hog_image
    # Otherwise call with one output
    else:
        features = hog(img, orientations=orient,
                       pixels_per_cell=(pix_per_cell, pix_per_cell),
                       cells_per_block=(cell_per_block, cell_per_block),
                       transform_sqrt=True,
                       visualise=vis, feature_vector=feature_vec)
        return features


# Define a function to compute binned color features
def bin_spatial(img, size=(32, 32)):
    # Use cv2.resize().ravel() to create the feature vector
    features = cv2.resize(img, size).ravel()
    # Return the feature vector
    return features

# Define a function to compute color histogram features
# NEED TO CHANGE bins_range if reading .png files with mpimg!
def color_hist(img, nbins=32, bins_range=(0, 256)):
    # Compute the histogram of the color channels separately
    channel1_hist = np.histogram(img[:, :, 0], bins=nbins, range=bins_range)
    channel2_hist = np.histogram(img[:, :, 1], bins=nbins, range=bins_range)
    channel3_hist = np.histogram(img[:, :, 2], bins=nbins, range=bins_range)
    # Concatenate the histograms into a single feature vector
    hist_features = np.concatenate((channel1_hist[0], channel2_hist[0], channel3_hist[0]))
    # Return the individual histograms, bin_centers and feature vector
    return hist_features


# Define a function to extract features from a list of images
def extract_features(imgs, color_space='RGB', spatial_size=(32, 32),
                     hist_bins=32, orient=9,
                     pix_per_cell=8, cell_per_block=2, hog_channel=0,
                     use_spatial=True, use_hist=True, use_hog=True):
    # Create a list to append feature vectors to
    features = []
    # Iterate through the list of images
    for file in imgs:
        file_features = []
        # Read in each one by one
        img = cv2.imread(file)

        # apply color conversion if other than 'RGB'
        if color_space == 'RGB':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif color_space == 'Lab':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)
        elif color_space == 'YUV':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
        elif color_space == 'YCrCb':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        elif color_space == 'HSV':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        elif color_space == 'LUV':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2LUV)
        elif color_space == 'HLS':
            feature_image = cv2.cvtColor(img, cv2.COLOR_BGR2HLS)
        else:
            feature_image = np.copy(img)

        if use_spatial == True:
            spatial_features = bin_spatial(feature_image, size=spatial_size)
            file_features.append(spatial_features)
        if use_hist == True:
            # Apply color_hist()
            hist_features = color_hist(feature_image, nbins=hist_bins)
            file_features.append(hist_features)
        if use_hog == True:
            # Call get_hog_features() with vis=False, feature_vec=True
            if hog_channel == 'ALL':
                hog_features = []
                for channel in range(feature_image.shape[2]):
                    hog_features.append(get_hog_features(feature_image[:, :, channel],
                                                         orient, pix_per_cell, cell_per_block,
                                                         vis=False, feature_vec=True))
                hog_features = np.ravel(hog_features)
            else:
                hog_features = get_hog_features(feature_image[:, :, hog_channel], orient,
                                                pix_per_cell, cell_per_block, vis=False, feature_vec=True)
            # Append the new feature vector to the features list
            file_features.append(hog_features)
        features.append(np.concatenate(file_features))
    # Return list of feature vectors
    return features

train_img_width  = 64       # Width of images in training dataset
train_img_height = 64       # Height of images in training dataset
color_space      = 'YUV'    # Can be RGB, HSV, LUV, HLS, YUV, YCrCb
orient           = 11       # HOG orientations
pix_per_cell     = 16       # HOG pixels per cell
cell_per_block   = 2        # HOG cells per block
hog_channel      = 'ALL'    # Can be 0, 1, 2, or "ALL"
spatial_size     = (16, 16) # Spatial binning dimensions
hist_bins        = 16       # Number of histogram bins
use_spatial      = False    # Spatial features on or off
use_hist         = False    # Histogram features on or off
use_hog          = True     # HOG features on or off
vehicles_dir     = './dataset/vehicles'     # Vehicle training images directory
non_vehicles_dir = './dataset/non-vehicles' # Non-vehicle training images directory
svm_model_path   = './svm_model.pkl'        # Trained classifier saved model
scaler_model_path= './scaler_model.pkl'     # Trained scaler model for classifier

if __name__ == '__main__':
    # Create empty list to store car image names
    img_names = []
    # Read in vehicles and non-vehicles
    cars = []
    for img_type in ['*.png', '*.jpg']:
        img_names.extend(glob.glob(vehicles_dir + '/**/' + img_type, recursive=True))
    for img_name in img_names:
        cars.append(img_name)
    # Delete list to append non-car images now
    del img_names[:]
    img_names = []
    notcars = []
    for img_type in ['*.png', '*.jpg']:
        img_names.extend(glob.glob(non_vehicles_dir + '/**/' + img_type, recursive=True))
    for img_name in img_names:
        notcars.append(img_name)
    print('Cars set size: ', len(cars), ' Non-cars set size: ', len(notcars))

    car_features = extract_features(cars, color_space=color_space,
                                    spatial_size=spatial_size, hist_bins=hist_bins,
                                    orient=orient, pix_per_cell=pix_per_cell,
                                    cell_per_block=cell_per_block,
                                    hog_channel=hog_channel, use_spatial=use_spatial,
                                    use_hist=use_hist, use_hog=use_hog)
    notcar_features = extract_features(notcars, color_space=color_space,
                                       spatial_size=spatial_size, hist_bins=hist_bins,
                                       orient=orient, pix_per_cell=pix_per_cell,
                                       cell_per_block=cell_per_block,
                                       hog_channel=hog_channel, use_spatial=use_spatial,
                                       use_hist=use_hist, use_hog=use_hog)
    X = np.vstack((car_features, notcar_features)).astype(np.float64)
    # Fit a per-column scaler
    X_scaler = StandardScaler().fit(X)
    # Apply the scaler to X
    scaled_X = X_scaler.transform(X)
    # Define the labels vector
    y = np.hstack((np.ones(len(car_features)), np.zeros(len(notcar_features))))

    # Split up data into randomized training and test sets
    rand_state = np.random.randint(0, 100)
    X_train, X_test, y_train, y_test = train_test_split(
        scaled_X, y, test_size=0.2, random_state=rand_state)

    print('Using:', orient, 'orientations', pix_per_cell,
          'pixels per cell and', cell_per_block, 'cells per block')
    print('Feature vector length:', len(X_train[0]))

    # Use a linear SVC
    svc = LinearSVC(C=0.01)
    # Check the training time for the SVC
    t = time.time()
    #parameters = {'kernel': ('linear', 'rbf'), 'C': range(1, 11)}
    #parameters = {'C': np.linspace(0.01,2, num = 20)}
    #svc = GridSearchCV(svc, parameters)
    svc.fit(X_train, y_train)
    t2 = time.time()
    print(round(t2 - t, 2), 'Seconds to train SVC...')
    #print('Best C: ', svc.best_params_)
    # Check the score of the SVC
    print('Test Accuracy of SVC = ', round(svc.score(X_test, y_test), 4))

    # Save classifier for later use
    joblib.dump(svc, svm_model_path)
    joblib.dump(X_scaler, scaler_model_path)
    print('SVM and Scaler model saved')

