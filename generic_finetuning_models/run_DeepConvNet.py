import os
import sys
import numpy as np
import torch
import torch.nn as nn

import argparse

from easydict import EasyDict as edict
from tqdm import trange

YOUR_PATH = os.environ['YOUR_PATH']
sys.path.insert(0, os.path.join(YOUR_PATH, 'fNIRS-mental-workload-classifiers/helpers'))
import models
import brain_data
from utils import generic_GetTrainValTestSubjects, seed_everything, makedir_if_not_exist, plot_confusion_matrix, save_pickle, train_one_epoch, eval_model, save_training_curves_FixedTrainValSplit, save_training_curves_FixedTrainValSplit_overlaid, write_performance_info_FixedTrainValSplit, write_initial_test_accuracy

# from sklearn.model_selection import KFold

parser = argparse.ArgumentParser()
parser.add_argument('--seed', default=1, type=int, help="random seed")
parser.add_argument('--gpu_idx', default=0, type=int, help="gpu idx")
parser.add_argument('--data_dir', default='../data/Leon/Visual/size_40sec_200ts_stride_3ts/', help="folder to the dataset")
parser.add_argument('--window_size', default=200, type=int, help='window size')
parser.add_argument('--result_save_rootdir', default='./experiments', help="Directory containing the dataset")
parser.add_argument('--classification_task', default='four_class', help='binary or four-class classification')
parser.add_argument('--restore_file', default='None', help="xxx.statedict")
parser.add_argument('--n_epoch', default=100, type=int, help="number of epoch")
parser.add_argument('--setting', default='64vs4_TestBucket1', help='which predefined train val test split scenario')
parser.add_argument('--adapt_on', default='train_100', help="what portion of the test subject' train set is used for adaptation")


#for personal model, save the test prediction of each cv fold
def train_classifier(args_dict, test_subjects):
    
    #convert to string list
    test_subjects = [str(i) for i in test_subjects]
    
    #parse args:
    gpu_idx = args_dict.gpu_idx
    data_dir = args_dict.data_dir
    window_size = args_dict.window_size
    result_save_rootdir = args_dict.result_save_rootdir
    classification_task = args_dict.classification_task
    restore_file = args_dict.restore_file
    adapt_on = args_dict.adapt_on
    n_epoch = args_dict.n_epoch
    
    model_to_use = models.DeepConvNet150
    num_chunk_this_window_size = 1488  
    
    
    if classification_task == 'binary':
        data_loading_function = brain_data.read_subject_csv_binary
        confusion_matrix_figure_labels = ['0back', '2back']
        
#     elif classification_task == 'four_class':
#         data_loading_function = brain_data.read_subject_csv
#         confusion_matrix_figure_labels = ['0back', '1back', '2back', '3back']
        
    else:
        raise NameError('not supported classification type')
        
    
    #GPU setting
    cuda = torch.cuda.is_available()
    if cuda:
        print('Detected GPUs', flush = True)
        device = torch.device('cuda')
#         device = torch.device('cuda:{}'.format(gpu_idx))
    else:
        print('DID NOT detect GPUs', flush = True)
        device = torch.device('cpu')
    
    
    #Perform finetuning for each test subject in this bucket
    for test_subject in test_subjects:
        #load this subject's test data
        sub_feature_array, sub_label_array = data_loading_function(os.path.join(data_dir, 'sub_{}.csv'.format(test_subject)), num_chunk_this_window_size=num_chunk_this_window_size)
        
        #sainty check for this test subject's data
        sub_data_len = len(sub_label_array)
        assert sub_data_len == int(num_chunk_this_window_size/2), 'subject {} len is not {} for binary classification'.format(test_subject, int(num_chunk_this_window_size/2))
        
        half_sub_data_len = int(sub_data_len/2)
        print('half_sub_data_len: {}'.format(half_sub_data_len), flush=True)
        
        #first half of the test subject's data is train set, the second half is test set
        sub_train_feature_array = sub_feature_array[:half_sub_data_len]
        sub_train_label_array = sub_label_array[:half_sub_data_len]
        
        sub_test_feature_array = sub_feature_array[half_sub_data_len:]
        sub_test_label_array = sub_label_array[half_sub_data_len:]
        
        #study the effect of the size of the finetuning set
        if adapt_on == 'train_100':
            print('adapt on data size: {}'.format(len(sub_train_feature_array)))

        elif adapt_on == 'train_50':
            sub_train_feature_array = sub_train_feature_array[-int(0.5*half_sub_data_len):]
            print('adapt on data size: {}'.format(len(sub_train_feature_array)))
                                                    
        else:
            raise NameError('not on the predefined gride')
          
        
        #convert subject's test data into dataset object
        sub_test_set = brain_data.brain_dataset(sub_test_feature_array, sub_test_label_array)
        
        #convert subject's test dataset object into dataloader object
        test_batch_size = len(sub_test_set)
        sub_test_loader = torch.utils.data.DataLoader(sub_test_set, batch_size=test_batch_size, shuffle=False)
            
            
        #cross validation:
