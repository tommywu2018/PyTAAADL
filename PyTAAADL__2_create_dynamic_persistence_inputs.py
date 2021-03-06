
"""
Created on Sat Dec  2 12:50:40 2017

@author: dp
"""

# --------------------------------------------------
# A Multilayer Perceptron implementation example using TensorFlow library.
# --------------------------------------------------

import os
import datetime
import numpy as np
import pandas
import configparser

from keras import backend as K
from keras.models import model_from_json
from keras.models import Sequential
from keras.layers import Conv2D
from keras.layers import Activation
from keras.layers import LeakyReLU
from keras.layers import MaxPooling2D
from keras.layers import Dropout
from keras.layers import Dense
from keras.layers.normalization import BatchNormalization
from keras.optimizers import RMSprop, Adam, Adagrad, Nadam

from matplotlib import pyplot as plt

## local imports
_cwd = os.getcwd()
os.chdir(os.path.join(os.getcwd()))
_data_path = os.getcwd()
'''
from functions.quotes_for_list_adjClose import get_Naz100List, \
                                               arrayFromQuotesForList
'''
from functions.allstats import allstats
from functions.TAfunctions import _is_odd, \
                                  generateExamples, \
                                  generatePredictionInput, \
                                  generateExamples3layer, \
                                  generateExamples3layerGen, \
                                  generateExamples3layerForDate, \
                                  generatePredictionInput3layer, \
                                  get_params, \
                                  interpolate, \
                                  cleantobeginning, \
                                  cleantoend
from functions.UpdateSymbols_inHDF5 import UpdateHDF5, \
                                           loadQuotes_fromHDF

from matplotlib import pyplot as plt
import matplotlib.gridspec as gridspec

os.chdir(_cwd)




def get_predictions_input(config_filename, adjClose, datearray):

    params = get_params(config_filename)

    first_history_index = params['first_history_index']
    num_periods_history = params['num_periods_history']
    increments = params['increments']

    print(" ... generating examples ...")
    Xpredict, Ypredict, dates_predict, companies_predict = generateExamples3layerGen(datearray,
                                               adjClose,
                                               first_history_index,
                                               num_periods_history,
                                               increments,
                                               output_incr='monthly')

    print(" ... examples generated ...")
    return Xpredict, Ypredict, dates_predict, companies_predict


