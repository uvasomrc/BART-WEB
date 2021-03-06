# -*- coding: utf-8 -*-

import os, sys
import subprocess
import shutil
import json
import yaml

import utils
import marge_bart

PROJECT_DIR = os.path.dirname(__file__)

def generate_user_key(username):
    import time
    tstamp = time.time()
    key = username + '_' + str(tstamp)
    return key

def init_project_path(user_key):
    user_path = os.path.join(PROJECT_DIR, 'usercase/' + user_key)
    user_upload_path = os.path.join(user_path, 'upload')
    user_download_path = os.path.join(user_path, 'download')
    user_log_path = os.path.join(user_path, 'log')
    bart_output_path = os.path.join(user_download_path, 'bart_output')

    utils.create_dir(user_path)
    utils.create_dir(user_upload_path)
    utils.create_dir(user_download_path)
    utils.create_dir(user_log_path)
    utils.create_dir(bart_output_path)

    return user_path


def init_user_config(user_path, user_data):
    # init username.config and save config data
    config_file = os.path.join(user_path, 'user.config')
    with open(config_file, 'w') as fopen:
        yaml.dump(user_data, fopen)


def get_user_data(user_key):
    user_path = os.path.join(PROJECT_DIR, 'usercase/' + user_key)
    config_file = os.path.join(user_path, 'user.config')
    with open(config_file, 'r') as fopen:
        user_data = yaml.load(fopen)

    return user_data


def is_user_key_exists(user_key):
    dest_path = os.path.join(PROJECT_DIR, 'usercase/' + user_key)
    return os.path.exists(dest_path)


def config_results(results, user_data):
    '''
    Copy user_data to results for demonstration page: user configuration

    results:   related to template/result_demonstration.html
    user_data: user configuration
    '''
    results['user_conf'] = {}
    results['user_conf']['YourKey'] = user_data['user_key']
    results['user_conf']['Assembly'] = user_data['assembly']
    results['user_conf']['DataType'] = user_data['dataType']
    if user_data['gene_exp_type'] != "":
        results['user_conf']['GeneExpressionType'] = user_data['gene_exp_type']
    if user_data['gene_id_type'] != "":
        results['user_conf']['GeneIdType'] = user_data['gene_id_type']

    results['user_conf']['PredictionType'] = []
    if 'rp' in user_data['prediction_type']:
        results['user_conf']['PredictionType'].append("Relative Potentials")
    if 'cis' in user_data['prediction_type']:
        results['user_conf']['PredictionType'].append("Cisregulatory Elements")
    if 'tf' in user_data['prediction_type']:
        results['user_conf']['PredictionType'].append("TF patterns")
    if 'eh' in user_data['prediction_type']:
        results['user_conf']['PredictionType'].append("Enhancer")

    results['user_conf']['UploadFiles'] = []
    for file_path in user_data['files']:
        results['user_conf']['UploadFiles'].append(str(file_path.split('/')[-1]))


def generate_results(user_data):
    results = {}
    config_results(results, user_data)
    results['done'] = True

    # dataType: ChIP-seq, Geneset, Both
    # prediction_type: rp, cis, tf, eh
    # assembly: hg38, mm10
    # gene_exp_type: Gene_Only, Gene_Response
    # gene_id_type: GeneSymbol, RefSeq
    # marge & bart
    if user_data['marge'] and not marge_bart.is_marge_done(user_data['user_path']):
        results['done'] = False
        return results
    marge_file_dict = generate_marge_file_results(user_data)
    results.update(marge_file_dict)

    if user_data['bart'] and not marge_bart.is_bart_done(user_data['user_path']):
        results['done'] = False
        return results
    bart_file_results, bart_chart_results, bart_table_results = generate_bart_file_results(user_data)
    results.update(bart_file_results)
    results.update(bart_chart_results)
    results.update(bart_table_results)

    return results  


