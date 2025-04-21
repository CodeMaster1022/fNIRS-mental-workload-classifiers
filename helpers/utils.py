import pickle
import time
import numpy as np
import torch
import csv 
import os
import random
import logging
import shutil
import torch.nn.functional as F

from matplotlib import gridspec
import matplotlib.pyplot as plt

from sklearn.metrics import confusion_matrix as sklearn_cm
import seaborn as sns

def load_pickle(result_dir, filename):
    with open(os.path.join(result_dir, filename), 'rb') as f:
        data = pickle.load(f)
    
    return data


def save_pickle(save_dir, save_file_name, data):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    data_save_fullpath = os.path.join(save_dir, save_file_name)
    with open(data_save_fullpath, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
        
        
def makedir_if_not_exist(specified_dir):
    if not os.path.exists(specified_dir):
        os.makedirs(specified_dir)

        
def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

#Mar23
def get_slope_and_intercept(column_values, return_value = 'w'):
    
    num_timesteps = len(column_values)
    print('num_timesteps: {}'.format(num_timesteps))
    tvec_T = np.linspace(0, 1, num_timesteps) #already asserted len(column_values) = 10
    tdiff_T = tvec_T - np.mean(tvec_T)
    
    w = np.inner(column_values - np.mean(column_values), tdiff_T) / np.sum(np.square(tdiff_T))
    b = np.mean(column_values) - w * np.mean(tvec_T)
    
    if return_value == 'w':
        return w
    
    elif return_value == 'b':
        return b
    
    else:
        raise Exception("invalid return_value")
        
        
def featurize(sub_feature_array, classification_task='four_class'):
    
    num_data = sub_feature_array.shape[0]
    num_features = sub_feature_array.shape[2]
    
    assert num_features == 8 #8 features
    
    transformed_sub_feature_array = []
    for i in range(num_data):
        this_chunk_data = sub_feature_array[i]
        this_chunk_column_means = np.mean(this_chunk_data, axis=0)
        this_chunk_column_stds = np.std(this_chunk_data, axis=0)
        this_chunk_column_slopes = np.array([get_slope_and_intercept(this_chunk_data[:,i], 'w') for i in range(num_features)])
        this_chunk_column_intercepts = np.array([get_slope_and_intercept(this_chunk_data[:,i], 'b') for i in range(num_features)])
        
        this_chunk_transformed_features = np.concatenate([this_chunk_column_means, this_chunk_column_stds, this_chunk_column_slopes, this_chunk_column_intercepts])
        
        transformed_sub_feature_array.append(this_chunk_transformed_features)
    
    return np.array(transformed_sub_feature_array)


def plot_confusion_matrix(predictions, true_labels, figure_labels, save_dir, filename):
    
    sns.set(color_codes=True)
    sns.set(font_scale=1.4)
    
    plt.figure(1, figsize=(8,5))
    plt.title('Confusion Matrix')
    
    data = sklearn_cm(true_labels, predictions)
    ax = sns.heatmap(data, annot=True, fmt='d', cmap='Blues')
    
    ax.set_xticklabels(figure_labels)
    ax.set_yticklabels(figure_labels)
    ax.set(ylabel='True Label', xlabel='Predicted Label')
    ax.set_ylim([4, 0])
    
    plt.savefig(os.path.join(save_dir, filename), bbox_inches='tight', dpi=300)
    plt.close()
    

def save_training_curves_FixedTrainValSplit(figure_name, result_save_subject_trainingcurvedir, epoch_train_loss, epoch_train_accuracy=None, epoch_validation_accuracy = None, epoch_test_accuracy = None):
    
    fig = plt.figure(figsize=(15, 8))
    
    ax_1 = fig.add_subplot(1,4,1)
    ax_1.plot(range(len(epoch_train_loss)), epoch_train_loss, label='epoch_train_loss')
    
    if epoch_train_accuracy is not None:
        ax_2 = fig.add_subplot(1,4,2, sharex = ax_1)
        ax_2.plot(range(len(epoch_train_accuracy)), epoch_train_accuracy, label='epoch_train_accuracy')
        ax_2.legend()
        
    if epoch_validation_accuracy is not None:
        ax_3 = fig.add_subplot(1,4,3, sharex = ax_1)
        ax_3.plot(range(len(epoch_validation_accuracy)), epoch_validation_accuracy, label='epoch_validation_accuracy')
        ax_3.legend()
    
    if epoch_test_accuracy is not None:
        ax_4 = fig.add_subplot(1,4,4)
        ax_4.plot(range(len(epoch_test_accuracy)), epoch_test_accuracy, label='epoch_test_accuracy')
        ax_4.legend()
    
    ax_1.legend()
        
    figure_save_path = os.path.join(result_save_subject_trainingcurvedir, figure_name)
    plt.savefig(figure_save_path)
    plt.close()
    

def save_training_curves_FixedTrainValSplit_overlaid(figure_name, result_save_subject_trainingcurvedir, epoch_train_loss, epoch_train_accuracy=None, epoch_validation_accuracy = None, epoch_test_accuracy = None):
    
    fig = plt.figure(figsize=(15, 8))
    
    ax_1 = fig.add_subplot(1,2,1)
    ax_1.plot(range(len(epoch_train_loss)), epoch_train_loss, label='epoch_train_loss')
    
    ax_2 = fig.add_subplot(1,2,2)
    ax_2.plot(range(len(epoch_train_accuracy)), epoch_train_accuracy, label='epoch_train_accuracy')
    ax_2.plot(range(len(epoch_validation_accuracy)), epoch_validation_accuracy, label='epoch_validation_accuracy')
    ax_2.plot(range(len(epoch_test_accuracy)), epoch_test_accuracy, label='epoch_test_accuracy')

    ax_2.legend()
    
    ax_1.legend()
        
    figure_save_path = os.path.join(result_save_subject_trainingcurvedir, figure_name)
    plt.savefig(figure_save_path)
    plt.close()
    
    

#Aug19
def write_performance_info_FixedTrainValSplit(model_state_dict, result_save_subject_resultanalysisdir, highest_validation_accuracy, corresponding_test_accuracy):
    #create file writer
    file_writer = open(os.path.join(result_save_subject_resultanalysisdir, 'performance.txt'), 'w')
    
    #write performance to file
    file_writer.write('highest validation accuracy: {}\n'.format(highest_validation_accuracy))
    file_writer.write('corresponding test accuracy: {}\n'.format(corresponding_test_accuracy))
    #write model parameters to file
    file_writer.write('Model parameters:\n')
    
    if model_state_dict != 'NA':
        total_elements = 0
        for name, tensor in model_state_dict.items():
            file_writer.write('layer {}: {} parameters\n'.format(name, torch.numel(tensor)))
            total_elements += torch.numel(tensor)
        file_writer.write('total elemets in this model: {}'.format(total_elements))
    else:
        file_writer.write('total elemets in this model NA, sklearn model')
    
    file_writer.close()
    
def write_initial_test_accuracy(result_save_subject_resultanalysisdir, initial_test_accuracy):
    #create file writer
    file_writer = open(os.path.join(result_save_subject_resultanalysisdir, 'initial_test_accuracy.txt'), 'w')
    
    #write performance to file
    file_writer.write('initial test accuracy: {}\n'.format(initial_test_accuracy))
    
    file_writer.close()

def write_program_time(result_save_subject_resultanalysisdir, time_in_seconds):
    #create file writer
    file_writer = open(os.path.join(result_save_subject_resultanalysisdir, 'program_time.txt'), 'w')
    
    #write performance to file
    file_writer.write('program_time: {} seconds \n'.format(round(time_in_seconds,2)))
    
    file_writer.close()

def write_inference_time(result_save_subject_resultanalysisdir, time_in_seconds):
    #create file writer
    file_writer = open(os.path.join(result_save_subject_resultanalysisdir, 'inference_time.txt'), 'w')
    
    #write performance to file
    file_writer.write('program_time: {} seconds \n'.format(round(time_in_seconds,2)))
    
    file_writer.close()

    
#Aug13
def train_one_epoch(model, optimizer, criterion, train_loader, device):
    model.train()
    
    loss_avg = RunningAverage()
    for i, (data_batch, labels_batch) in enumerate(train_loader):
#         print('Inside train_one_epoch, size of data_batch is {}'.format(data_batch.shape))
        #inputs: tensor on cpu, torch.Size([batch_size, sequence_length, num_features])
        #labels: tensor on cpu, torch.Size([batch_size])
        
        data_batch = data_batch.to(device) #put inputs to device
        labels_batch = labels_batch.to(device) #when performing training, need to also put labels to device to do loss calculation and backpropagation

        #forward pass
        #outputs: tensor on gpu, requires grad, torch.Size([batch_size, num_classes])
        output_batch = model(data_batch)
        
        #calculate loss
        #loss: tensor (scalar) on gpu, torch.Size([])
        loss = criterion(output_batch, labels_batch)
        
        #update running average of the loss
        loss_avg.update(loss.item())
        
        #clear previous gradients
        optimizer.zero_grad()

        #calculate gradient
        loss.backward()
        #perform parameters update
        optimizer.step()
    
    average_loss_this_epoch = loss_avg()
    return average_loss_this_epoch


def eval_model(model, eval_loader, device):
    
    #reference: https://github.com/cs230-stanford/cs230-code-examples/blob/master/pytorch/nlp/evaluate.py
    #set the model to evaluation mode
    model.eval()
    
#     predicted_array = None # 1d numpy array, [batch_size * num_batches]
    labels_array = None # 1d numpy array, [batch_size * num_batches]
    probabilities_array = None # 2d numpy array, [batch_size * num_batches, num_classes] 
    
    for data_batch, labels_batch in eval_loader:#test_loader
        print('Inside eval_model, size of data_batch is {}'.format(data_batch.shape))
        #inputs: tensor on cpu, torch.Size([batch_size, sequence_length, num_features])
        #labels: tensor on cpu, torch.Size([batch_size])
       
        data_batch = data_batch.to(device) #put inputs to device

        #forward pass
        #outputs: tensor on gpu, requires grad, torch.Size([batch_size, num_classes])
        output_batch = model(data_batch)
        
        #extract data from torch variable, move to cpu, convert to numpy arrays    
        if labels_array is None:
#             label_array = labels.numpy()
            labels_array = labels_batch.data.cpu().numpy()
            
        else:
            labels_array = np.concatenate((labels_array, labels_batch.data.cpu().numpy()), axis=0)#np.concatenate without axis will flattened to 1d array
        
        
        if probabilities_array is None:
            probabilities_array = output_batch.data.cpu().numpy()
        else:
            probabilities_array = np.concatenate((probabilities_array, output_batch.data.cpu().numpy()), axis = 0) #concatenate on batch dimension: torch.Size([batch_size * num_batches, num_classes])
            
    class_predictions_array = probabilities_array.argmax(1)
#     print('class_predictions_array.shape: {}'.format(class_predictions_array.shape))

#     class_labels_array = onehot_labels_array.argmax(1)
    labels_array = labels_array
    accuracy = (class_predictions_array == labels_array).mean() * 100
#     accuracy = (class_predictions_array == class_labels_array).mean() * 100
    
    
    return accuracy, class_predictions_array, labels_array, probabilities_array

   
class RunningAverage():
    '''
    A class that maintains the running average of a quantity
    
    Usage example:
    loss_avg = RunningAverage()
    loss_avg.update(2)
    loss_avg.update(4)
    
    '''

    def __init__(self):
        self.steps = 0
        self.total = 0
    
    def update(self, val):
        self.total += val
        self.steps += 1
    
    def __call__(self):
        return self.total / float(self.steps)

    

def save_dict_to_json(d, json_path):
    """Saves dict of floats in josn file
    
    Args:
        d: (dict) of float-castable values (np.float, int, float, etc.)
        json_path: (string) path to json file
    """
    with open(json_path, 'w') as f:
        # We need to convert the values to float for json (it doesn't accept np.array, np.float)
        d = {k: float(v) for k, v in d.items()}
        json.dump(d, f, indent=4)
    
    

def save_checkpoint(state, is_best, checkpoint):
    """Save model and training parameters at checkpoint + 'last.pth.tar'. If is_best==True, also saves checkpoint + 'best.pth.tar'
    
    Args:
        state: (dict) contains model's state_dict, may contain other keys such as epoch, optimizer state_dict
        is_best: (bool) True if it is the best model seen till now
        checkpoint: (string) folder where parameters are to be saved
    """
    
    filepath = os.path.join(checkpoint, 'last.pth.tar')
    if not os.path.exists(checkpoint):
        print("Checkpoint Directory does not exist! Making directory {}".format(checkpoint))
        os.mkdir(checkpoint)
    
    else:
        print("Checkpoint Directory exists!")
    
    torch.save(state, filepath)
    
    if is_best:
        shutil.copyfile(filepath, os.path.join(checkpoint, 'best.pth.tar'))
    


def load_checkpoint(checkpoint, model, optimizer=None):
    """Loads model parameters (state_dict) from file_path. 
    If optimizer is provided, loads state_dict of optimizer assuming it is present in checkpoint.
    
    Args:
        checkpoint: (string) filename which needs to be loaded
        model: model for which the parameters are loaded
        optimizer: (torch.optim) optional: resume optimizer from checkpoint
    """
    
    if not os.path.exists(checkpoint):
        raise("File doesn't exist {}".format(checkpoint))
    
    checkpoint = torch.load(checkpoint)
    model.load_state_dict(checkpoint['state_dict'])
    
    if optimizer:
        optimizer.load_state_dict(checkpoint['optim_dict'])
    
    return checkpoint
    
    
def write_model_info(model_state_dict, result_save_path, file_name):
    temp_file_name = os.path.join(result_save_path, file_name)
    
    auto_file = open(temp_file_name, 'w')
    total_elements = 0
    for name, tensor in model_state_dict.items():
        total_elements += torch.numel(tensor)
        auto_file.write('\t Layer {}: {} elements \n'.format(name, torch.numel(tensor)))

        #print('\t Layer {}: {} elements'.format(name, torch.numel(tensor)))
    auto_file.write('\n total elemets in this model state_dict: {}\n'.format(total_elements))
    #print('\n total elemets in this model state_dict: {}\n'.format(total_elements))
    auto_file.close()
    

def bootstrapping(candidate_subjects, lookup_table, num_bootstrap_samples=5000, upper_percentile=97.5, lower_percentile=2.5):
    '''
    To generate 1 bootstrap sample, first sample the 71 subjects to include for this bootstrap sample.
    Then for each included subject, sample the chunk to calculate accuracy for this subject
    '''
    
    rng = np.random.RandomState(0)
    
    num_candidate_subjects = len(candidate_subjects)
    
    bootstrap_accuracy_list = [] # each element is the accuracy of this bootstrap sample (the average accuracy of the selected subjects with their selected chunks in this bootstrap sample)
    for i in range(num_bootstrap_samples):
        print('sample: {}'.format(i))
        #sample the subjects to include for this sample
        subject_location_ix = np.array(range(num_candidate_subjects))
        bootstrap_subject_location_ix = rng.choice(subject_location_ix, num_candidate_subjects, replace=True)
        bootstrap_subjects = candidate_subjects[bootstrap_subject_location_ix]
#         print('subject to include for this sample: {}'.format(bootstrap_subjects))
        
        #for each selected subject, independently resample the chunks to include (as the test set for this subject)
        subject_accuracies = []
        for subject_id in bootstrap_subjects:
            #load the test predictions (for the selected hyper setting) of this subject, and the corresponding true labels
            ResultSaveDict_this_subject_path = lookup_table.loc[lookup_table['subject_id']==subject_id].experiment_folder.values[0]
            ResultSaveDict_this_subject = load_pickle(ResultSaveDict_this_subject_path, 'predictions/result_save_dict.pkl')

            TestLogits_this_subject = ResultSaveDict_this_subject['bestepoch_test_logits']
            TrueLabels_this_subject = ResultSaveDict_this_subject['bestepoch_test_class_labels']

            #bootstrap the chunks to include for this subject (at this bootstrap sample)
            chunk_location_ix = np.array(range(len(TrueLabels_this_subject)))
            bootstrap_chunk_location_ix = rng.choice(chunk_location_ix, len(TrueLabels_this_subject), replace=True)
            bootstrap_chunks_logits = TestLogits_this_subject[bootstrap_chunk_location_ix]
            bootstrap_chunks_true_labels = TrueLabels_this_subject[bootstrap_chunk_location_ix]

            accuracy_this_subject = (bootstrap_chunks_logits.argmax(1) == bootstrap_chunks_true_labels).mean()*100

            subject_accuracies.append(accuracy_this_subject)
        
        
        average_accuracy_this_bootstrap_sample = np.mean(np.array(subject_accuracies))
        bootstrap_accuracy_list.append(average_accuracy_this_bootstrap_sample)
    
    bootstrap_accuracy_array = np.array(bootstrap_accuracy_list)
    
    accuracy_upper_percentile = np.percentile(bootstrap_accuracy_array, upper_percentile)
    accuracy_lower_percentile = np.percentile(bootstrap_accuracy_array, lower_percentile)

#     return accuracy_upper_percentile, accuracy_lower_percentile, bootstrap_accuracy_df
    return accuracy_upper_percentile, accuracy_lower_percentile


def generic_GetTrainValTestSubjects(setting):
    if setting == '64vs4_TestBucket1':
        test_subjects = [86, 56, 72, 79]
        train_subjects = [5, 40, 35, 14, 65, 49, 32, 42, 25, 15, 81, 83, 38, 34, 60, 13, 78, 57, 36, 80, 27, 20, 61, 85, 23, 54, 28, 84, 31, 1, 73, 55, 22, 92, 58, 95, 93, 29, 69, 82, 97, 45, 7, 46, 91, 75, 24, 74]
        val_subjects = [37, 63, 21, 52, 43, 94, 62, 68, 70, 64, 71, 51, 76, 44, 48, 47]
        
    elif setting == '64vs4_TestBucket2':
        test_subjects = [93, 82, 55, 48]
        train_subjects = [81, 60, 79, 29, 78, 36, 22, 51, 80, 97, 37, 71, 49, 47, 25, 62, 20, 74, 7, 84, 54, 42, 68, 70, 83, 5, 92, 24, 1, 85, 76, 86, 40, 64, 95, 69, 28, 27, 15, 14, 63, 13, 75, 23, 58, 38, 35, 34]
        val_subjects = [94, 52, 43, 44, 91, 65, 72, 31, 46, 57, 45, 32, 21, 61, 56, 73]
    
    elif setting == '64vs4_TestBucket3':
        test_subjects = [80, 14, 58, 75]
        train_subjects = [82, 1, 38, 95, 23, 86, 56, 71, 79, 72, 24, 35, 36, 43, 40, 74, 45, 92, 49, 15, 25, 73, 65, 47, 63, 64, 51, 32, 44, 97, 7, 29, 62, 52, 61, 68, 83, 57, 13, 94, 70, 27, 46, 31, 60, 54, 84, 85]
        val_subjects = [93, 78, 21, 55, 22, 48, 34, 5, 91, 81, 76, 28, 42, 20, 69, 37]
        
    elif setting == '64vs4_TestBucket4':
        test_subjects = [62, 47, 52, 84]
        train_subjects = [78, 51, 27, 49, 82, 23, 46, 85, 74, 36, 86, 25, 7, 75, 32, 79, 31, 22, 92, 28, 34, 71, 20, 65, 56, 73, 57, 1, 81, 83, 24, 58, 69, 95, 38, 91, 13, 54, 97, 42, 93, 80, 15, 35, 43, 21, 55, 72]
        val_subjects = [5, 60, 76, 40, 63, 14, 44, 37, 68, 61, 64, 29, 45, 48, 70, 94]
    
    elif setting == '64vs4_TestBucket5':
        test_subjects = [73, 69, 42, 63]
        train_subjects = [72, 97, 84, 62, 54, 29, 20, 32, 60, 35, 52, 51, 15, 45, 80, 56, 70, 81, 79, 94, 91, 28, 58, 48, 34, 55, 13, 83, 40, 27, 37, 93, 61, 57, 82, 21, 24, 47, 5, 46, 31, 43, 14, 95, 68, 25, 49, 44]
        val_subjects = [76, 75, 22, 36, 7, 86, 23, 71, 38, 64, 65, 85, 78, 74, 92, 1]
    
    elif setting == '64vs4_TestBucket6':
        test_subjects = [81, 15, 57, 70]
        train_subjects = [7, 68, 38, 29, 79, 45, 83, 76, 82, 63, 48, 13, 75, 80, 28, 93, 58, 23, 60, 43, 64, 47, 14, 49, 78, 40, 52, 36, 34, 42, 20, 94, 44, 24, 31, 25, 65, 69, 74, 37, 91, 62, 71, 95, 35, 85, 92, 55]
        val_subjects = [56, 1, 54, 27, 21, 46, 61, 86, 97, 51, 32, 84, 5, 72, 73, 22]
    
    elif setting == '64vs4_TestBucket7':
        test_subjects = [27, 92, 38, 76]
        train_subjects = [49, 82, 57, 63, 60, 23, 47, 36, 48, 5, 32, 51, 58, 70, 80, 46, 69, 34, 21, 28, 43, 83, 7, 97, 45, 13, 86, 72, 54, 24, 94, 25, 14, 40, 65, 52, 31, 15, 73, 93, 29, 55, 79, 95, 37, 62, 35, 20]
        val_subjects = [42, 84, 85, 44, 81, 56, 75, 78, 1, 61, 74, 68, 22, 64, 91, 71]
    
    elif setting == '64vs4_TestBucket8':
        test_subjects = [45, 24, 36, 71]
        train_subjects = [55, 21, 74, 28, 76, 91, 20, 93, 95, 29, 35, 34, 32, 68, 27, 40, 84, 5, 82, 38, 47, 78, 97, 75, 56, 7, 85, 62, 37, 79, 58, 72, 13, 15, 25, 42, 64, 43, 48, 44, 80, 31, 69, 70, 92, 60, 86, 46]
        val_subjects = [54, 22, 23, 65, 49, 94, 83, 81, 14, 61, 57, 73, 52, 1, 51, 63]
    
    elif setting == '64vs4_TestBucket9':
        test_subjects = [91, 85, 61, 83]
        train_subjects = [31, 60, 81, 80, 82, 1, 54, 97, 62, 45, 24, 92, 48, 74, 93, 20, 63, 84, 37, 55, 49, 7, 76, 23, 25, 40, 69, 27, 64, 43, 47, 79, 32, 14, 38, 72, 68, 65, 35, 70, 28, 13, 75, 15, 73, 5, 71, 36]
        val_subjects = [46, 34, 21, 29, 95, 51, 57, 56, 78, 94, 52, 22, 86, 58, 44, 42]
    
    elif setting == '64vs4_TestBucket10':
        test_subjects = [94, 31, 43, 54]
        train_subjects = [52, 74, 37, 25, 70, 95, 23, 47, 85, 63, 76, 7, 32, 58, 1, 14, 91, 55, 71, 83, 79, 34, 62, 40, 69, 64, 73, 27, 24, 22, 84, 13, 78, 48, 80, 92, 61, 72, 21, 29, 82, 86, 36, 51, 42, 75, 35, 56]
        val_subjects = [97, 93, 68, 45, 49, 15, 81, 65, 20, 57, 44, 60, 38, 5, 46, 28]
        
    elif setting == '64vs4_TestBucket11':
        test_subjects = [51, 64, 68, 44]
        train_subjects = [38, 61, 15, 79, 97, 36, 78, 57, 35, 28, 73, 75, 29, 43, 63, 85, 95, 86, 76, 5, 70, 58, 60, 46, 80, 65, 42, 34, 24, 21, 37, 47, 20, 32, 81, 45, 62, 56, 93, 14, 13, 49, 52, 94, 48, 55, 23, 54]
        val_subjects = [84, 91, 1, 74, 40, 7, 83, 82, 31, 27, 25, 71, 92, 72, 22, 69]
    
    elif setting == '64vs4_TestBucket12':
        test_subjects = [20, 32, 5, 49]
        train_subjects = [61, 46, 63, 79, 24, 29, 60, 57, 69, 71, 72, 43, 62, 82, 54, 45, 84, 85, 15, 65, 1, 25, 23, 73, 42, 48, 81, 7, 13, 37, 55, 22, 91, 51, 95, 38, 76, 58, 14, 75, 83, 28, 44, 64, 68, 31, 97, 52]
        val_subjects = [92, 36, 93, 47, 80, 74, 34, 86, 27, 56, 70, 78, 21, 40, 94, 35]
    
    elif setting == '64vs4_TestBucket13':
        test_subjects = [65, 28, 78, 37]
        train_subjects = [62, 84, 47, 31, 15, 42, 43, 40, 79, 48, 38, 80, 97, 45, 14, 85, 55, 75, 76, 44, 69, 29, 51, 95, 5, 25, 71, 46, 92, 56, 52, 83, 72, 61, 70, 22, 81, 74, 68, 27, 34, 94, 58, 20, 91, 63, 93, 49]
        val_subjects = [21, 86, 82, 35, 24, 13, 32, 60, 54, 64, 57, 36, 23, 7, 1, 73]
    
    elif setting == '64vs4_TestBucket14':
        test_subjects = [97, 40, 74, 46]
        train_subjects = [68, 95, 58, 1, 63, 51, 43, 85, 48, 81, 21, 86, 55, 54, 28, 7, 52, 91, 84, 22, 60, 73, 25, 20, 62, 45, 36, 70, 24, 38, 5, 29, 42, 27, 34, 44, 37, 93, 64, 72, 76, 69, 80, 47, 71, 65, 78, 13]
        val_subjects = [92, 75, 83, 35, 15, 56, 57, 61, 79, 23, 31, 82, 14, 32, 49, 94]
    
    elif setting == '64vs4_TestBucket15':
        test_subjects = [22, 7, 23, 95]
        train_subjects = [85, 70, 27, 78, 49, 24, 57, 81, 94, 65, 51, 34, 1, 54, 61, 92, 63, 68, 47, 73, 91, 80, 58, 97, 15, 45, 28, 79, 74, 83, 64, 32, 36, 14, 71, 13, 46, 84, 60, 43, 52, 48, 44, 5, 93, 69, 76, 75]
        val_subjects = [21, 56, 29, 55, 38, 82, 62, 40, 20, 37, 35, 42, 72, 31, 86, 25]
    
    elif setting == '64vs4_TestBucket16':
        test_subjects = [13, 35, 1, 34]
        train_subjects = [47, 83, 60, 81, 29, 76, 61, 94, 5, 51, 42, 48, 7, 27, 58, 21, 45, 32, 36, 92, 46, 31, 62, 57, 86, 73, 71, 84, 80, 65, 79, 64, 69, 56, 44, 68, 20, 23, 43, 54, 72, 74, 37, 93, 38, 97, 75, 78]
        val_subjects = [40, 95, 85, 52, 63, 28, 25, 15, 49, 70, 91, 24, 55, 14, 22, 82]
    
    elif setting == '64vs4_TestBucket17':
        test_subjects = [21, 25, 29, 60]
        train_subjects = [28, 36, 52, 43, 22, 44, 72, 15, 79, 75, 85, 37, 32, 38, 45, 63, 14, 97, 83, 31, 80, 73, 70, 24, 13, 20, 1, 94, 68, 93, 61, 86, 46, 64, 65, 91, 84, 54, 69, 81, 78, 55, 74, 35, 40, 49, 27, 42]
        val_subjects = [48, 56, 34, 57, 95, 62, 76, 23, 51, 47, 58, 5, 7, 92, 82, 71]
    
    elif setting == '16vs4_TestBucket1':
        test_subjects = [86, 56, 72, 79]
        train_subjects = [85, 29, 44, 25, 74, 22, 40, 75, 64, 65, 7, 76]
        val_subjects = [21, 78, 55, 62]
    
    elif setting == '16vs4_TestBucket2':
        test_subjects = [93, 82, 55, 48]
        train_subjects = [23, 28, 91, 65, 63, 56, 35, 73, 15, 20, 7, 49]
        val_subjects = [21, 86, 25, 70]
    
    elif setting == '16vs4_TestBucket3':
        test_subjects = [80, 14, 58, 75]
        train_subjects = [82, 56, 36, 72, 44, 84, 49, 63, 43, 27, 24, 69]
        val_subjects = [74, 15, 94, 22]
    
    elif setting == '16vs4_TestBucket4':
        test_subjects = [62, 47, 52, 84]
        train_subjects = [71, 34, 82, 92, 49, 60, 81, 75, 57, 46, 86, 70]
        val_subjects = [74, 51, 38, 37]
    
    elif setting == '16vs4_TestBucket5':
        test_subjects = [73, 69, 42, 63]
        train_subjects = [40, 62, 81, 27, 93, 47, 48, 97, 57, 85, 64, 60]
        val_subjects = [20, 1, 68, 24]
    
    elif setting == '16vs4_TestBucket6':
        test_subjects = [81, 15, 57, 70]
        train_subjects = [38, 13, 1, 95, 32, 68, 71, 84, 22, 43, 58, 62]
        val_subjects = [92, 47, 74, 82]
    
    elif setting == '16vs4_TestBucket7':
        test_subjects = [27, 92, 38, 76]
        train_subjects = [85, 32, 80, 91, 71, 14, 1, 49, 24, 78, 35, 34]
        val_subjects = [28, 47, 64, 94]
    
    elif setting == '16vs4_TestBucket8':
        test_subjects = [45, 24, 36, 71]
        train_subjects = [13, 76, 44, 72, 69, 70, 68, 34, 21, 84, 15, 82]
        val_subjects = [55, 97, 60, 83]
    
    elif setting == '16vs4_TestBucket9':
        test_subjects = [91, 85, 61, 83]
        train_subjects = [69, 36, 29, 31, 75, 84, 32, 28, 37, 54, 43, 49]
        val_subjects = [38, 79, 52, 14]
    
    elif setting == '16vs4_TestBucket10':
        test_subjects = [94, 31, 43, 54]
        train_subjects = [52, 58, 42, 80, 72, 68, 93, 56, 95, 44, 63, 64]
        val_subjects = [5, 14, 79, 81]
    
    elif setting == '16vs4_TestBucket11':
        test_subjects = [51, 64, 68, 44]
        train_subjects = [58, 49, 21, 93, 62, 37, 32, 71, 56, 73, 82, 97]
        val_subjects = [36, 61, 13, 45]
    
    elif setting == '16vs4_TestBucket12':
        test_subjects = [20, 32, 5, 49]
        train_subjects = [69, 40, 14, 44, 58, 37, 60, 85, 64, 68, 65, 61]
        val_subjects = [47, 76, 28, 55]
    
    elif setting == '16vs4_TestBucket13':
        test_subjects = [65, 28, 78, 37]
        train_subjects = [56, 62, 20, 72, 80, 54, 64, 70, 22, 35, 58, 74]
        val_subjects = [57, 5, 34, 43]
    
    elif setting == '16vs4_TestBucket14':
        test_subjects = [97, 40, 74, 46]
        train_subjects = [15, 34, 36, 32, 52, 42, 91, 21, 37, 20, 48, 81]
        val_subjects = [83, 69, 84, 64]
    
    elif setting == '16vs4_TestBucket15':
        test_subjects = [22, 7, 23, 95]
        train_subjects = [84, 40, 60, 48, 57, 13, 69, 37, 32, 55, 56, 21]
        val_subjects = [76, 80, 85, 75]
    
    elif setting == '16vs4_TestBucket16':
        test_subjects = [13, 35, 1, 34]
        train_subjects = [92, 29, 78, 72, 85, 80, 70, 95, 15, 24, 7, 97]
        val_subjects = [81, 52, 69, 63]
    
    elif setting == '16vs4_TestBucket17':
        test_subjects = [21, 25, 29, 60]
        train_subjects = [38, 1, 27, 62, 83, 84, 70, 24, 20, 5, 85, 52]
        val_subjects = [76, 34, 63, 86]
    
    elif setting == '4vs4_TestBucket1':
        test_subjects = [86, 56, 72, 79]
        train_subjects = [37, 76, 83]
        val_subjects = [31]
    
    elif setting == '4vs4_TestBucket2':
        test_subjects = [93, 82, 55, 48]
        train_subjects = [38, 78, 54]
        val_subjects = [47]
    
    elif setting == '4vs4_TestBucket3':
        test_subjects = [80, 14, 58, 75]
        train_subjects = [44, 82, 97]
        val_subjects = [29]
    
    elif setting == '4vs4_TestBucket4':
        test_subjects = [62, 47, 52, 84]
        train_subjects = [42, 55, 34]
        val_subjects = [46]
    
    elif setting == '4vs4_TestBucket5':
        test_subjects = [73, 69, 42, 63]
        train_subjects = [92, 60, 21]
        val_subjects = [38]
    
    elif setting == '4vs4_TestBucket6':
        test_subjects = [81, 15, 57, 70]
        train_subjects = [44, 97, 37]
        val_subjects = [72]
    
    elif setting == '4vs4_TestBucket7':
        test_subjects = [27, 92, 38, 76]
        train_subjects = [7, 14, 63]
        val_subjects = [64]
    
    elif setting == '4vs4_TestBucket8':
        test_subjects = [45, 24, 36, 71]
        train_subjects = [20, 72, 65]
        val_subjects = [58]
    
    elif setting == '4vs4_TestBucket9':
        test_subjects = [91, 85, 61, 83]
        train_subjects = [13, 47, 54]
        val_subjects = [95]
    
    elif setting == '4vs4_TestBucket10':
        test_subjects = [94, 31, 43, 54]
        train_subjects = [79, 97, 40]
        val_subjects = [82]
    
    elif setting == '4vs4_TestBucket11':
        test_subjects = [51, 64, 68, 44]
        train_subjects = [81, 80, 5]
        val_subjects = [71]
    
    elif setting == '4vs4_TestBucket12':
        test_subjects = [20, 32, 5, 49]
        train_subjects = [37, 14, 71]
        val_subjects = [52]
    
    elif setting == '4vs4_TestBucket13':
        test_subjects = [65, 28, 78, 37]
        train_subjects = [63, 32, 84]
        val_subjects = [31]
    
    elif setting == '4vs4_TestBucket14':
        test_subjects = [97, 40, 74, 46]
        train_subjects = [71, 63, 45]
        val_subjects = [81]
    
    elif setting == '4vs4_TestBucket15':
        test_subjects = [22, 7, 23, 95]
        train_subjects = [54, 80, 57]
        val_subjects = [55]
    
    elif setting == '4vs4_TestBucket16':
        test_subjects = [13, 35, 1, 34]
        train_subjects = [82, 86, 15]
        val_subjects = [61]
    
    elif setting == '4vs4_TestBucket17':
        test_subjects = [21, 25, 29, 60]
        train_subjects = [80, 85, 69]
        val_subjects = [23]
    else:
        raise NameError('not supported setting')

    return test_subjects, train_subjects, val_subjects


def SubgroupAnalysisAsian_GetTrainValTestSubjects(setting):
    
    if setting == 'random_partition1':
        train_subjects = [72, 68, 27, 75, 52, 46, 65, 71, 73, 63, 74, 44, 81, 13, 54, 84, 55, 37, 51, 7]
        val_subjects = [56, 57, 24, 43, 25, 61]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [85, 38, 42, 29, 48, 40]
        test_subjects_ASIAN = [5, 76, 93, 49, 94, 35]
    
    elif setting == 'random_partition2':
        train_subjects = [27, 84, 7, 49, 68, 37, 76, 71, 72, 56, 5, 93, 55, 52, 94, 46, 61, 81, 74, 43]
        val_subjects = [65, 25, 51, 13, 63, 75]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [80, 15, 82, 29, 32, 92]
        test_subjects_ASIAN = [54, 44, 35, 73, 24, 57]

    elif setting == 'random_partition3':
        train_subjects = [55, 25, 71, 24, 68, 49, 46, 13, 44, 5, 65, 54, 84, 61, 63, 7, 27, 74, 43, 73]
        val_subjects = [72, 76, 51, 57, 75, 81]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [79, 95, 31, 32, 92, 34]
        test_subjects_ASIAN = [94, 56, 93, 35, 37, 52]
    
    elif setting == 'random_partition4':
        train_subjects = [25, 63, 56, 74, 72, 76, 7, 24, 46, 43, 5, 13, 71, 44, 51, 52, 27, 94, 55, 81]
        val_subjects = [57, 37, 68, 75, 54, 65]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [42, 32, 14, 95, 92, 97]
        test_subjects_ASIAN = [61, 84, 73, 93, 49, 35]
    
    else:
        raise NameError('not supported setting')
    
    return  train_subjects, val_subjects, test_subjects_URG, test_subjects_WHITE, test_subjects_ASIAN


def SubgroupAnalysisWhite_GetTrainValTestSubjects(setting):
    
    if setting == 'random_partition1':
        train_subjects = [38, 45, 21, 31, 48, 14, 34, 91, 42, 29, 20, 85, 36, 23, 86, 79]
        val_subjects = [32, 95, 40, 82, 47]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [64, 69, 80, 92, 97, 15]
        test_subjects_ASIAN = [25, 7, 54, 24, 37, 94]
    
    elif setting == 'random_partition2':
        train_subjects = [97, 92, 38, 47, 48, 32, 69, 45, 15, 64, 91, 79, 95, 42, 14, 31]
        val_subjects = [86, 40, 21, 80, 23]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [36, 85, 34, 82, 29, 20]
        test_subjects_ASIAN = [55, 76, 56, 24, 13, 93]
    
    elif setting == 'random_partition3':
        train_subjects = [92, 36, 14, 21, 64, 47, 42, 32, 91, 85, 15, 45, 38, 80, 95, 23]
        val_subjects = [29, 40, 31, 82, 48]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [34, 97, 86, 20, 79, 69]
        test_subjects_ASIAN = [49, 57, 43, 7, 56, 61]
    
    elif setting == 'random_partition4':
        train_subjects = [21, 47, 92, 40, 36, 97, 48, 20, 91, 38, 82, 64, 23, 42, 79, 95]
        val_subjects = [80, 29, 15, 45, 14]
        test_subjects_URG = [22, 70, 78, 28, 60, 58]
        test_subjects_WHITE = [69, 85, 34, 31, 86, 32]
        test_subjects_ASIAN = [51, 25, 44, 65, 52, 56]
    
    else:
        raise NameError('not supported setting')
    
    return  train_subjects, val_subjects, test_subjects_URG, test_subjects_WHITE, test_subjects_ASIAN