def build_model(config_filename, verbose=False):
    # --------------------------------------------------
    # build DL model
    # --------------------------------------------------

    params = get_params(config_filename)

    optimizer_choice = params['optimizer_choice']
    loss_function = params['loss_function']

    weights_filename = params['weights_filename']
    model_json_filename = params['model_json_filename']

    # load model and weights from json and hdf files.
    json_file = open(model_json_filename, 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    model = model_from_json(loaded_model_json)
    # load weights into new model
    model.load_weights(weights_filename)
    if verbose:
        print("    ... model successfully loaded from disk")

    if optimizer_choice == 'RMSprop':
        optimizer = RMSprop(lr=0.001, rho=0.9, epsilon=1e-08, decay=0.0)
    elif optimizer_choice == 'Adam':
        optimizer = Adam(lr=0.0005, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0)
    elif optimizer_choice == 'Adagrad':
        optimizer = Adagrad(lr=0.005, epsilon=1e-08, decay=0.0)
    elif optimizer_choice == 'Nadam':
        optimizer = Nadam(lr=0.001, beta_1=0.9, beta_2=0.999, epsilon=1e-08, schedule_decay=0.004)

    if verbose:
        model.summary()
    model.compile(optimizer=optimizer, loss=loss_function)

    return model


def one_model_prediction(imodel, first_history_index, datearray, adjClose, symbols, num_stocks, verbose=False):

    # --------------------------------------------------
    # build DL model
    # --------------------------------------------------

    config_filename = imodel.replace('.hdf','.txt')
    print("\n ... config_filename = ", config_filename)
    #print(".", end='')
    model = build_model(config_filename)

    # collect meta data for weighting ensemble_symbols
    params = get_params(config_filename)
    #num_stocks = params['num_stocks']
    num_periods_history = params['num_periods_history']
    increments = params['increments']

    symbols_predict = symbols
    Xpredict, Ypredict, dates_predict, companies_predict = generateExamples3layerGen(datearray,
                                                                                  adjClose,
                                                                                  first_history_index,
                                                                                  num_periods_history,
                                                                                  increments,
                                                                                  output_incr='monthly')

    dates_predict = np.array(dates_predict)
    companies_predict = np.array(companies_predict)

    # --------------------------------------------------
    # make predictions monthly for backtesting
    # - there might be some bias since entire preiod
    #   has data used for training
    # --------------------------------------------------

    try:
        model.load_weights(imodel)
    except:
        pass

    dates_predict = np.array(dates_predict)
    companies_predict = np.array(companies_predict)

    inum_stocks = num_stocks
    cumu_system = [10000.0]
    cumu_BH = [10000.0]
    plotdates = [dates_predict[0]]
    _forecast_mean = []
    _forecast_median = []
    _forecast_stdev = []
    for i, idate in enumerate(dates_predict[1:]):
        if idate != dates[-1] and companies_predict[i] < companies_predict[i-1]:
            # show predictions for (single) last date
            _Xtrain = Xpredict[dates_predict == idate]
            _dates = np.array(dates_predict[dates_predict == idate])
            _companies = np.array(companies_predict[dates_predict == idate])
            #print("forecast shape = ", model.predict(_Xtrain).shape)
            _forecast = model.predict(_Xtrain)[:, 0]
            _symbols = np.array(symbols_predict)

            indices = _forecast.argsort()
            sorted_forecast = _forecast[indices]
            sorted_symbols = _symbols[indices]

            try:
                _Ytrain = Ypredict[dates_predict == idate]
                sorted_Ytrain = _Ytrain[indices]
                BH_gain = sorted_Ytrain.mean()
            except:
                BH_gain = 0.0

            avg_gain = sorted_Ytrain[-inum_stocks:].mean()

            _forecast_mean.append(_forecast.mean())
            _forecast_median.append(np.median(_forecast))
            _forecast_stdev.append(_forecast.std())

            if verbose:
                print(" ... date, system_gain, B&H_gain = ",
                      idate,
                      format(avg_gain, '3.1%'), format(BH_gain, '3.1%'),
                      sorted_symbols[-inum_stocks:])
            cumu_system.append(cumu_system[-1] * (1.+avg_gain))
            cumu_BH.append(cumu_BH[-1] * (1.+BH_gain))
            plotdates.append(idate)
    print(" ... system, B&H = ", format(cumu_system[-1], '10,.0f'), format(cumu_BH[-1], '10,.0f'))

    return cumu_system, cumu_BH, sorted_symbols, plotdates



def ensemble_prediction(models_list, idate, datearray, adjClose, num_stocks, sort_mode='sharpe', verbose=False):
    #--------------------------------------------------------------
    # loop through best models and pick companies from ensemble prediction
    #--------------------------------------------------------------

    ensemble_symbols = []
    ensemble_Ytrain = []
    ensemble_sharpe = []
    ensemble_recent_sharpe = []
    ensemble_equal = []
    ensemble_rank = []
    for iii,imodel in enumerate(models_list):

        # --------------------------------------------------
        # build DL model
        # --------------------------------------------------

        config_filename = os.path.join(models_folder, imodel).replace('.hdf','.txt')
        #print(" ... config_filename = ", config_filename)
        print(".", end='')
        model = build_model(config_filename, verbose=False)

        # collect meta data for weighting ensemble_symbols
        params = get_params(config_filename)
        #num_stocks = params['num_stocks']
        num_periods_history = params['num_periods_history']
        increments = params['increments']

        symbols_predict = symbols
        Xpredict, Ypredict, dates_predict, companies_predict = generateExamples3layerForDate(idate,
                                                                                             datearray,
                                                                                             adjClose,
                                                                                             num_periods_history,
                                                                                             increments,
                                                                                             output_incr='monthly',
                                                                                             verbose=False)

        dates_predict = np.array(dates_predict)
        companies_predict = np.array(companies_predict)

        # --------------------------------------------------
        # make predictions monthly for backtesting
        # - there might be some bias since entire preiod
        #   has data used for training
        # --------------------------------------------------

        weights_filename = os.path.join(models_folder, imodel)
        try:
            model.load_weights(weights_filename)
        except:
            pass

        # show predictions for (single) last date
        _Xtrain = Xpredict[dates_predict == idate]
        _Ytrain = Ypredict[dates_predict == idate][:,0]
        _dates = np.array(dates_predict[dates_predict == idate])
        _companies = np.array(companies_predict[dates_predict == idate])
        _forecast = model.predict(_Xtrain)[:, 0]
        _symbols = np.array(symbols_predict)[_companies]

        del model
        K.clear_session()

        forecast_indices = _forecast.argsort()[-num_stocks:]
        sorted_Xtrain = _Xtrain[forecast_indices,:,:,:]
        sorted_Ytrain = _Ytrain[forecast_indices]
        sorted_companies = _companies[forecast_indices]
        sorted_forecast = _forecast[forecast_indices]
        sorted_symbols = _symbols[forecast_indices]
        ##print("\n ... sorted_symbols = ",sorted_symbols[-num_stocks:])

#        ensemble_sharpe_weights = np.ones(np.array(sorted_symbols[-num_stocks:]).shape, 'float') * params['_sharpe_ratio_system']
#        ensemble_recent_sharpe_weights = np.ones_like(ensemble_sharpe_weights) * params['_sharpe_ratio_recent_system']
        ensemble_sharpe_weights = np.ones(sorted_companies.shape, 'float')
        ensemble_recent_sharpe_weights = np.ones_like(ensemble_sharpe_weights)
        #print("sorted_Xtrain.shape = ",sorted_Xtrain.shape, "   sorted_companies.shape = ", sorted_companies.shape)
        for icompany in range(sorted_companies.shape[0]):
            #print("sorted_Xtrain[icompany,:,2,0].shape, sharpe = ",sorted_Xtrain[icompany,:,2,0].shape,allstats((sorted_Xtrain[icompany,:,0,0]+1.).cumprod()).sharpe(periods_per_year=252./increments[2]))
            if sort_mode == 'sharpe':
                ensemble_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,-1,0]+1.).cumprod()).sharpe(periods_per_year=252./increments[-1])
                ensemble_recent_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,int(sorted_Xtrain.shape[2]/2),0]+1.).cumprod()).sharpe(periods_per_year=252./increments[0])
            elif sort_mode == 'sharpe_plus_sortino':
                ensemble_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,-1,0]+1.).cumprod()).sharpe(periods_per_year=252./increments[-1]) + \
                                                    allstats((sorted_Xtrain[icompany,:,-1,0]+1.).cumprod()).sortino()
                ensemble_recent_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,int(sorted_Xtrain.shape[2]/2),0]+1.).cumprod()).sharpe(periods_per_year=252./increments[0]) + \
                                                           allstats((sorted_Xtrain[icompany,:,int(sorted_Xtrain.shape[2]/2),0]+1.).cumprod()).sortino()
            elif sort_mode == 'sortino':
                ensemble_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,-1,0]+1.).cumprod()).sortino()
                ensemble_recent_sharpe_weights[icompany] = allstats((sorted_Xtrain[icompany,:,int(sorted_Xtrain.shape[2]/2),0]+1.).cumprod()).sortino()
            elif sort_mode == 'count' or sort_mode == 'equal':
                ensemble_sharpe_weights[icompany] = 1.
                ensemble_recent_sharpe_weights[icompany] = 1.

        ensemble_equal_weights = np.ones_like(ensemble_sharpe_weights)
        ensemble_rank_weights = np.arange(np.array(sorted_symbols[-num_stocks:]).shape[0])[::-1]

        ensemble_symbols.append(sorted_symbols[-num_stocks:])
        ensemble_Ytrain.append(sorted_Ytrain[-num_stocks:])
        ensemble_sharpe.append(ensemble_sharpe_weights)
        ensemble_recent_sharpe.append(ensemble_recent_sharpe_weights)
        ensemble_equal.append(ensemble_recent_sharpe_weights)
        ensemble_rank.append(ensemble_rank_weights)

        #print(imodel,sorted_symbols[-num_stocks:])
        #print(" ... ",ensemble_sharpe_weights)

    # sift through ensemble symbols
    ensemble_symbols = np.array(ensemble_symbols).flatten()
    ensemble_Ytrain = np.array(ensemble_Ytrain).flatten()
    ensemble_sharpe = np.array(ensemble_sharpe).flatten()
    ensemble_recent_sharpe = np.array(ensemble_recent_sharpe).flatten()
    ensemble_equal = np.array(ensemble_equal).flatten()
    ensemble_rank = np.array(ensemble_rank).flatten()

    #unique_symbols = list(set(np.array(ensemble_symbols)))
    unique_symbols = list(set(list(np.array(ensemble_symbols).flatten())))
    unique_ensemble_symbols = []
    unique_ensemble_Ytrain = []
    unique_ensemble_sharpe = []
    unique_ensemble_recent_sharpe = []
    unique_ensemble_equal = []
    unique_ensemble_rank = []
    for k, ksymbol in enumerate(unique_symbols):
        unique_ensemble_symbols.append(np.array(ensemble_symbols)[ensemble_symbols == ksymbol][0])
        unique_ensemble_Ytrain.append(ensemble_Ytrain[ensemble_symbols == ksymbol].mean())
        unique_ensemble_sharpe.append(ensemble_sharpe[ensemble_symbols == ksymbol].sum())
        unique_ensemble_recent_sharpe.append(ensemble_recent_sharpe[ensemble_symbols == ksymbol].sum())
        unique_ensemble_equal.append(ensemble_equal[ensemble_symbols == ksymbol].sum())
        unique_ensemble_rank.append(ensemble_rank[ensemble_symbols == ksymbol].sum())

    #print("unique_ensemble_sharpe = ", np.sort(unique_ensemble_sharpe)[-num_stocks:])

    indices_recent = np.argsort(unique_ensemble_recent_sharpe)[-num_stocks:]
    #print("indices = ",indices)
    sorted_recent_sharpe = np.array(unique_ensemble_recent_sharpe)[indices_recent]
    sorted_recent_sharpe = np.array(sorted_recent_sharpe)

    unique_ensemble_sharpe = np.array(unique_ensemble_sharpe) + np.array(unique_ensemble_recent_sharpe)
    if sort_mode == 'equal':
        unique_ensemble_sharpe = np.ones_like(unique_ensemble_sharpe)

    indices = np.argsort(unique_ensemble_sharpe)[-num_stocks:]
    #print("indices = ",indices)
    sorted_sharpe = np.array(unique_ensemble_sharpe)[indices]
    ##sorted_sharpe = np.array(sorted_sharpe)
    #print("                                       ... sorted_sharpe[sorted_sharpe < 0.].shape = ", sorted_sharpe[sorted_sharpe < 0.].shape, sorted_recent_sharpe[sorted_recent_sharpe < 0.].shape)
    sorted_symbols = np.array(unique_ensemble_symbols)[indices]
    sorted_Ytrain = np.array(unique_ensemble_Ytrain)[indices]
    #company_indices = [list(unique_ensemble_symbols).index(isymbol) for isymbol in sorted_symbols]

    ##print("sorted_symbols = ", sorted_symbols)
    ##print("sorted_Ytrain = ", sorted_Ytrain)
    #print("_symbols[company_indices] = ", _symbols[company_indices][-num_stocks:])
    #print("_Ytrain[company_indices] = ", _Ytrain[company_indices][-num_stocks:])

    """
    # equal-weighted
    try:
        _Ytrain = _Ytrain[dates_predict == idate]
        sorted_Ytrain = sorted_Ytrain[-num_stocks:]
        BH_gain = _Ytrain.mean()
    except:
        BH_gain = 0.0

    avg_gain = sorted_Ytrain.mean()

    return avg_gain, BH_gain, sorted_symbols
    """

    # weighted contribution according to sharpe ratio
    try:
        _Ytrain = _Ytrain[dates_predict == idate]
        sorted_Ytrain = sorted_Ytrain[-num_stocks:]
        sorted_sharpe = sorted_sharpe[-num_stocks:]
        BH_gain = _Ytrain.mean()
    except:
        BH_gain = 0.0

    ####sorted_sharpe = 1./ sorted_sharpe
    sorted_sharpe = np.sqrt(np.clip(sorted_sharpe,0.,sorted_sharpe.max()))
    if verbose:
        print("       gains, stddev of gains = ", np.around(sorted_Ytrain,3),np.std(sorted_Ytrain))
        print("       sorted_sharpe", np.around(sorted_sharpe,2), np.std(sorted_sharpe))
        print("       weights", np.around(sorted_sharpe/ sorted_sharpe.sum(),3), np.std(sorted_sharpe/ sorted_sharpe.sum()))
        print("       weighted gains", np.around((sorted_Ytrain * sorted_sharpe) / sorted_sharpe.sum(),3))
    avg_gain = ((sorted_Ytrain * sorted_sharpe) / sorted_sharpe.sum()).sum()
    symbols_weights = sorted_sharpe / sorted_sharpe.sum()

    return avg_gain, BH_gain, sorted_symbols, symbols_weights

