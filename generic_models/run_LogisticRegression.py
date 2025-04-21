import os
import sys
import numpy as np
import argparse

import time

from easydict import EasyDict as edict
from tqdm import trange
from sklearn.model_selection import KFold
from sklearn.linear_model import LogisticRegression

YOUR_PATH = os.environ['YOUR_PATH']
sys.path.insert(0, os.path.join(YOUR_PATH, 'fNIRS-mental-workload-classifiers/helpers'))
import models
import brain_data
from utils import generic_GetTrainValTestSubjects, seed_everything, featurize, makedir_if_not_exist, plot_confusion_matrix, save_pickle, write_performance_info_FixedTrainValSplit, write_program_time

parser = argparse.ArgumentParser()
parser.add_argument('--seed', default=0, type=int, help='random seed')
parser.add_argument('--data_dir', default='../data/Leon/Visual/size_2sec_10ts_stride_3ts/', help='folder to the train data')
parser.add_argument('--window_size', default=200, type=int, help='window size')
parser.add_argument('--result_save_rootdir', default='./experiments', help='folder to the result')
parser.add_argument('--classification_task', default='four_class', help='binary or four-class classification')
parser.add_argument('--setting', default='64vs4_TestBucket1', help='which predefined train val test split scenario')

def train_classifier(args_dict, train_subjects, val_subjects, test_subjects):
    
    #convert to string list
    train_subjects = [str(i) for i in train_subjects]
    val_subjects = [str(i) for i in val_subjects]
    test_subjects = [str(i) for i in test_subjects]
    
    #parse args:
    data_dir = args_dict.data_dir
    window_size = args_dict.window_size
    result_save_rootdir = args_dict.result_save_rootdir
    classification_task = args_dict.classification_task
    
    num_chunk_this_window_size = 1488

        
    if classification_task == 'binary':
        data_loading_function = brain_data.read_subject_csv_binary
        confusion_matrix_figure_labels = ['0back', '2back']
        
