"""
Test generates statistics for puf.csv variables.
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 test_puf_var_stats.py
# pylint --disable=locally-disabled test_puf_var_stats.py

import os
import json
import copy
import difflib
import numpy as np
import pandas as pd
import pytest
from taxcalc import Policy, Records, Calculator  # pylint: disable=import-error


def create_base_table(test_path):
    """
    Create and return base table.
    """
    # specify calculated variable names and descriptions
    calc_dict = {'eitc': 'Federal EITC',
                 'iitax': 'Federal income tax liability',
                 'payrolltax': 'Payroll taxes (ee+er) for OASDI+HI',
                 'c00100': 'Federal AGI',
                 'c02500': 'OASDI benefits in AGI',
                 'c04600': 'Post-phase-out personal exemption',
                 'c21040': 'Itemized deduction that is phased out',
                 'c04470': 'Post-phase-out itemized deduction',
                 'c04800': 'Federal regular taxable income',
                 'c05200': 'Regular tax on taxable income',
                 'c07220': 'Child tax credit (adjusted)',
                 'c11070': 'Extra child tax credit (refunded)',
                 'c07180': 'Child care credit',
                 'c09600': 'Federal AMT liability'}
    # specify read variable names and descriptions
    unused_var_set = set(['AGIR1', 'DSI', 'EFI', 'EIC', 'ELECT', 'FDED',
                          'h_seq', 'ffpos', 'fips', 'agi_bin',
                          'FLPDYR', 'FLPDMO', 'f2441', 'f3800', 'f6251',
                          'f8582', 'f8606', 'f8829', 'f8910', 'f8936', 'n20',
                          'n24', 'n25', 'n30', 'PREP', 'SCHB', 'SCHCF', 'SCHE',
                          'TFORM', 'IE', 'TXST', 'XFPT', 'XFST', 'XOCAH',
                          'XOCAWH', 'XOODEP', 'XOPAR', 'XTOT', 'MARS', 'MIDR',
                          'RECID', 'gender', 'wage_head', 'wage_spouse',
                          'earnsplit', 'agedp1', 'agedp2', 'agedp3',
                          's006', 's008', 's009', 'WSAMP', 'TXRT',
                          'filer', 'matched_weight', 'e00200p', 'e00200s',
                          'e00900p', 'e00900s', 'e02100p', 'e02100s',
                          'age_head', 'age_spouse',
                          'blind_head', 'blind_spouse'])
    read_vars = list(Records.USABLE_READ_VARS - unused_var_set)
    # get read variable information from JSON file
    rec_vars_path = os.path.join(test_path, '..', 'records_variables.json')
    with open(rec_vars_path) as rvfile:
        read_var_dict = json.load(rvfile)
    # create table_dict with sorted read vars followed by sorted calc vars
    table_dict = dict()
    for var in sorted(read_vars):
        table_dict[var] = read_var_dict['read'][var]['desc']
    sorted_calc_vars = sorted(calc_dict.keys())
    for var in sorted_calc_vars:
        table_dict[var] = calc_dict[var]
    # construct DataFrame table from table_dict
    table = pd.DataFrame.from_dict(table_dict, orient='index')
    table.columns = ['description']
    return table


def calculate_corr_stats(calc, table):
    """
    Calculate correlation coefficient matrix.
    """
    for varname1 in table.index:
        var1 = calc.array(varname1)
        var1_cc = list()
        for varname2 in table.index:
            var2 = calc.array(varname2)
            cor = np.corrcoef(var1, var2)[0][1]
            var1_cc.append(cor)
        table[varname1] = var1_cc


def calculate_mean_stats(calc, table, year):
    """
    Calculate weighted means for year.
    """
    total_weight = calc.total_weight()
    means = list()
    for varname in table.index:
        wmean = calc.weighted_total(varname) / total_weight
        means.append(wmean)
    table[str(year)] = means


def differences(new_filename, old_filename, stat_kind):
    """
    Return boolean-string pair with
    boolean indicating if differences between new and old file contents and
    string describing differences (if any).
    """
    with open(new_filename, 'r') as vfile:
        new_text = vfile.read()
    with open(old_filename, 'r') as vfile:
        old_text = vfile.read()
    # expected_results = txt.rstrip('\n\t ') + '\n'  # cleanup end of file txt
    new = new_text.splitlines(True)
    old = old_text.splitlines(True)
    diff = difflib.unified_diff(new, old, fromfile='new', tofile='old', n=0)
    # convert diff generator into a list of lines:
    diff_lines = list()
    for line in diff:
        diff_lines.append(line)
    # test failure if there are any diff_lines
    if len(diff_lines) > 0:
        fail = True
        new_name = os.path.basename(new_filename)
        old_name = os.path.basename(old_filename)
        msg = '{} RESULTS DIFFER:\n'.format(stat_kind)
        msg += '-------------------------------------------------'
        msg += '-------------\n'
        msg += '--- NEW RESULTS IN {} FILE ---\n'.format(new_name)
        msg += '--- if new OK, copy {} to  ---\n'.format(new_name)
        msg += '---                 {}         ---\n'.format(old_name)
        msg += '---            and rerun test.                   '
        msg += '          ---\n'
        msg += '-------------------------------------------------'
        msg += '-------------\n'
    else:
        fail = False
        msg = ''
        os.remove(new_filename)
    return fail, msg


MEAN_FILENAME = 'puf_var_wght_means_by_year.csv'
CORR_FILENAME = 'puf_var_correl_coeffs_2016.csv'


@pytest.mark.requires_pufcsv
def test_puf_var_stats(tests_path, puf_fullsample):
    """
    Main logic of test.
    """
    # create a Calculator object
    rec = Records(data=puf_fullsample)
    calc = Calculator(policy=Policy(), records=rec, verbose=False)
    # create base tables
    table_mean = create_base_table(tests_path)
    table_corr = copy.deepcopy(table_mean)
    del table_corr['description']
    # add statistics to tables
    year_headers = ['description']
    for year in range(Policy.JSON_START_YEAR, Policy.LAST_BUDGET_YEAR + 1):
        assert year == calc.policy.current_year
        year_headers.append(str(year))
        calc.calc_all()
        calculate_mean_stats(calc, table_mean, year)
        if year == 2016:
            calculate_corr_stats(calc, table_corr)
        if year < Policy.LAST_BUDGET_YEAR:
            calc.increment_year()
    # write tables to new CSV files
    mean_path = os.path.join(tests_path, MEAN_FILENAME + '-new')
    table_mean.sort_index(inplace=True)
    table_mean.to_csv(mean_path, header=year_headers, float_format='%8.0f')
    corr_path = os.path.join(tests_path, CORR_FILENAME + '-new')
    table_corr.sort_index(inplace=True)
    table_corr.to_csv(corr_path, float_format='%8.2f',
                      columns=table_corr.index)
    # compare new and old CSV files
    diffs_in_mean, mean_msg = differences(mean_path, mean_path[:-4], 'MEAN')
    diffs_in_corr, corr_msg = differences(corr_path, corr_path[:-4], 'CORR')
    if diffs_in_mean or diffs_in_corr:
        raise ValueError(mean_msg + corr_msg)