# --------------------------------------------------
# Import list of symbols to process.
# --------------------------------------------------

# read list of symbols from disk.
stockList = 'Naz100'
filename = os.path.join(_data_path, 'symbols', 'Naz100_Symbols.txt')                   # plotmax = 1.e10, runnum = 902

# --------------------------------------------------
# Get quotes for each symbol in list
# process dates.
# Clean up quotes.
# Make a plot showing all symbols in list
# --------------------------------------------------

## update quotes from list of symbols
(symbols_directory, symbols_file) = os.path.split(filename)
basename, extension = os.path.splitext(symbols_file)
print((" symbols_directory = ", symbols_directory))
print(" symbols_file = ", symbols_file)
print("symbols_directory, symbols.file = ", symbols_directory, symbols_file)
###############################################################################################
do_update = False
if do_update is True:
    UpdateHDF5(symbols_directory, symbols_file)  ### assume hdf is already up to date
adjClose, symbols, datearray, _, _ = loadQuotes_fromHDF(filename)

firstdate = datearray[0]

# --------------------------------------------------
# Clean up missing values in input quotes
#  - infill interior NaN values using nearest good values to linearly interpolate
#  - copy first valid quote from valid date to all earlier positions
#  - copy last valid quote from valid date to all later positions
# --------------------------------------------------

