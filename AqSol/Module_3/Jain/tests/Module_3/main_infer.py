"""
multi-model 
"""
import sys
import time
import subprocess
import pulp

from Module_3.libs.ANN.infer_2LMM_ANN import ANN_add_vars_constraints_to_MILP
from Module_3.libs.LR.infer_2LMM_LLR import LR_add_vars_constraints_to_MILP
from Module_3.libs.RF.infer_2LMM_RF import RF_add_vars_constraints_to_MILP
from Module_3.libs.Function.twolayered_MILP_2LMM_L import print_sdf_file, print_gstar_file
from Module_3.libs.Function.create_base_MILP import create_base_MILP

from Module_3.libs.ANN import ann_inverter
from Module_3.libs.LR import lr_inverter
from Module_3.libs.RF import rf_inverter

from Module_3.libs.Class.InputConfiguration import Config

####################################################
# IMPORTANT:
# Please specify the path of the cplex solver here
CPLEX_PATH = "C:/Program Files/IBM/ILOG/CPLEX_Studio2211/cplex/bin/x64_win64/cplex.exe"
#CPLEX_PATH="C:/Program Files/IBM/ILOG/CPLEX_Studio2211/cplex/bin/x64_win64/cplex.exe"
# CPLEX_PATH= \
# "/opt/cplex_12.10/cplex/bin/x86-64_linux/cplex"

CPLEX_MSG = False
CPLEX_TIMELIMIT = 600
CPLEX_LOG_PATH = "./logs/cplex.log"
SOLVER_CASE = 1  # change 1 to 2 if use CBC solver
STD_EPS = 1e-5
# file of fv generator used to generate fv to check
FV_GEN_NAME = "./libs/2LMM_v019/FV_2LMM_V019.exe"
####################################################

