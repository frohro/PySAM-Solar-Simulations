#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 08:50:44 2020
This script assumes: 
    you are using PVWatts Commercial.
    you are nonprofit (no taxes or incentives)
    you are on Guam where the rates are flat as a function of time of day
    you are using PySAM version 2.02
You make an excel file with the rates as a function of time:
    Year, 50000 kWh rate, rest rate
    It will write the output to a new sheet in that file called Results.
    If you want to run the program again, you need to delete that sheet
    or make a new rates spreadsheet.
@author: frohro
"""

import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import tkinter as tk
import json
import PySAM.Pvwattsv7 as PVWattsCommercial
import PySAM.Utilityrate5 as UtilityRate
import PySAM.Cashloan as Cashloan
import PySAM.PySSC as pssc
import xlrd as xlrd
from xlutils.copy import copy as xl_copy

def output(filename, wb, years, NPV, period):
    new_wb = xl_copy(wb)
    sheet1 = new_wb.add_sheet('Results')
    
    sheet1.write(0, 0, 'Year')
    sheet1.write(0, 1, 'NPV')
    sheet1.write(0, 2, 'Payback')

    for i in range(0, len(years)):
        sheet1.write(i+1, 0, years[i])
        sheet1.write(i+1, 1, NPV[i])
        sheet1.write(i+1, 2, period[i])
        
    new_wb.save(filename)

years_to_plot = 10

root = tk.Tk()  # For filedialogs
root.withdraw()  # No root window

ssc = pssc.PySSC()

testing = False  # Make False if you are not running tests.
verbose = False  # Make False if you don't want all the debugging info.


# Get the SAM json file, make the simulations we need for the commercial
# PVWatts simulation.

try:
    if testing:
        json_file_path = '100kW_PVWatts_05degr.json'
    else:
        json_file_path = filedialog.askopenfilename(defaultextension='.json',
                title='Select the json file generated by SAM.',
                filetypes=[('Json file','*.json'), ('All files','*.*'), ])
    if verbose:
        print(json_file_path)
  
except NameError:
    print('NameError: with the json file')
else:
    with open(json_file_path) as f:
        dic = json.load(f)
pv_dat = pssc.dict_to_ssc_table(dic, "pvwattsv7")
ur_dat = pssc.dict_to_ssc_table(dic, "utilityrate5")
cl_dat = pssc.dict_to_ssc_table(dic, "cashloan")
pv = PVWattsCommercial.wrap(pv_dat)
ur = UtilityRate.from_existing(pv, 'PVWattsCommercial')
cl = Cashloan.from_existing(pv, 'PVWattsCommercial')
ur.assign(UtilityRate.wrap(ur_dat).export())
cl.assign(Cashloan.wrap(cl_dat).export())

degradation = cl.SystemOutput.degradation[0]
if verbose:
    print('degradation', degradation)
if testing:
    pv.execute()
    ur.execute()
    cl.execute()
    npv_single_stage = cl.Outputs.npv
    if verbose:
        if round(pv.Outputs.ac_annual) != 134580:
            print('\nError: Annual AC Output doesn\'t agree with SAM!\n')
        if round(cl.Outputs.npv) != 138348:
            print('Error Net Present Value does\'t agree with SAM!\n')
        if round(cl.Outputs.adjusted_installed_cost) != 223249:
            print('Error: Net installed cost doesn\'t agree with SAM!\n')
        if verbose:
            print('Full analysis for testing with no degradation:')
            print('Annual AC output: ', pv.Outputs.ac_annual, 
                  ' Should be 134580.')
            print('ur_ec_tou_mat: ', ur.ElectricityRates.ur_ec_tou_mat, 
                  ' Should 1, 1, 55000, 0.23, 0.08, ...')
            print('Should be 0.23. ', ur.ElectricityRates.ur_ec_tou_mat[0][4])
            print('cl.Outputs.npv: ', cl.Outputs.npv, 
                  'Should be $138,348.')
            print('cl.FinancialParameters.analysis_period: ', 
                  cl.FinancialParameters.analysis_period, ' Should be 25.')
            print('cl.FinancialParameters.real_discount_rate: ',
                  cl.FinancialParameters.real_discount_rate, ' Should be 1.5')
            print('cl.Outputs.adjusted_installed cost', 
                  cl.Outputs.adjusted_installed_cost, 
                  'Should be $223,249.')
            print('len(cl.Outputs.cf_operating_expenses): ',
                      len(cl.Outputs.cf_operating_expenses))
            print()

    check_payback = cl.Outputs.payback
    check_discounted_payback = cl.Outputs.discounted_payback
    if verbose:
        print('check_payback: ', check_payback)


# Get the rate data from the excel spreadsheet.
try:
    if testing:
        xl_file_path = 'Rates.xlsx'
    else:
        xl_file_path = filedialog.askopenfilename(defaultextension='xlxs',
            title='Select the excel file with rate data.',
            filetypes=[('excel 2007+', '*.xlsx'), ('excel 2003-', '*.xls'),
                           ('All files', '*.*')])
except NameError:
    print('NameError: with the excel file.')
else:
    with open(xl_file_path) as f:
        wb = xlrd.open_workbook(xl_file_path)
        try:
            rate_sheet = wb.sheet_by_name('Rates')
        except:
            print('\nError:  Does you spreadsheet have a \"Rates\" sheet?\n')

if verbose:
    print('The rates you have are:')   
rate_table = [rate_sheet.row_values(rn) for rn in range(rate_sheet.nrows)]
if verbose:
    print(rate_table)
    print()
initial_year = rate_table[1][0]
if verbose:
    print('initial_year', initial_year)
            
total_analysis_period = cl.FinancialParameters.analysis_period
npv_array = np.zeros(years_to_plot)
simple_payback_array = np.zeros(years_to_plot)
if verbose:
    print(npv_array)
iter_num = -1
for starting_year in range(int(rate_table[1][0]), int(rate_table[1][0] + \
                                               years_to_plot)): 
    iter_num  = iter_num + 1 
    if verbose:
        print('\nstarting_year: ', starting_year)
    # Manipulate the rate_table to match starting year.
    # Go through the rate table and remove any years prior to starting_year
    # except the last one just before the starting year.  That one change
    # the year to starting_year.
    for j in range(1, len(rate_table)): 
        if int(rate_table[j][0])  <= starting_year:
                rate_table[j][0] = starting_year
                if j > 1:
                    if int(rate_table[j-1][0]) == int(starting_year):
                        del rate_table[j-1]
                        break
    if verbose:
        print(rate_table)
    npv = 0.0
    yearly_savings_tuple = ()
    discounted_yearly_savings_tuple = ()
    starting_system_capacity = pv.SystemDesign.system_capacity
    starting_insurance_rate = cl.FinancialParameters.insurance_rate
    if verbose:
        print('Starting system capacity: ', starting_system_capacity)
        print('Total analysis period: ',total_analysis_period) 
        print('rate_table[1][0]', rate_table[1][0])
        print('rate_sheet.cell_value(1, 0) ', rate_sheet.cell_value(1, 0) )
    year = total_analysis_period + \
            rate_table[1][0]  # rate_sheet.cell_value(1, 0)
    end_year = year
    if verbose:
        print('Initially, year is: ', year) 
        print('cl.FinancialParameters.real_discount_rate', cl.FinancialParameters.
          real_discount_rate) 
        print()
        
    for i in range(len(rate_table)-1, 0, -1):  # Ditch the titles.        
    
        if verbose:
            # print(i, rate_sheet.cell_value(i,0))
            print(i, rate_table[i][0])
        
        year = rate_table[i][0] # rate_sheet.cell_value(i, 0) + j
        years_old = year - rate_table[1][0]  # rate_sheet.cell_value(1, 0) - j
        temp_list = [list(x) for x in ur.ElectricityRates.ur_ec_tou_mat]
        temp_list[0][4] = rate_table[i][1]
        # rate_sheet.cell_value(i, 1)
        temp_list[1][4] = rate_table[i][2]
        # rate_sheet.cell_value(i, 2)
        ur.ElectricityRates.ur_ec_tou_mat = tuple(temp_list)
        if verbose:
            print('ur.ElectricityRates.ur_ec_tou_mat[0][4]', 
                  ur.ElectricityRates.ur_ec_tou_mat[0][4])
        period = end_year - year
        pv.SystemDesign.system_capacity = starting_system_capacity*\
            (1 - 0.01*degradation)**(years_old)
        if verbose:
            print('System_Capacity (kW): ', pv.SystemDesign.system_capacity)
            print('Year: ', year, 'Years Old: ', years_old,'Period: ', period)
        cl.FinancialParameters.analysis_period = period
        cl.FinancialParameters.insurance_rate = \
                starting_insurance_rate / \
                (1 - 0.01*degradation)**years_old
        if verbose:
            print('cl.FinancialParameters.insurance_rate', 
              cl.FinancialParameters.insurance_rate)
        pv.execute()
        ur.execute()
        cl.execute()
        # We need to account for insurance when we turn down the initial install
        # size, because in the full calculation, it is a percent of the initial
        # installed cost.  If that cost goes down, we have a problem.
    
        # net_installed_cost = (cl.Outputs.adjusted_installed_cost\
        #     - 40000)*(1 - 0.01*degradation)**(years_old) + 40000
        net_installed_cost = cl.SystemCosts.total_installed_cost
        if i != 1:
            npv = npv + (cl.Outputs.npv + net_installed_cost)/\
                (1+0.01*cl.FinancialParameters.real_discount_rate)**years_old
        else:
            npv = npv + cl.Outputs.npv  
        end_year = year
        if verbose:
            print('End year: ', end_year)
            print('Year: ', year, 'NPV: ', npv)
            print('Annual AC output: ', pv.Outputs.ac_annual)
            print('ur_ec_tou_mat: ', ur.ElectricityRates.ur_ec_tou_mat)
            print('cl.Outputs.npv: ', cl.Outputs.npv)
            print('cl.FinancialParameters.analysis_period: ', 
              cl.FinancialParameters.analysis_period)
            print('cl.FinancialParameters.real_discount_rate: ',
              cl.FinancialParameters.real_discount_rate)
            print('cl.Outputs.adjusted_installed cost', 
              cl.Outputs.adjusted_installed_cost)
            print('net_installed_cost', net_installed_cost)
            print('cl.SystemCosts.total_installed_cost', 
                  cl.SystemCosts.total_installed_cost)
            print()
    
        installed_cost = cl.Outputs.adjusted_installed_cost
        if verbose:
            print('years_old: ', years_old)
            print('cl.Outputs.cf_energy_value: ', cl.Outputs.cf_energy_value)
            print('cl.Outputs.cf_operating_expenses: ', 
                  cl.Outputs.cf_operating_expenses)
            print('yearly_savings_tuple: ', yearly_savings_tuple)
        temp_tuple = tuple(np.subtract(cl.Outputs.cf_energy_value,
                    cl.Outputs.cf_operating_expenses)*\
                (1 + 0.01*cl.FinancialParameters.inflation_rate)**(years_old))
        yearly_savings_tuple = temp_tuple + yearly_savings_tuple
        yearly_savings_tuple = yearly_savings_tuple[1: \
                                    len(yearly_savings_tuple)]
        # This installed_cost will be the earliest one (the correct one)
        # Remove 0.0 from the front of yearly_savings_tuple.
        # if verbose:
        #     print('cl.Outputs.cf_energy_value: ', cl.Outputs.cf_energy_value)
        #     print('cl.Outputs.cf_operating_expenses: ', 
        #           cl.Outputs.cf_operating_expenses)
        #     print('len(cl.Outputs.cf_operating_expenses): ',
        #           len(cl.Outputs.cf_operating_expenses))
        #     print('yearly_savings_tuple: ', yearly_savings_tuple)
        #     print('len(yearly_savings_tuple): ', len(yearly_savings_tuple))
        # yearly_savings_tuple = yearly_savings_tuple[1: \
        #                         len(yearly_savings_tuple)]
        # yearly_savings_tuple = tuple(np.subtract(cl.Outputs.cf_energy_value,
        #             cl.Outputs.cf_operating_expenses)) + yearly_savings_tuple
        if verbose:
            print('yearly_savings_tuple: ', yearly_savings_tuple)
            print('len(yearly_savings_tuple): ', len(yearly_savings_tuple))
# We need to get rid of the zero in yearly_savings_tuple.
    #     discounted_yearly_savings_tuple = tuple(np.subtract(\
    #         cl.Outputs.cf_energy_value,
    #         cl.Outputs.cf_operating_expenses)/ \
    # # This cannot work. It raises all values to the years_old.  Fix me!
    #         (1+0.01*cl.FinancialParameters.real_discount_rate)**years_old) + \
    #                 discounted_yearly_savings_tuple

    if verbose:
        print('\nCalculating Simple Payback')
        print('yearly_savings_tuple: ', yearly_savings_tuple)
        print('installed_cost: ', installed_cost)
    years_payback = 0
    sum_simple_savings = 0 
    for simple_savings in yearly_savings_tuple:
            sum_simple_savings = sum_simple_savings + simple_savings
            if sum_simple_savings < installed_cost:
                years_payback = years_payback + 1
            else:

                previous_sum_simple_savings = sum_simple_savings - simple_savings
                part_year = (installed_cost - previous_sum_simple_savings)\
                    /simple_savings
                years_payback = years_payback + part_year
# Should the above 1 be a 2?
                break  
    print('Simple Payback Period (years): ', years_payback)
    if verbose:
        print('check_payback: ', check_payback)
    
    # discounted_years_payback = 0
    # sum_discounted_savings = 0 
    # for discounted_savings in discounted_yearly_savings_tuple:
    #         sum_discounted_savings = sum_discounted_savings + discounted_savings
    #         if sum_discounted_savings < installed_cost:
    #             discounted_years_payback = discounted_years_payback + 1
    #         else:
    #             previous_sum_discounted_savings = sum_discounted_savings - \
    #                 discounted_savings
    #             part_year = (installed_cost - previous_sum_discounted_savings)\
    #                 /simple_savings
    #             discounted_years_payback = discounted_years_payback - 2 + part_year
    #             # The 2 is because the first element of the tuple is 0.0.
    #             break  
    # print('Discounted Payback Period (years): ', discounted_years_payback)
    # if verbose:
    #     print('check_discounted_payback: ', check_discounted_payback)
        
    if testing:
        if verbose:
            if round(npv) != round(npv_single_stage):
                print('\nError:  NPV computed by stages does not equal NPV computed '
                  'directly!  NPV directly is: ', npv_single_stage, '\n')
    npv_array[iter_num] = npv    
    print('NPV: ', npv) 
    print()  
    simple_payback_array[iter_num] = years_payback      
years = np.arange(initial_year, initial_year + years_to_plot) 
plt.figure(0)
plt.bar(years, npv_array) 
plt.title('Net Present Value for Install Date')
plt.xlabel('Install Date (Year)')
plt.ylabel('Net Present Value ($)')

plt.figure(1)
plt.bar(years, simple_payback_array) 
plt.title('Simple Payback for Install Date')
plt.xlabel('Install Date (Year)')
plt.ylabel('Simple Payback (years)')

MsgBox = messagebox.askquestion ('eXcel Output',
        'Do you wish to save results to the eXcel rates file?')
if MsgBox == 'yes':
    output(xl_file_path, wb, years, npv_array, simple_payback_array)    
root = tk.Tk()
root.withdraw()