for ii in range(adjClose.shape[0]):
    adjClose[ii, :] = interpolate(adjClose[ii, :])
    adjClose[ii, :] = cleantobeginning(adjClose[ii, :])
    adjClose[ii, :] = cleantoend(adjClose[ii, :])

print(" security values check: ", adjClose[np.isnan(adjClose)].shape)

# --------------------------------------------------
# prepare labeled data for DL training
# - set up historical data plus actual performance one month forward
# --------------------------------------------------

best_final_value = -99999
best_recent_final_value = -99999
num_periods_history = 20
first_history_index = 1500

try:
    for jdate in range(len(datearray)):
        year, month, day = datearray[jdate].split('-')
        datearray[jdate] = datetime.date(int(year), int(month), int(day))
except:
    pass

dates = []
company_number = []
first_day_of_month = []
new_month = []
previous_month = datearray[0]
for idate in range(adjClose.shape[1]):
    if idate == 0 or idate < first_history_index:
        beginning_of_month = False
    elif datearray[idate].month == datearray[idate-1].month:
        beginning_of_month = False
    else:
        beginning_of_month = True
    for icompany in range(adjClose.shape[0]):
        dates.append(datearray[idate])
        company_number.append(icompany)
        new_month.append(beginning_of_month)

datearray_new_months = []
for i,ii in enumerate(new_month):
    if ii is True:
        datearray_new_months.append(dates[i])