# def infer(argv):
def infer(config_filename: str):
    start = time.time()
    config: Config = Config(config_filename)
    ## Create MILP
    MILP = pulp.LpProblem("MultiModel")
    base_var: tuple = create_base_MILP(
        MILP, config.instance_file, config.fringe_tree_file
    )
    milp_results: list = [()] * len(config.input_data)
    print("Input data:")
    for index, item in enumerate(config.input_data):
        print("\tindex:", index)
        if item["model"] == "ANN":
            print("\tmodel: ANN")
            milp_results[index] = ANN_add_vars_constraints_to_MILP(config, index, MILP, base_var)
        elif item["model"] == "LR":
            print("\tmodel: LR")
            milp_results[index] = LR_add_vars_constraints_to_MILP(config, index, MILP, base_var)
        elif item["model"] == "RF":
            print("\tmodel: RF")
            milp_results[index] = RF_add_vars_constraints_to_MILP(config, index, MILP, base_var)
        else:
            print(f"\tmodel {item['model']} not supported")
            sys.exit(1)
        print()

    ########## solve and output ##########
    # Output all MILP variables and constraints
    MILP.writeLP(config.output_prefix + ".lp")

    init_end = time.time()
    print("Initializing Time:", f"{init_end - start:.3f}")

    num_vars = len(MILP.variables())
    num_ints = len([var for var in MILP.variables() if var.cat == pulp.LpInteger])
    bins = [v.name for v in MILP.variables()
                                if (v.cat == pulp.LpBinary or
                                (v.cat == "Integer" and
                                v.upBound and v.lowBound is not None and
                                round(v.upBound - v.lowBound) == 1))]

    num_constraints = len(MILP.constraints.items())

    print("Number of variables:", num_vars)
    print(" - Integer :", num_ints)
    print(" - Binary  :", len(bins))
    print("Number of constraints:", num_constraints, end="\n\n", flush=True)
    
    # Solve MILP
    if SOLVER_CASE == 1:
        if CPLEX_TIMELIMIT > 0:
            cplex = pulp.CPLEX(
                path=CPLEX_PATH, msg=CPLEX_MSG, timeLimit=CPLEX_TIMELIMIT,
            )
        else:
            cplex = pulp.CPLEX(
                path=CPLEX_PATH, msg=CPLEX_MSG, 
            )
        try:
            MILP.solve(cplex)
        except Exception as ex:
            print(f"Error: {ex}")
        solve_end = time.time()
    else:
        MILP.solve()
        solve_end = time.time()
        
    # Output result of solving MILP to command-line
    if pulp.LpStatus[MILP.status] == "Optimal":
        output_status = "Feasible"
    else:
        output_status = pulp.LpStatus[MILP.status]
    print("Status:", output_status)

    if pulp.LpStatus[MILP.status] == "Optimal":
        for index, item in enumerate(config.input_data):
            if item["model"] == "ANN":
                y, y_min, y_max, _, _, _ = milp_results[index]
                y_star = y.value()
                y_star_scaled = y_star * (y_max - y_min) + y_min
                print("index", index, " y*:", f"{y_star_scaled:.3f}")
            elif item["model"] == "LR":
                y, y_min, y_max, _, _, _, _ = milp_results[index]
                y_star = y.value()
                y_star_scaled = y_star * (y_max - y_min) + y_min
                print("index", index, " y*:", f"{y_star_scaled:.3f}")
            elif item["model"] == "RF":
                y, y_min, y_max, _, _, _, _ = milp_results[index]
                y_star = y.value()
                y_star_scaled = y_star * (y_max - y_min) + y_min
                print("index", index, " y*:", f"{y_star_scaled:.3f}")
    print()
    print("Solving Time:", f"{solve_end - init_end:.3f}", end="\n\n", flush=True)

    ############################################
    # The following block of code is used to print out the value of feature vector #
    # and the value of all variables used in MILP in to a file "test.txt" #
    ############################################
    with open(config.output_prefix + "_test_all.txt", "w") as file:
        for var in MILP.variables():
            if isinstance(var, dict):
                for x in var:
                    if var[x].value() is None:
                        pass
                    elif abs(var[x].value()) > 0.0000001:
                        file.write(f"{var[x].name}: {var[x].value()}\n")
            elif var.value() is None:
                pass
            elif abs(var.value()) > 0.0000001:
                file.write(f"{var.name}: {var.value()}\n")

        file.write("\n")

    ##############################################

    if pulp.LpStatus[MILP.status] == "Optimal":
        strF, Lambda_int, Lambda_ex, Gamma_int, Gamma_int_less, Gamma_int_equal, Gamma_lf_ac, \
        n_G, n_G_int, MASS, dg, dg_int, bd_int, na_int, na_ex, ec_int, fc, ac_lf, rank_G, mass_n, \
        t_C, t_T, t_F, t_C_tilde, n_C, n_T, n_F, c_F, Lambda, \
        head_C, tail_C, I_equal_one, I_zero_one, I_ge_one, I_ge_two, set_F, Code_F, \
        v_T, v_F, alpha_C, alpha_T, alpha_F, \
        beta_C, beta_T, beta_F, beta_CT, beta_TC, beta_CF, beta_TF, chi_T, chi_F, \
        e_T, e_F, delta_fr_C, delta_fr_T, delta_fr_F, \
        E_C, ch_LB, ch_UB, \
        set_F_v, set_F_E = base_var

        # Output SDF file
        outputfilename = config.output_prefix + ".sdf"
    
        index_C, index_T, graph_adj, graph_ind = print_sdf_file(
            t_C, t_T, t_F, t_C_tilde, n_C, n_T, n_F, c_F, Lambda, Lambda_int, Lambda_ex,
            head_C, tail_C, I_equal_one, I_zero_one, I_ge_one, I_ge_two, set_F, Code_F,
            n_G, v_T, v_F, alpha_C, alpha_T, alpha_F,
            beta_C, beta_T, beta_F, beta_CT, beta_TC, beta_CF, beta_TF, chi_T, chi_F,
            e_T, e_F, delta_fr_C, delta_fr_T, delta_fr_F,
            outputfilename,
        )
        
        # Output file of partition
        outputfilename = config.output_prefix + "_partition.txt"

        print_gstar_file(
            graph_ind, chi_T,
            t_C, t_T, index_C, index_T, graph_adj, E_C, ch_LB, ch_UB,
            I_ge_one, I_ge_two, I_zero_one, I_equal_one,
            set_F_v, set_F_E,
            outputfilename,
        )

        ## Check the calculated descriptors
        check_calculated_descriptors(config, milp_results)

    print(f"DONE: {config.output_prefix} ({output_status}) in {time.time() - start:.3f} seconds", flush=True)
    return output_status

def check_calculated_descriptors(config: Config, milp_results: list):
    print("Checking calculated descriptors")
    outputfilename = config.output_prefix + ".sdf"
    test_prefix = config.output_prefix + "_test_tmp"
    for index, item in enumerate(config.input_data):
        prop = config.get_with_index(index, "prefix")
        # output current directory
        # sleep 
        subprocess.run([FV_GEN_NAME, f"{prop}.sdf", f"{prop}_test", outputfilename, test_prefix],
            stdout=subprocess.DEVNULL , check=False)
        model = item["model"]
        if model == "ANN":
            y, y_min, y_max, x_hat, ann_training_data_norm_filename, ann = milp_results[index]
            y_predict, _ = ann_inverter.inspection(f"{test_prefix}_desc_norm.csv", ann_training_data_norm_filename, ann, x_hat, STD_EPS)
        elif model == "LR":
            y, y_min, y_max, x_hat, fv_list, lr, num_fv = milp_results[index]
            y_star = y.value()
            y_predict = lr_inverter.inspection(f"{test_prefix}_desc_norm.csv", lr, x_hat, STD_EPS, num_fv, fv_list)
            y_predict = y_predict[0]
        elif model == "RF":
            y, y_min, y_max, x_hat, fv_list, rf, num_fv = milp_results[index]
            y_star = y.value()
            y_predict = rf_inverter.inspection(f"{test_prefix}_desc_norm.csv", rf, x_hat, STD_EPS, num_fv, fv_list)
            y_predict = y_predict[0]
        print("\tInspection value (scaled):  ", y_predict * (y_max - y_min) + y_min, end="\n\n")