#         lrs = [0.001, 0.01, 0.1, 1.0, 10.0]
        lrs = [0.0001, 0.001, 0.01, 0.1, 1.0]

        dropouts = [0.25, 0.5, 0.75]

        for lr in lrs:
            for dropout in dropouts:
                experiment_name = 'lr{}_dropout{}'.format(lr, dropout)#experiment name: used for indicating hyper setting

                #derived arg
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

                result_save_dict = dict()

                total_number_train_chunks = len(sub_train_feature_array)
                total_index = np.arange(total_number_train_chunks)
                print('total number train chunks: {}'.format(total_number_train_chunks), flush=True)
                train_index = total_index[:int(total_number_train_chunks/2)]
                val_index = total_index[int(total_number_train_chunks/2):]
                
                #1-fold cv
                #dataset object
                sub_cv_train_set = brain_data.brain_dataset(sub_train_feature_array[train_index], sub_train_label_array[train_index])
                sub_cv_val_set = brain_data.brain_dataset(sub_train_feature_array[val_index], sub_train_label_array[val_index])

                #dataloader object
                cv_train_batch_size = len(sub_cv_train_set)
                cv_val_batch_size = len(sub_cv_val_set)
                sub_cv_train_loader = torch.utils.data.DataLoader(sub_cv_train_set, batch_size=cv_train_batch_size, shuffle=True) 
                sub_cv_val_loader = torch.utils.data.DataLoader(sub_cv_val_set, batch_size=cv_val_batch_size, shuffle=False)
                print('cv train set size: {}'.format(len(sub_cv_train_set)), flush=True)
                print('cv val set size: {}'.format(len(sub_cv_val_set)), flush=True)    
                    
                #create model
                model = model_to_use(dropout=dropout).to(device)
                
                #reload weights from restore_file is specified
                if restore_file != 'None':
                    restore_path = os.path.join(os.path.join(result_save_subject_checkpointdir, restore_file))
                    print('loading checkpoint: {}'.format(restore_path))
                    model.load_state_dict(torch.load(restore_path, map_location=device))
                    
                #create criterion and optimizer
                criterion = nn.NLLLoss() #for EEGNet and DeepConvNet, use nn.NLLLoss directly, which accept integer labels
                optimizer = torch.optim.Adam(model.parameters(), lr=lr) #the authors used Adam instead of SGD

                #training loop
                best_val_accuracy = 0.0    
                epoch_train_loss = []
                epoch_train_accuracy = []
                epoch_validation_accuracy = []  
                epoch_test_accuracy = []
                
                #also record the initial test accuracy
                initial_test_accuracy, _, _, _ = eval_model(model, sub_test_loader, device)
                epoch_test_accuracy.append(initial_test_accuracy)
                #write the initial test accuracy to file
                write_initial_test_accuracy(result_save_subject_resultanalysisdir, initial_test_accuracy)
                
                for epoch in trange(n_epoch, desc='1-fold cross validation'):
                    average_loss_this_epoch = train_one_epoch(model, optimizer, criterion, sub_cv_train_loader, device)
                    val_accuracy, _, _, _ = eval_model(model, sub_cv_val_loader, device)
                    test_accuracy, _, _, _ = eval_model(model, sub_test_loader, device)
                    train_accuracy, _, _ , _ = eval_model(model, sub_cv_train_loader, device)

                    epoch_train_loss.append(average_loss_this_epoch)
                    epoch_train_accuracy.append(train_accuracy)
                    epoch_validation_accuracy.append(val_accuracy)
                    epoch_test_accuracy.append(test_accuracy)

                    #update is_best flag
                    is_best = val_accuracy >= best_val_accuracy
                    
                    if is_best:
                        best_val_accuracy = val_accuracy
                        torch.save(model.state_dict(), os.path.join(result_save_subject_checkpointdir, 'best_model.statedict'))
                        test_accuracy, test_class_predictions, test_class_labels, test_logits = eval_model(model, sub_test_loader, device)
                        print('subject {} test accuracy at this epoch is {}'.format(test_subject, test_accuracy), flush=True)
                        result_save_dict['bestepoch_test_accuracy'] = test_accuracy
                        result_save_dict['bestepoch_val_accuracy'] = val_accuracy
                        result_save_dict['bestepoch_test_logits'] = test_logits.copy()
                        result_save_dict['bestepoch_test_class_labels'] = test_class_labels.copy()
                        
                #save training curve 
                save_training_curves_FixedTrainValSplit('training_curve.png', result_save_subject_trainingcurvedir, epoch_train_loss, epoch_train_accuracy, epoch_validation_accuracy, epoch_test_accuracy)
                
                #save overlaid training curve
                save_training_curves_FixedTrainValSplit_overlaid('training_curve_overlaid.png', result_save_subject_trainingcurvedir, epoch_train_loss, epoch_train_accuracy, epoch_validation_accuracy, epoch_test_accuracy)
                
                #confusion matrix 
                plot_confusion_matrix(test_class_predictions, test_class_labels, confusion_matrix_figure_labels, result_save_subject_resultanalysisdir, 'test_confusion_matrix.png')

                #save the model at last epoch
                torch.save(model.state_dict(), os.path.join(result_save_subject_checkpointdir, 'last_model.statedict'))
                
                #save result_save_dict
                save_pickle(result_save_subject_predictionsdir, 'result_save_dict.pkl', result_save_dict)
            
                #write performance to txt file
                write_performance_info_FixedTrainValSplit(model.state_dict(), result_save_subject_resultanalysisdir, result_save_dict['bestepoch_val_accuracy'], result_save_dict['bestepoch_test_accuracy'])