datearray_new_months = list(set(datearray_new_months))
datearray_new_months.sort()


# --------------------------------------------------
# make predictions monthly for backtesting
# - apply multiple DL models and use 'num_stocks' most frequent stocks
# - break ties randomly
# --------------------------------------------------

# initialize dict for monitoring best recent performance
# - track results while varying 'sort_mode', 'num_stocks'
# - each list element to contain list of lists:
# - [sort_mode,num_stocks] [['sortino', 'sharpe', 'equal'],[0,1,2,3,4,5,6,7,8,9]]
recent_performance = {}

#for model_filter in ['SP', 'Naz100', 'all']:
#for model_filter in ['SP']:
#for sort_mode in ['sortino', 'sharpe']:

models_folder = os.path.join(os.getcwd(), 'pngs', 'best_performers4')
models_list = os.listdir(models_folder)
models_list = [i for i in models_list if '.txt' in i]
models_list = [i for i in models_list if 'bak' not in i]

model_filter = 'SP'

if model_filter == 'Naz100':
    models_list = [i for i in models_list if 'Naz100' in i]
if model_filter == 'SP':
    models_list = [i for i in models_list if 'SP' in i]

#sort_mode = 'sharpe'
#sort_mode = 'sortino'
#sort_mode = 'sharpe_plus_sortino'


