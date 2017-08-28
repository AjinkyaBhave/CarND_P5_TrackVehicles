import os
import matplotlib.pyplot as plt
from sklearn.externals import joblib
from classify_vehicles import *
from scipy.ndimage.measurements import label
from moviepy.editor import VideoFileClip

def track_vehicles(img, visualise=False):
    # Image copy to draw detected vehicle boxes after heat maps
    img_draw = np.copy(img)
    # Image copy to draw detected vehicle boxes before heat maps
    img_boxes = np.copy(img)
    # Heat map to combine multiple scale detections
    img_heat = np.zeros_like(img[:, :, 0]).astype(np.float)
    # List to store detected windows at all image scales
    all_detected_windows = []
    # Uncomment the following line if you extracted training
    # data from .png images (scaled 0 to 1 by mpimg) and the
    # image you are searching is a .jpg (scaled 0 to 255)
    # image = image.astype(np.float32)/255

    t1 = time.time()
    for i, scale in enumerate(scale_list):
        x_start = x_start_stop[i][0]
        x_stop  = x_start_stop[i][1]
        y_start = y_start_stop[i][0]
        y_stop  = y_start_stop[i][1]
        cells_per_xstep = cells_xstep_list[i]
        cells_per_ystep = cells_ystep_list[i]

        detected_windows = find_vehicles(img, scale, cells_per_xstep, cells_per_ystep,
                                         x_start, x_stop, y_start, y_stop, visualise=visualise  )
        all_detected_windows.extend(detected_windows)

    img_heat=create_heatmap(img_heat,heat_thresh, all_detected_windows)
    labels = label(img_heat)
    t2 = time.time()
    img_draw  = draw_labeled_boxes(img_draw, labels)
    img_boxes = draw_boxes(img_boxes, all_detected_windows)

    if visualise == True:
        print('Detection time: ', round(t2 - t1, 2))
        print(labels[1], 'Vehicles found')
        fig = plt.figure()
        plt.subplot(131)
        plt.imshow(img_boxes)
        plt.title('Car Boxes')
        plt.subplot(132)
        plt.imshow(img_draw)
        plt.title('Car Positions')
        plt.subplot(133)
        plt.imshow(img_heat, cmap='hot')
        plt.title('Heat Map')
        fig.tight_layout()
        plt.show()

    return img_draw