if __name__=='__main__':
    
    
    #parse args
    args = parser.parse_args()
    
    seed = args.seed
    gpu_idx = args.gpu_idx
    data_dir = args.data_dir
    window_size = args.window_size
    result_save_rootdir = args.result_save_rootdir
    classification_task = args.classification_task
    restore_file = args.restore_file
    adapt_on = args.adapt_on
    n_epoch = args.n_epoch
    setting = args.setting

    test_subjects, _, _ = generic_GetTrainValTestSubjects(setting)
    
    #sanity check:
    print('data_dir: {}, type: {}'.format(data_dir, type(data_dir)))
    print('window_size: {}, type: {}'.format(window_size, type(window_size)))
    print('result_save_rootdir: {}, type: {}'.format(result_save_rootdir, type(result_save_rootdir)))
    print('classification_task: {}, type: {}'.format(classification_task, type(classification_task)))
    print('restore_file: {} type: {}'.format(restore_file, type(restore_file)))
    print('n_epoch: {} type: {}'.format(n_epoch, type(n_epoch)))
    print('setting: {} type: {}'.format(setting, type(setting)))
    
    args_dict = edict() 
    
    args_dict.gpu_idx = gpu_idx
    args_dict.data_dir = data_dir
    args_dict.window_size = window_size
    args_dict.result_save_rootdir = result_save_rootdir
    args_dict.classification_task = classification_task
    args_dict.restore_file = restore_file
    args_dict.n_epoch = n_epoch
    args_dict.adapt_on = adapt_on

    
    
    seed_everything(seed)
    train_classifier(args_dict, test_subjects)
    