print("\n\n****************************\n")
print(" ... model_filter = ", model_filter)

first_pass = True
num_stocks_list = [5,6,7,8,9]
num_stocks_list = [2,3,4,5,6,7,8,9]
num_stocks_list = [3,5,7,9]
sort_mode_list = ['sortino', 'sharpe', 'count', 'equal']
for inum_stocks in num_stocks_list:

    print(" ... inum_stocks = ", inum_stocks)

    # -------------------------------------------------------------------------
    # initialize performance history for individual models
    # -------------------------------------------------------------------------
    cumu_models = []
    for im, imodel in enumerate(models_list):
        cumu_models.append([10000.0])

    # -------------------------------------------------------------------------
    # compute performance history for individual models
    # -------------------------------------------------------------------------

    for im, imodel in enumerate(models_list):
        avg_gain, _, _, models_plotdates = one_model_prediction(os.path.abspath(os.path.join(models_folder,imodel)),
                                                         first_history_index,
                                                         datearray,
                                                         adjClose,
                                                         symbols,
                                                         inum_stocks)
        cumu_models[im] = avg_gain


    # -------------------------------------------------------------------------
    # initialize performance history for ensemble model
    # -------------------------------------------------------------------------
    cumu_system = [10000.0]
    cumu_system_worst = [10000.0]
    cumu_BH = [10000.0]
    cumu_dynamic_system = [10000.0]
    cumu_dynamic_reversion_system = [10000.0]
    plotdates = [datearray_new_months[0]]
    _weights_stdev = [0]

    _forecast_mean = []
    _forecast_median = []
    _forecast_stdev = []

    # -------------------------------------------------------------------------
    # compute performance for all models collectively, as ensemble model
    # -------------------------------------------------------------------------

    #for i, idate in enumerate(datearray_new_months[:-1]):
    for i, idate in enumerate(datearray_new_months[:-1]):

        recent_comparative_gain = [1.]
        recent_comparative_month_gain = [1.]
        recent_comparative_method = ['cash']
        for sort_mode in sort_mode_list:

            if sort_mode == sort_mode_list[0]:
                print("")

            avg_gain, BH_gain, sorted_symbols, symbols_weights = ensemble_prediction(models_list, idate, datearray, adjClose, inum_stocks, sort_mode=sort_mode)

            if symbols_weights[np.isnan(symbols_weights)].shape[0] > 0 or inum_stocks==0:
                avg_gain = 0.
                symbols_weights = np.ones(symbols_weights.shape, 'float')

            if first_pass:
                # set up pandas dataframe to hold results
                '''
                datarow = [ ['dates',idate], ['sort_modes', sort_mode],
                         ['number_stocks', inum_stocks], ['gains', avg_gain],
                         ['symbols', [sorted_symbols]], ['weights', [symbols_weights]] ]
                '''
                df = pandas.DataFrame(columns=['dates', 'sort_modes', 'number_stocks', 'gains', 'symbols', 'weights', 'cumu_value'])
                for iinum_stocks in num_stocks_list:
                    for isort_mode in sort_mode_list:
                        datarow = [ datearray[first_history_index], isort_mode, iinum_stocks, 0., [], [], 10000.]
                        df.loc[len(df)] = datarow
                datarow = [ idate, sort_mode, inum_stocks, avg_gain, sorted_symbols, symbols_weights, np.isnan]
                df.loc[len(df)] = datarow
                smode = df.values[-1,1]
                nstocks = df.values[-1,2]
                indices = df.loc[np.logical_and(df['sort_modes']==smode,df['number_stocks']==nstocks)]['gains'].index
                method_cumu_gains = 10000.*(df.values[indices,-4]+1.).cumprod()
                df.loc[len(df)-1,'cumu_value'] = method_cumu_gains[-1]
                first_pass = False
            else:
                datarow = [ idate, sort_mode,
                         inum_stocks, avg_gain,
                         sorted_symbols, symbols_weights, np.isnan]
                df.loc[len(df)] = datarow
                smode = df.values[-1,1]
                nstocks = df.values[-1,2]
                indices = df.loc[np.logical_and(df['sort_modes']==smode,df['number_stocks']==nstocks)]['gains'].index
                method_cumu_gains = 10000.*(df.values[indices,-4]+1.).cumprod()
                df.loc[len(df)-1,'cumu_value'] = method_cumu_gains[-1]

            cumu_system.append(cumu_system[-1] * (1.+avg_gain))
            recent_comparative_month_gain.append(1.+avg_gain)
            if sort_mode == sort_mode_list[0]:
                cumu_BH.append(cumu_BH[-1] * (1.+BH_gain))
            plotdates.append(idate)
            _weights_stdev.append(symbols_weights.std())

            print(" ... system, B&H = ",
                  idate,
                  format(avg_gain, '3.1%'), format(BH_gain, '3.1%'),
                  sort_mode, format(method_cumu_gains[-1], '10,.0f'), format(cumu_BH[-1], '10,.0f'))
            try:
                print("           ... symbols, weights = ",
                  sorted_symbols, np.around(symbols_weights,3), symbols_weights.sum(), format(method_cumu_gains[-2]/method_cumu_gains[-5],'5.3f') )
            except:
                print("           ... symbols, weights = ",
                  sorted_symbols, np.around(symbols_weights,3), symbols_weights.sum() )

            '''
            if len(df)>1 and len(df)%20==0:
                #print(" ...datarow = ", datarow)
                print(" ...df (partial) = ", df.values[:,np.array([0,1,2,3,6])])
            '''

            try:
                recent_comparative_gain.append(method_cumu_gains[-2]/method_cumu_gains[-5])
                recent_comparative_method.append(sort_mode)
            except:
                recent_comparative_gain.append(1.+BH_gain)
                recent_comparative_method.append('BH')
            if sort_mode == sort_mode_list[-1]:
                best_comparative_index = np.argmax(recent_comparative_gain)
                worst_comparative_index = np.argmin(recent_comparative_gain[1:])+1
                cumu_dynamic_system.append(cumu_dynamic_system[-1] * recent_comparative_month_gain[best_comparative_index])
                cumu_dynamic_reversion_system.append(cumu_dynamic_reversion_system[-1] * recent_comparative_month_gain[worst_comparative_index])
                print("        ... methods, near-term gains ", recent_comparative_method, np.around(recent_comparative_gain,2))
                print("        ... dynamic system = ",
                      recent_comparative_method[best_comparative_index], format(cumu_dynamic_system[-1], '10,.0f'),
                      recent_comparative_method[worst_comparative_index], format(cumu_dynamic_reversion_system[-1], '10,.0f'))


    print(" ...system, B&H = ", format(cumu_system[-1], '10,.0f'), format(cumu_BH[-1], '10,.0f'))

