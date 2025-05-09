# reduce size of D_i before BSP with THRESHOLD

############### import ###############
import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso, LinearRegression
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_absolute_error
from sklearn import linear_model

# from src import LR, ALR, BSP, ANN, RF, DT, SVM, KSVM
from src import EVAL, FUN

import time, sys, copy, itertools, math, warnings, argparse, json

warnings.simplefilter('ignore')
####################################################
def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv_D1", help='input csv file D1')
    parser.add_argument("input_value_D1", help='input value file D1')
    # parser.add_argument("output_pre", help='input output directory for results of preliminary experiments')
    # parser.add_argument("output_eval", help='input output file for results of evalutation experiments')
    parser.add_argument('-l', '--lasso', nargs='+', type=str)
    parser.add_argument('-rbsp', '--rbsp', nargs='+', type=str)
    parser.add_argument('-ann', '--ann', nargs='+', type=str)
    parser.add_argument('-rf', '--rf', nargs='+', type=str)
    parser.add_argument('-alr', '--alr', nargs='+', type=str)
    parser.add_argument('-dt', '--dt', nargs='+', type=str)
    parser.add_argument('-svm', '--svm', nargs='+', type=str)
    parser.add_argument('-ksvm', '--ksvm', nargs='+', type=str)

    parser.add_argument('-mlr', '--mlr', nargs='*', type=str)

    parser.add_argument('-c', '--clsf', nargs='+', type=str)   ## indicate that this is a classification task, -c bacc (use bacc for eval), -c aucroc (use aucroc for eval)
    parser.add_argument('-ec', '--errorcheck', nargs='*', type=str)   ## error check for EVAL
    parser.add_argument('-o', '--output', nargs='*', type=str)  ## output_prefix, to do

    parser.add_argument('-sb', '--sb', nargs='*', type=str)  ## status bar, use '1>' instead of '>'

    args = parser.parse_args()

    return(args) 

def read_params(params, arr, head, tail):
    for i in range(head, tail, 2):
        if arr[i + 1] == "None":
            params[arr[i]] = None
        elif arr[i + 1] == "sqrt":
            params[arr[i]] = "sqrt"
        elif "." in arr[i + 1]:
            params[arr[i]] = float(arr[i + 1])
        elif arr[i + 1].isnumeric():
            params[arr[i]] = int(arr[i + 1])
        else:
            params[arr[i]] = arr[i + 1]

    return params

def read_dataset(data_csv, value_txt):
    
    ### read files ###
    # read the csv and the observed values
    fv = pd.read_csv(data_csv) 
    value = pd.read_csv(value_txt)      

    fv_list = list(fv.columns)
    fv_list = fv_list[1:]

    ### prepare data set ###
    # prepare CIDs
    CIDs = np.array(fv['CID'])
    # prepare target, train, test arrays
    target = np.array(value['a'])
    # construct dictionary: CID to feature vector
    fv_dict = {}
    for cid,row in zip(CIDs, fv.values[:,1:]):
        fv_dict[cid] = row
    # construct dictionary: CID to target value
    target_dict = {}
    for cid, val in zip(np.array(value['CID']), np.array(value['a'])):
        target_dict[cid] = val
    # check CIDs: target_values_filename should contain all CIDs that appear in descriptors_filename
    for cid in CIDs:
        if cid not in target_dict:
            sys.stderr.write('error: {} misses the target value of CID {}\n'.format(target_values_filename, cid))
            exit(1)
    # construct x and y so that the CIDs are ordered in ascending order
    CIDs.sort()
    x = np.array([fv_dict[cid] for cid in CIDs])
    y = np.array([target_dict[cid] for cid in CIDs])

    return (CIDs,x,y,fv_list)

def read_dataset2(data_csv, value_txt, CIDs):
    
    ### read files ###
    # read the csv and the observed values
    fv = pd.read_csv(data_csv, index_col=0) 
    value = pd.read_csv(value_txt)      

    fv_list = list(fv.columns)
    # fv_list = fv_list[1:]

    # ### prepare data set ###
    # # prepare CIDs
    # CIDs = np.array(fv['CID'])
    # # prepare target, train, test arrays
    # target = np.array(value['a'])
    # # construct dictionary: CID to feature vector
    # fv_dict = {}
    # for cid,row in zip(CIDs, fv.values[:,1:]):
    #     fv_dict[cid] = row
    # # construct dictionary: CID to target value
    # target_dict = {}
    # for cid, val in zip(np.array(value['CID']), np.array(value['a'])):
    #     target_dict[cid] = val
    # # check CIDs: target_values_filename should contain all CIDs that appear in descriptors_filename
    # for cid in CIDs:
    #     if cid not in target_dict:
    #         sys.stderr.write('error: {} misses the target value of CID {}\n'.format(target_values_filename, cid))
    #         exit(1)
    # # construct x and y so that the CIDs are ordered in ascending order
    # CIDs.sort()

    x = fv.loc[CIDs]

    # x = np.array([fv_dict[cid] for cid in CIDs])
    # y = np.array([target_dict[cid] for cid in CIDs])

    return x.values, fv_list

def output_dataset(CIDs, fv_list, x, D_best, selected_fv_filename):

    x_new = pd.DataFrame(index=CIDs)
    x_new.index.name = "CID"
    for i in D_best:
        x_new[fv_list[i]] = x[:, i]

    x_new.to_csv(selected_fv_filename)

