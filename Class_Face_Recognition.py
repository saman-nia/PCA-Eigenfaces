from __future__ import division
import os
import numpy as np
import cv2
import matplotlib.pyplot as plt
import bunch
import fnmatch
#-----------------------------------------------------------------------------------------------------
Data_Dir = ""
#-----------------------------------------------------------------------------------------------------
class FaceRecognition(object):
    # load images
    def __init__(self, image_path=Data_Dir, suffix="*.pgm", variance_pct=0.80, knn=5):
        self.variance_pct = variance_pct # variance percentage
        self.knn = knn
        self.image_story = [] # the original images
        image_names = []
        for root, dirnames, filenames in os.walk(image_path):
            for filename in fnmatch.filter(filenames, suffix):
                image_names.append(os.path.join(root, filename))
        for idx, image_name in enumerate(image_names):
            img = cv2.imread(image_name, cv2.IMREAD_GRAYSCALE).astype(np.float64)
            if idx == 0:
                self.imgShape = img.shape # the shape of the image.
                # the normalized image matrix
                self.vector_matrix = np.zeros((self.imgShape[0] * self.imgShape[1], len(image_names)), dtype=np.float64)
            self.image_story.append((image_name, img, self.make_label(image_name)))
            self.vector_matrix[:, idx] = img.flatten()
        subjects = set()
        for _, _, subject in self.image_story:
            subjects.add(subject)
        print("loaded all images: %d, subject number is: %d" % (len(self.image_story), len(subjects)))
        self.get_eigen()
        self.getWeight4Training()
# -----------------------------------------------------------------------------------------------------
    def make_label(self, fileName, lastSubdir=True):
        if lastSubdir:
            name = os.path.basename(os.path.dirname(fileName))
        else:
            name = os.path.basename(fileName)
        return int(name)
# -----------------------------------------------------------------------------------------------------
    def get_eigen(self):
        mean_vector = self.vector_matrix.mean(axis=1)
        for ii in range(self.vector_matrix.shape[1]):
            self.vector_matrix[:, ii] -= mean_vector
        shape = self.vector_matrix.shape
        if (shape[0] < shape[1]):
            _, lamb, u = np.linalg.svd(np.dot(self.vector_matrix, self.vector_matrix.T))
            u = u.T
        else:
            _, lamb, v = np.linalg.svd(np.dot(self.vector_matrix.T, self.vector_matrix))
            v = v.T
            u = np.dot(self.vector_matrix, v)
            norm = np.linalg.norm(u, axis=0)
            u = u / norm
        standard_deviation = lamb ** 2 / float(len(lamb))
        variance_value = standard_deviation / np.sum(standard_deviation)
        eigen = bunch.Bunch()
        eigen.lamb = lamb
        eigen.u = u
        eigen.variance_value = variance_value
        eigen.mean_vector = mean_vector
        self.eigen = eigen
        self.K = self.get_n_components_2_variance(self.variance_pct)
        print("Get the n_components to preserve variance: var=%.2f, K=%d" % (self.variance_pct, self.K))
# -----------------------------------------------------------------------------------------------------
    def reconstruct_eigenFaces(self, img, k=-1):
        if k < 0:
            k = self.K
        ws = self.getWeight4NormalizedImg(img)
        u = self.eigen.u
        imgNew = np.dot(self.eigen.u[:, 0:k], ws[0:k])
        fig, axarr = plt.subplots(1, 2)
        axarr[0].set_title("Original")
        axarr[0].imshow(img.reshape(self.imgShape) + self.get_average_weight_matrix(), cmap=plt.cm.gray)
        axarr[1].set_title("Reconstructed")
        axarr[1].imshow(imgNew.reshape(self.imgShape) + self.get_average_weight_matrix(), cmap=plt.cm.gray)
        return imgNew
# -----------------------------------------------------------------------------------------------------
    def getWeight4Training(self):
        self.weightTraining = np.dot(self.eigen.u.T, self.vector_matrix).astype(np.float32)
        return self.weightTraining
# -----------------------------------------------------------------------------------------------------
    def get_eigen_value_distribution(self):
        data = np.cumsum(self.eigen.lamb) / np.sum(self.eigen.lamb)
        return data
# -----------------------------------------------------------------------------------------------------
    def get_n_components_2_variance(self, variance=.95):
        for ii, eigen_value_cumsum in enumerate(self.get_eigen_value_distribution()):
            if eigen_value_cumsum >= variance:
                return ii