# write comparative data to hdf
#df.set_index('dates', inplace=True)
df.to_hdf(os.path.join(os.getcwd(),'persistence_data_full_v2.hdf'), 'table', table=True, mode='a')

# plot results
os.chdir(_cwd)
system_label = 'best ensemble'
plt.close(2)
subplotsize = gridspec.GridSpec(2,1,height_ratios=[5,2])
plt.figure(2, figsize=(14, 10))
plt.clf()
plt.subplot(subplotsize[0])
plt.plot(plotdates, cumu_BH, 'r-', lw=3, label='B&H')
plt.plot(plotdates, cumu_system, 'k-', label=system_label)
plt.grid(True)
plt.yscale('log')
for im, imodel in enumerate(models_list):
    plt.plot(models_plotdates, cumu_models[im], 'k-', lw=.15, label=imodel)
plt.legend()
plt.title('Best ensemble systems\nPredict on stocks in '+stockList)
plt.text(plotdates[0]+datetime.timedelta(100), 7000., "ensemble of best systems")
plt.text(plotdates[0]+datetime.timedelta(2500), 7000., "models: "+model_filter)
plt.text(plotdates[0]+datetime.timedelta(4500), 7000., "num_stocks: "+str(inum_stocks))
plt.subplot(subplotsize[1])
plt.grid(True)
plt.plot(plotdates, _weights_stdev, label='weights_stdev')
plt.legend()
plt.savefig(os.path.join(models_folder, model_filter+"_"+str(inum_stocks)+"_ensemble_"+sort_mode+"_best_fig-2"+'.png'), format='png')