#     elif classification_task == 'four_class':
#         data_loading_function = brain_data.read_subject_csv
#         confusion_matrix_figure_labels = ['0back', '1back', '2back', '3back']
        
    else:
        raise NameError('not supported classification type')
        
    
    #create the group train data 
    group_model_sub_train_feature_list = []
    group_model_sub_train_label_list = []
    
    for subject in train_subjects:
        sub_feature, sub_label = data_loading_function(os.path.join(data_dir, 'sub_{}.csv'.format(subject)),  num_chunk_this_window_size=num_chunk_this_window_size)
        
        group_model_sub_train_feature_list.append(sub_feature)
        group_model_sub_train_label_list.append(sub_label)
    
    group_model_sub_train_feature_array = np.concatenate(group_model_sub_train_feature_list, axis=0).astype(np.float32)
    group_model_sub_train_label_array = np.concatenate(group_model_sub_train_label_list, axis=0)
    
    transformed_group_model_sub_train_feature_array = featurize(group_model_sub_train_feature_array, classification_task)
    
    
    #create the group val data
    group_model_sub_val_feature_list = []
    group_model_sub_val_label_list = []
    
    for subject in val_subjects:
        sub_feature, sub_label = data_loading_function(os.path.join(data_dir, 'sub_{}.csv'.format(subject)),  num_chunk_this_window_size=num_chunk_this_window_size)
        
        group_model_sub_val_feature_list.append(sub_feature)
        group_model_sub_val_label_list.append(sub_label)
    
    group_model_sub_val_feature_array = np.concatenate(group_model_sub_val_feature_list, axis=0).astype(np.float32)
    group_model_sub_val_label_array = np.concatenate(group_model_sub_val_label_list, axis=0)
    
    transformed_group_model_sub_val_feature_array = featurize(group_model_sub_val_feature_array, classification_task)

    
    #cross validation
    Cs = np.logspace(-5,5,11)

    start_time = time.time()
    
    for C in Cs:
        experiment_name = 'C{}'.format(C)
        
        #create test subjects dict
        test_subjects_dict = dict()
        for test_subject in test_subjects:
            #load this subject's test data
            sub_feature_array, sub_label_array = data_loading_function(os.path.join(data_dir, 'sub_{}.csv'.format(test_subject)), num_chunk_this_window_size=num_chunk_this_window_size)
            
            sub_data_len = len(sub_label_array)
            assert sub_data_len == int(num_chunk_this_window_size/2), 'subject {} len is not {} for binary classification'.format(test_subject, int(num_chunk_this_window_size/2))
            half_sub_data_len = int(sub_data_len/2)
            print('half_sub_data_len: {}'.format(half_sub_data_len), flush=True)
            
            sub_test_feature_array = sub_feature_array[half_sub_data_len:]
            transformed_sub_test_feature_array = featurize(sub_test_feature_array, classification_task)
            sub_test_label_array = sub_label_array[half_sub_data_len:]
            
            #create the dict for this subject: 
            #each subject's dict has: 'transformed_sub_test_feature_array', 'sub_test_label_array',
                                    # 'resutl_save_subjectdir', 'resutl_save_subject_checkpointdir', 
                                    # 'result_save_subject_predictiondir', 'result_save_subject_resultanalysisdir'
                                    # 'result_save_subject_trainingcurvedir', 'result_save_dir', 
                        
            test_subjects_dict[test_subject] = dict()
            test_subjects_dict[test_subject]['transformed_sub_test_feature_array'] = transformed_sub_test_feature_array
            test_subjects_dict[test_subject]['sub_test_label_array'] = sub_test_label_array

        
            #derived args
            result_save_subjectdir = os.path.join(result_save_rootdir, test_subject, experiment_name)
            result_save_subject_checkpointdir = os.path.join(result_save_subjectdir, 'checkpoint')
            result_save_subject_predictionsdir = os.path.join(result_save_subjectdir, 'predictions')
            result_save_subject_resultanalysisdir = os.path.join(result_save_subjectdir, 'result_analysis')
            result_save_subject_trainingcurvedir = os.path.join(result_save_subjectdir, 'trainingcurve')

            makedir_if_not_exist(result_save_subjectdir)
            makedir_if_not_exist(result_save_subject_checkpointdir)
            makedir_if_not_exist(result_save_subject_predictionsdir)
            makedir_if_not_exist(result_save_subject_resultanalysisdir)
            makedir_if_not_exist(result_save_subject_trainingcurvedir)
            
            test_subjects_dict[test_subject]['result_save_subjectdir'] = result_save_subjectdir
            test_subjects_dict[test_subject]['result_save_subject_checkpointdir'] = result_save_subject_checkpointdir
            test_subjects_dict[test_subject]['result_save_subject_predictionsdir'] = result_save_subject_predictionsdir
            test_subjects_dict[test_subject]['result_save_subject_resultanalysisdir'] = result_save_subject_resultanalysisdir
            test_subjects_dict[test_subject]['result_save_subject_trainingcurvedir'] = result_save_subject_trainingcurvedir

            test_subjects_dict[test_subject]['result_save_dict'] = dict()
            

            
        #create Logistic Regression object
        model = LogisticRegression(C=C, random_state=0, max_iter=10000, solver='lbfgs').fit(transformed_group_model_sub_train_feature_array, group_model_sub_train_label_array)

        # val performance 
        val_accuracy = model.score(transformed_group_model_sub_val_feature_array, group_model_sub_val_label_array) * 100
            
        # test performance
        for test_subject in test_subjects:
            test_subjects_dict[test_subject]['result_save_dict']['bestepoch_val_accuracy'] = val_accuracy
            test_accuracy = model.score(test_subjects_dict[test_subject]['transformed_sub_test_feature_array'], test_subjects_dict[test_subject]['sub_test_label_array']) * 100
            test_logits = model.predict_proba(test_subjects_dict[test_subject]['transformed_sub_test_feature_array'])
            test_class_predictions = test_logits.argmax(1)

            test_subjects_dict[test_subject]['result_save_dict']['bestepoch_test_accuracy'] = test_accuracy
            test_subjects_dict[test_subject]['result_save_dict']['bestepoch_test_logits'] = test_logits
            test_subjects_dict[test_subject]['result_save_dict']['bestepoch_test_class_labels'] = test_subjects_dict[test_subject]['sub_test_label_array']

            plot_confusion_matrix(test_class_predictions, test_subjects_dict[test_subject]['sub_test_label_array'], confusion_matrix_figure_labels, test_subjects_dict[test_subject]['result_save_subject_resultanalysisdir'], 'test_confusion_matrix.png')
            
            save_pickle(test_subjects_dict[test_subject]['result_save_subject_predictionsdir'], 'result_save_dict.pkl', test_subjects_dict[test_subject]['result_save_dict'])
            
            #write performance to txt file
            write_performance_info_FixedTrainValSplit('NA', test_subjects_dict[test_subject]['result_save_subject_resultanalysisdir'], val_accuracy, test_accuracy)
        
    end_time = time.time()
    total_time = end_time - start_time
    write_program_time(result_save_rootdir, total_time)
    
    
if __name__=='__main__':
    
    #parse args
    args = parser.parse_args()
    
    seed = args.seed
    data_dir = args.data_dir
    window_size = args.window_size
    result_save_rootdir = args.result_save_rootdir
    classification_task = args.classification_task
    setting = args.setting
    
    test_subjects, train_subjects, val_subjects = generic_GetTrainValTestSubjects(setting)
    
    #sanity check 
    print('data_dir: {}, type: {}'.format(data_dir, type(data_dir)))
    print('window_size: {}, type: {}'.format(window_size, type(window_size)))
    print('result_save_rootdir: {}, type: {}'.format(result_save_rootdir, type(result_save_rootdir)))
    print('classification_task: {}, type: {}'.format(classification_task, type(classification_task)))
    print('setting: {} type: {}'.format(setting, type(setting)))

    
    args_dict = edict()
    args_dict.data_dir = data_dir
    args_dict.window_size = window_size
    args_dict.result_save_rootdir = result_save_rootdir
    args_dict.classification_task = classification_task
    
    seed_everything(seed)
    train_classifier(args_dict, train_subjects, val_subjects, test_subjects)
        
            
            
            
            
    
    
    
    
    
    
    
    
    
    
    
    
    
    