# -----------------------------------------------------------------------------------------------------
    def getWeight4NormalizedImg(self, imgNormlized):
        return np.dot(self.eigen.u.T, imgNormlized)
# -----------------------------------------------------------------------------------------------------
    def getWeight4img(self, img):
        return self.getWeight4NormalizedImg(img.flatten - self.eigen.mean_vector)
# -----------------------------------------------------------------------------------------------------
    def store_testing(self, Kpca=-1):
        test_data = self.weightTraining[0:Kpca, :].T.astype(np.float32)
        return test_data
# -----------------------------------------------------------------------------------------------------
    def get_eval(self, knn_k=-1, Kpca=-1):
        eval_data = self.eval(knn_k, Kpca)
        tp = 0
        fp = 0
        for pair in eval_data:
            if int(pair[0]) == int(pair[1]):
                tp += 1
            else:
                fp += 1
        precision = 1.0 * tp / (tp + fp)
        return precision
# -----------------------------------------------------------------------------------------------------
    def eval(self, knn_k=-1, Kpca=-1):
        response = []
        for name, img, label in self.image_story:
            response.append(label)
        responses = np.asarray(response, dtype=np.float32)
        knn = cv2.ml.KNearest_create()
        knn.train(self.weightTraining[0:Kpca, :].T.astype(np.float32), cv2.ml.ROW_SAMPLE, responses)
        ret, results, neighbours, dist = knn.findNearest(self.weightTraining[0:Kpca, :].T.astype(np.float32), knn_k)
        eval_data = []
        for idx, nb in enumerate(neighbours):
            neighbours_count = []
            for n in nb:
                neighbours_count.append(nb.tolist().count(n))
            vote = nb[neighbours_count.index(max(neighbours_count))]
            eval_data.append((vote, responses[idx]))
        return eval_data

# -----------------------------------------------------------------------------------------------------
    def get_average_weight_matrix(self):
        return np.reshape(self.eigen.mean_vector, self.imgShape)
# -----------------------------------------------------------------------------------------------------
    def visualize_eigen_vector(self, n_eigen=-1, nth=-1):
        if nth is -1:
            self.visualize_eigen_vectors(n_eigen)
        else:
            plt.figure()
            plt.imshow(np.reshape(self.eigen.u[:, nth], self.imgShape), cmap=plt.cm.gray)
# -----------------------------------------------------------------------------------------------------
    def visualize_eigen_vectors(self, number=-1):
        if number < 0:
            number = self.eigen.u.shape[1]
        num_row_x = num_row_y = int(np.floor(np.sqrt(number - 1))) + 1
        fig, axarr = plt.subplots(num_row_x, num_row_y)
        for ii in range(number):
            div, rem = divmod(ii, num_row_y)
            axarr[div, rem].imshow(np.reshape(self.eigen.u[:, ii], self.imgShape), cmap=plt.cm.gray)
            axarr[div, rem].set_title("%.6f" % self.eigen.variance_value[ii])
            axarr[div, rem].axis('off')
            if ii == number - 1:
                for jj in range(ii, num_row_x * num_row_y):
                    div, rem = divmod(jj, num_row_y)
                    axarr[div, rem].axis('off')
# -----------------------------------------------------------------------------------------------------
    def visualize_mean_vector(self):
        fig, axarr = plt.subplots()
        axarr.set_title("Compute and display the mean face.")
        axarr.imshow(self.get_average_weight_matrix(), cmap=plt.cm.gray)
# -----------------------------------------------------------------------------------------------------
    def visualize_pca_components_value(self):
        plt.figure(figsize=(14, 8))
        plt.grid(True)
        plt.xlabel('Number of Components')
        plt.ylabel('Percentage of Variance')
        plt.title("Components Value of PCA")
        plt.scatter(range(self.eigen.variance_value.size), self.eigen.variance_value, color='g')
# -----------------------------------------------------------------------------------------------------
    def visualize_eigen_value_distribution(self):
        plt.figure(figsize=(14, 8))
        plt.grid(True)
        plt.xlabel('Number of Components')
        plt.ylabel('Percentage of Variance')
        plt.title("Distribution of Eigen Value")
        data = np.cumsum(self.eigen.lamb, ) / np.sum(self.eigen.lamb)
        plt.scatter(range(data.size), data, color='r')
# -----------------------------------------------------------------------------------------------------