# plot results
num_months = int(12*13.75)
plt.close(3)
plt.figure(3, figsize=(14, 10))
plt.clf()
plt.subplot(subplotsize[0])
plt.plot(plotdates[-num_months:], cumu_BH[-num_months:]/cumu_BH[-num_months]*10000., 'r-', lw=3, label='B&H')
plt.plot(plotdates[-num_months:], cumu_system[-num_months:]/cumu_system[-num_months]*10000., 'k-', label=system_label)
plt.grid(True)
plt.yscale('log')
for im, imodel in enumerate(models_list):
    plt.plot(models_plotdates[-num_months:], cumu_models[im][-num_months:]/cumu_models[im][-num_months]*10000., 'k-', lw=.15, label=imodel)
plt.legend(loc='upper left')
#plt.title('Train on SP500 w/o 20 random stocks\nPredict on all SP500 stocks\n'+str(missing_stocks))
plt.title('Best ensemble systems\nPredict on stocks in '+stockList)
plt.text(plotdates[-num_months]+datetime.timedelta(100), 9500., "ensemble of best systems")
plt.text(plotdates[-num_months]+datetime.timedelta(600), 9500., "models: "+model_filter)
plt.text(plotdates[-num_months]+datetime.timedelta(1100), 9500., "num_stocks: "+str(inum_stocks))
plt.subplot(subplotsize[1])
plt.grid(True)
plt.plot(plotdates[-num_months:], _weights_stdev[-num_months:], label='weights_stdev')
plt.legend()
plt.savefig(os.path.join(models_folder, model_filter+"_"+str(inum_stocks)+"_ensemble_"+sort_mode+"_best_fig-3"+'.png'), format='png')


# plot results
num_months = int(12*4.75)
plt.close(4)
plt.figure(4, figsize=(14, 10))
plt.clf()
plt.subplot(subplotsize[0])
plt.plot(plotdates[-num_months:], cumu_BH[-num_months:]/cumu_BH[-num_months]*10000., 'r-', lw=3, label='B&H')
plt.plot(plotdates[-num_months:], cumu_system[-num_months:]/cumu_system[-num_months]*10000., 'k-', label=system_label)
plt.grid(True)
plt.yscale('log')
for im, imodel in enumerate(models_list):
    plt.plot(models_plotdates[-num_months:], cumu_models[im][-num_months:]/cumu_models[im][-num_months]*10000., 'k-', lw=.15, label=imodel)
plt.legend(loc='upper left')
#plt.title('Train on SP500 w/o 20 random stocks\nPredict on all SP500 stocks\n'+str(missing_stocks))
plt.title('Best ensemble systems\nPredict on stocks in '+stockList)
plt.text(plotdates[-num_months]+datetime.timedelta(100), 9500., "ensemble of best systems")
plt.text(plotdates[-num_months]+datetime.timedelta(600), 9500., "models: "+model_filter)
plt.text(plotdates[-num_months]+datetime.timedelta(1100), 9500., "num_stocks: "+str(inum_stocks))
plt.subplot(subplotsize[1])
plt.grid(True)
plt.plot(plotdates[-num_months:], _weights_stdev[-num_months:], label='weights_stdev')
plt.legend()
plt.savefig(os.path.join(models_folder, model_filter+"_"+str(inum_stocks)+"_ensemble_"+sort_mode+"_best_fig-4"+'.png'), format='png')