def generate_marge_file_results(user_data):
    '''
    If marge is done processing, generate marge results file for user to download.

    Input:   
    user_data: user configuration 

    Return:
    marge_file_results: related to marge file for downloading   
    '''
    # marge procedure log file path
    marge_file_results = {}
    marge_file_results['proc_log'] = []
    marge_file_results['marge_result_files'] = []

    if not user_data['marge']:
        return marge_file_results

    user_path = user_data['user_path']
    snakemake_log_dir = os.path.join(user_path, 'marge_data/.snakemake/log')
    
    for log_file in os.listdir(snakemake_log_dir):
        if log_file.endswith(".log"):
            src_log = os.path.join(snakemake_log_dir, log_file)
            dest_log = os.path.join(user_path, 'download/' + log_file)
            shutil.copyfile(src_log, dest_log)
            
            log_file_url = '/download/%s___%s' % (user_data['user_key'], log_file)
            marge_file_results['proc_log'].append((log_file, log_file_url))

    # marge output file path
    marge_output_path = os.path.join(user_path, 'marge_data/margeoutput')
    marge_suffix_type = ['_enhancer_prediction.txt', '_all_relativeRP.txt', '_Strength.txt', '_all_RP.txt', '_target_regressionInfo.txt']
    for root, dirs, files in os.walk(marge_output_path):
        for file in files:
            for file_type in marge_suffix_type:
                if file_type in str(file):
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(user_path, 'download/' + file)
                    shutil.copyfile(src_file, dest_file)

                    dest_file_url = '/download/%s___%s' % (user_data['user_key'], file)
                    marge_file_results['marge_result_files'].append((file, dest_file_url))

    return marge_file_results


def generate_bart_file_results(user_data):
    '''
    If bart is done processing, generate bart results file for user to download.

    Input:
    user_data: user configuration

    Return:
    bart_file_results: related to bart file for downloading
    bart_chart_results: related to bart chart for demonstrating and downloading
    bart_table_results: related to bart table for demonstrating and downloading

    '''
    bart_file_results = {}
    bart_chart_results = {}
    bart_table_results = {}

    bart_file_results['bart_result_files'] = []
    bart_table_results['bartResult'] = []
    bart_chart_results['bart_chart_files'] = []

    if not user_data['bart']:
        return bart_file_results, bart_chart_results, bart_table_results

    user_files = []
    for uf in user_data['files']:
        user_files.append(os.path.basename(uf).split('.')[0])

    # bart output file path
    bart_output_dir = os.path.join(user_data['user_path'], 'download/bart_output')
    for root, dirs, files in os.walk(bart_output_dir):
        if 'bart_output/plot' in root:
            for chart_file in files:
                src_file = os.path.join(root, chart_file)
                dest_file_url = '/download/bart_output/plot/%s___%s' % (user_data['user_key'], chart_file)
                bart_chart_results['bart_chart_files'].append((src_file, dest_file_url))
        else: 
            for bart_file in files:
                if '_auc.txt' in bart_file:
                    src_file = os.path.join(root, bart_file)
                    dest_file_url = '/download/bart_output/%s___%s' % (user_data['user_key'], bart_file)
                    bart_file_results['bart_result_files'].append((bart_file, dest_file_url))
                    
                if '_bart_results.txt' in bart_file:
                    src_file = os.path.join(root, bart_file)
                    dest_file_url = '/download/bart_output/%s___%s' % (user_data['user_key'], bart_file)
                    bart_file_results['bart_result_files'].append((bart_file, dest_file_url))
                    # bart table results for demonstration
                    bart_table_results['bartResult'] = parse_bart_results(src_file)

                    # just finding chart files in bart_output/plot

                    # bart_chart_results['bart_chart_files'] = plot_top_tf(bart_df, bart_output_dir, AUCs)
        
    return bart_file_results, bart_chart_results, bart_table_results


# for showing table
def parse_bart_results(bart_result_file):
    # tf_name, tf_score, p_value, z_score, max_auc, r_rank -> definition in result_demonstration.html
    bart_title = ['tf_name', 'tf_score', 'p_value', 'z_score', 'max_auc', 'r_rank'] 
    bart_result = []
    with open(bart_result_file, 'r') as fopen:
        next(fopen) # skip first line
        for line in fopen:
            line = line.strip()
            bart_result.append(dict(zip(bart_title, line.split('\t'))))
    return bart_result
            

if __name__ == '__main__':
    parse_bart_results('/Users/marvin/Projects/flask_playground/usercase/a_1534972940.637962/download/genelist1_bart_results.txt')