# Define a single function that can extract features using hog sub-sampling and make predictions
def find_vehicles(img, scale, cells_per_xstep, cells_per_ystep, x_start, x_stop,y_start, y_stop, visualise=False):
    # Convert image to colour space used in SVM classifier training
    img_conv = cv2.cvtColor(img, cv2.COLOR_RGB2YUV)
    img_search = img_conv[y_start:y_stop, x_start:x_stop, :]
    img_local = np.copy(img)
    img_search = cv2.resize(img_search, (np.int(img_search.shape[1] / scale),
                                             np.int(img_search.shape[0] / scale)))
    if hog_channel == 'ALL':
        ch1 = img_search[:, :, 0]
        ch2 = img_search[:, :, 1]
        ch3 = img_search[:, :, 2]

        # Compute individual channel HOG features for the entire image
        hog1 = get_hog_features(ch1, orient, pix_per_cell, cell_per_block, feature_vec=False)
        hog2 = get_hog_features(ch2, orient, pix_per_cell, cell_per_block, feature_vec=False)
        hog3 = get_hog_features(ch3, orient, pix_per_cell, cell_per_block, feature_vec=False)
    else:
        ch1 = img_search[:, :, hog_channel]
        hog1 = get_hog_features(ch1, orient, pix_per_cell, cell_per_block, feature_vec=False)

    # Define blocks in image in x and y
    nxblocks = (ch1.shape[1] // pix_per_cell) - cell_per_block + 1
    nyblocks = (ch1.shape[0] // pix_per_cell) - cell_per_block + 1

    # 64 pixels was the original training window, with 3 cells and 6 pix per cell
    window = train_img_width
    nwinblocks = (window // pix_per_cell) - cell_per_block + 1
    nxsteps = (nxblocks - nwinblocks) // cells_per_xstep
    nysteps = (nyblocks - nwinblocks) // cells_per_ystep

    if visualise == True:
        print(scale, x_start, x_stop, y_start, y_stop)
        #print('nxblocks: ', nxblocks, ' nxsteps: ', nxsteps,  )
    # Initialize a list to append window positions to
    window_list = []
    for xb in range(nxsteps):
        for yb in range(nysteps):
            # Define an empty list to receive features
            img_features = []
            ypos = yb * cells_per_ystep
            xpos = xb * cells_per_xstep
            xleft = xpos * pix_per_cell
            ytop = ypos * pix_per_cell

            if use_spatial == True or use_hist == True:
                # Extract the image patch
                subimg = cv2.resize(img_search[ytop:ytop + window, xleft:xleft + window], (train_img_height, train_img_width))
            # Get color features
            if use_spatial == True:
                spatial_features = bin_spatial(subimg, size=spatial_size)
                img_features.append(spatial_features)
            if use_hist == True:
                hist_features = color_hist(subimg, nbins=hist_bins)
                img_features.append(hist_features)
            if hog_channel == 'ALL':
                # Extract HOG for all channels in this patch
                hog_feat1 = hog1[ypos:ypos + nwinblocks, xpos:xpos + nwinblocks].ravel()
                hog_feat2 = hog2[ypos:ypos + nwinblocks, xpos:xpos + nwinblocks].ravel()
                hog_feat3 = hog3[ypos:ypos + nwinblocks, xpos:xpos + nwinblocks].ravel()
                hog_features = np.hstack((hog_feat1, hog_feat2, hog_feat3))
            else:
                # Extract HOG for single channel in this patch
                hog_features = hog1[ypos:ypos + nwinblocks, xpos:xpos + nwinblocks].ravel()
            img_features.append(hog_features)
            feature_vector = np.concatenate(img_features).astype(np.float64)
            # Scale features and make a prediction
            test_features = X_scaler.transform(feature_vector.reshape(1, -1))
            test_prediction = svc.predict(test_features)

            if test_prediction == 1:
                if visualise == True:
                    print('Confidence: ', svc.decision_function(test_features))
                if svc.decision_function(test_features) > SVC_CONF_THRESH:
                    #print('Detected Confidence: ', svc.decision_function(test_features))
                    win_scaled = np.int(window * scale)
                    startx = np.int(xleft * scale) + x_start
                    starty = np.int(ytop * scale) + y_start
                    endx = startx + win_scaled
                    endy = starty + win_scaled
                    # Append window position to list
                    window_list.append(((startx, starty), (endx, endy)))
                    if visualise == True:
                        if scale == 1:
                            colour_tuple = (0, 0, 255)
                        elif scale == 1.5:
                            colour_tuple = (255, 0, 0)
                        else:
                            colour_tuple = (0, 255, 0)
                        cv2.rectangle(img_local, (startx, starty), (endx, endy), colour_tuple, 3)
                        plt.imshow(img_local)
                        plt.show()

            '''if visualise == True and TEST_ON_VIDEO == False:
                if scale ==1:
                    colour_tuple = (0, 0, 255)
                elif scale == 1.5:
                    colour_tuple = (255, 0, 0)
                else:
                    colour_tuple = (0, 255, 0)
                win_scaled = np.int(window * scale)
                startx = np.int(xleft * scale) + x_start
                starty = np.int(ytop * scale) + y_start
                endx = startx + win_scaled
                endy = starty + win_scaled
                cv2.rectangle(img_local, (startx, starty),(endx, endy), colour_tuple, 3)
            '''
    '''if visualise == True and TEST_ON_VIDEO == False:
        plt.imshow(img_local)
        plt.show()
        plt.imshow(img_search)
        plt.show()
    '''
    return window_list

def create_heatmap(heatmap, heat_thresh, bbox_list):
    # Iterate through list of bboxes
    for box in bbox_list:
        # Add += 1 for all pixels inside each bbox
        # Assuming each "box" takes the form ((x1, y1), (x2, y2))
        heatmap[box[0][1]:box[1][1], box[0][0]:box[1][0]] += 1
        # Zero out pixels below the threshold
    heatmap[heatmap < heat_thresh] = 0
    # Return updated heatmap
    return heatmap

# Define a function to draw bounding boxes
def draw_boxes(img_draw, bboxes):
    # Iterate through the bounding boxes
    for bbox in bboxes:
        # Draw a rectangle given bbox coordinates
        cv2.rectangle(img_draw, bbox[0], bbox[1], (0, 0, 255), 3)
    # Return the image copy with boxes drawn
    return img_draw

def draw_labeled_boxes(img_draw, labels):
    # Iterate through all detected cars
    for car_number in range(1, labels[1]+1):
        # Find pixels with each car_number label value
        nonzero = (labels[0] == car_number).nonzero()
        # Identify x and y values of those pixels
        nonzeroy = np.array(nonzero[0])
        nonzerox = np.array(nonzero[1])
        # Define a bounding box based on min/max x and y
        bbox = ((np.min(nonzerox), np.min(nonzeroy)), (np.max(nonzerox), np.max(nonzeroy)))
        # Draw the box on the image
        cv2.rectangle(img_draw, bbox[0], bbox[1], (0,0,255), 3)
    # Return the image
    return img_draw

if __name__ == '__main__':
    # Paths to test images and videos
    video_input = 'test_video.mp4'
    video_output = 'test_video_output.mp4'
    img_dir = 'test_images/'
    video_img_dir = img_dir + 'test_video/'

    # Scales to search for vehicle features in image
    scale_list = [2, 1.5, 1]
    # Region in x and y to search in slide_window based on scale
    x_start_stop = [(0, 1280), (300, 1280), (300, 1280)]
    y_start_stop = [(400, 700), (400, 600), (400, 560)]
    # Overlap in cells per step x and y
    cells_xstep_list = [3, 2, 3]
    cells_ystep_list = [2, 2, 2]

    # Classifier confidence above which detection is true
    SVC_CONF_THRESH = 0.1
    # Minumum number of times a pixel is present in a bounding box set to accept detection
    heat_thresh = 1
    # Load pre-trained SVM classifier model
    svc = joblib.load(svm_model_path)
    # Load pre-trained per-column scaler
    X_scaler = joblib.load(scaler_model_path)
    print('Load SVM and Scaler')

    # Run on video file if true else run on test images
    TEST_ON_VIDEO = True

    if TEST_ON_VIDEO == True:
        # Video is at 25 FPS
        clip = VideoFileClip(video_input)
        clip_output = clip.fl_image(track_vehicles)  # NOTE: this function expects color images!!
        clip_output.write_videofile(video_output, audio=False)
    else:
        if not os.listdir(video_img_dir):
            v_start = 0
            v_end = 1
            video_times = np.linspace(v_start, v_end, 25)
            print(video_times)
            clip = VideoFileClip(video_input)
            for vt in video_times:
                video_img_file = video_img_dir + 'video{:3.3}.jpg'.format(vt)
                clip.save_frame(video_img_file, vt)

        # Read camera frames from disk
        img_files = glob.glob(video_img_dir+'video*.jpg')
        #img_files = glob.glob(img_dir + '*.jpg')
        for img_file in img_files:
            img = cv2.imread(img_file)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            track_vehicles(img, visualise=True)