def main(args):

    params_D1 = {}
   
    try:
        way_D1 = ""
        if args.lasso is not None:
            way_D1 = "Lasso"
            params_D1["lambda"] = float(args.lasso[0])
        elif args.rbsp is not None:
            way_D1 = "BSP"
            params_D1["selected_fv_filename"] = args.rbsp[0]
        elif args.ann is not None:
            way_D1 = "ANN"
            params_D1["selected_fv_filename"] = args.ann[0]
            params_D1["rho"] = float(args.ann[1])
            params_D1["maxitr"] = int(args.ann[2])
            params_D1["arch"] = list(map(int, args.ann[3:]))
        elif args.rf is not None:
            way_D1 = "RF"
            params_D1["selected_fv_filename"] = args.rf[0]
            params_D1 = read_params(params_D1, args.rf, 1, len(args.rf))
        elif args.alr is not None:
            way_D1 = "ALR"
            params_D1["lambda"] = float(args.alr[0])
        elif args.dt is not None:
            way_D1 = "DT"
            params_D1["selected_fv_filename"] = args.dt[0]
            params_D1 = read_params(params_D1, args.dt, 1, len(args.dt))
        elif args.mlr is not None:
            way_D1 = "MLR"
        elif args.svm is not None:
            way_D1 = "SVM"
            params_D1["selected_fv_filename"] = args.svm[0]
            params_D1 = read_params(params_D1, args.svm, 1, len(args.svm))
        elif args.ksvm is not None:
            way_D1 = "KSVM"
            params_D1["selected_fv_filename"] = args.ksvm[0]
            params_D1 = read_params(params_D1, args.ksvm, 1, len(args.ksvm))
        else:
            sys.stderr.write("Please specify one learning method for D1\n")
            exit(1)

        params_D1["way"] = way_D1

        if "selected_fv_filename" in params_D1:
            CIDs_D1, x_D1, y_D1, fv_list_D1 = read_dataset(params_D1["selected_fv_filename"], args.input_value_D1)
        else:
            CIDs_D1, x_D1, y_D1, fv_list_D1 = read_dataset(args.input_csv_D1, args.input_value_D1)

        clsf_D1 = False
        if args.clsf is not None:
            clsf_D1 = True
            if args.clsf[0] == 'bacc':
                params_D1["metric"] = 'BACC'
            elif args.clsf[0] == 'aucroc':
                params_D1["metric"] = 'AUCROC'
        else:
            params_D1["metric"] = 'R2'

        metric_D1 = params_D1["metric"]


    except Exception as e:
        print(e)
        sys.stderr.write("usage: {} (input_csv_D1.csv)(input_value_D1.txt)(input_csv_D2.csv)(input_value_D2.txt)\n\n".format(sys.argv[0]))
        exit(1)

    x_D1 = x_D1.astype(np.float64)
    y_D1 = y_D1.astype(np.float64)

    # # re-normalization, only for pre
    # for eval, not here
    # min_y = np.amin(y_D1)
    # max_y = np.amax(y_D1)
    # y_D1 = (y_D1 - min_y) / (max_y - min_y)

    # min_y = np.amin(y_D2)
    # max_y = np.amax(y_D2)
    # y_D2 = (y_D2 - min_y) / (max_y - min_y)

    sp_loc = args.input_csv_D1.find('_desc_norm')
    sp_loc2 = args.input_csv_D1.rfind('/')
    if sp_loc2 == -1:
        prop_name_D1 = args.input_csv_D1[:sp_loc]
    else:
        prop_name_D1 = args.input_csv_D1[sp_loc2 + 1:sp_loc]

    nonzero_linear_org_D1 = 0
    nonzero_quadratic_org_D1 = 0
    for fv in fv_list_D1:
        if "*" in fv:
            nonzero_quadratic_org_D1 += 1
        else:
            nonzero_linear_org_D1 += 1

    time_start = time.time()

    Sbar = FUN.Status_Bar()
    Sbar.set_prop_name(f"{prop_name_D1} {way_D1}")
    # Sbar.verbose = True if args.sb is not None else False
    Sbar.verbose = True

    if clsf_D1:
        log_filename_D1 = "./log_eval/SINGLE_eval_" + prop_name_D1 + "_" + params_D1["metric"] + "_" + way_D1 + "_log.txt"
    else:
        log_filename_D1 = "./log_eval/SINGLE_eval_" + prop_name_D1 + "_" + way_D1 + "_log.txt"
    
    with open(log_filename_D1, 'w') as f:
        f.close()

    output_prefix = args.output
    if output_prefix is not None:
        output_prefix = output_prefix[0]
    R2_train_D1, R2_test_D1, sum_time_D1 = EVAL.eval_single(x_D1, y_D1, fv_list_D1, log_filename_D1, params_D1, output_prefix=output_prefix, error_check=True if args.errorcheck is not None else False, Sbar=Sbar)

    output_str = f"{prop_name_D1}\t{x_D1.shape[0]}\t{x_D1.shape[1]}\t{nonzero_linear_org_D1}\t{nonzero_quadratic_org_D1}\t"
    output_str += f"{way_D1}\t{metric_D1}\t{np.median(R2_train_D1)}\t{np.amin(R2_train_D1)}\t{np.amax(R2_train_D1)}\t"
    output_str += f"{np.median(R2_test_D1)}\t{np.amin(R2_test_D1)}\t{np.amax(R2_test_D1)}\t{sum_time_D1}\t"
    
    Sbar.finish()

    print(output_str)

if __name__ == "__main__":
    # prop = "Bp_large"
    # main((0, f"./data_var0/{prop}_var0_desc_norm.csv", f"./data_var0/{prop}_norm_values.txt"))
    # main((0, "./data_regression_var0/BHL_large_var0_theta0.001_D1_quadratic_h5000_desc_norm.csv", "./data_regression_var0/BHL_large_var0_theta0.001_D1_values.txt", "./data_regression_var0/BHL_large_var0_theta0.001_D2_quadratic_h5000_desc_norm.csv", "./data_regression_var0/BHL_large_var0_theta0.001_D2_values.txt"))
    # main(sys.argv)
    main(get_args())

