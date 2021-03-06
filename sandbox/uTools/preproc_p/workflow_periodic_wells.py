import pandas as pd
import numpy as np
import scipy
from scipy import integrate


import sys
sys.path.append('../')
sys.path.append('../'*4)
import unifloc.sandbox.uTools.preproc_p.preproc_tool as preproc_tool
import unifloc.sandbox.uTools.plot_workflow.plotly_workflow as pltl_wf


gn = preproc_tool.GlobalNames()

fsolve = scipy.optimize.fsolve
this_time_delta = pd.to_timedelta(1, unit = 'hour')


def prepare_data(this_file):
    this_file = preproc_tool.rename_columns_by_dict(this_file)

    if this_file[gn.i_a_motor_a].min() == 0.1:
        this_file[gn.i_a_motor_a] = this_file[gn.i_a_motor_a].replace(0.1, 0)

    work_status, work_timedelta, stop_timedelta, work_bounds, stop_bounds, stats = calculated_regime_time(this_file,
                                                                                                   regime_column=gn.i_a_motor_a,
                                                                                                   return_all=True)
    this_file = this_file.dropna(subset=[gn.i_a_motor_a])
    this_file[gn.work_status_number] = work_status
    return this_file


def calculated_regime_time(this_file, regime_column=gn.i_a_motor_a, return_all=False):
    """
    Функция для расчета параметров работы ПКВ
    :param this_file:
    :param regime_column:
    :param return_all:
    :return:
    """
    this_file = this_file.dropna(subset=[regime_column])
    last_time = this_file.index[0]

    work_status = []
    if this_file[regime_column][0] > 0:
        work_status.append(1)
    else:
        work_status.append(0)

    work_timedelta = []
    stop_timedelta = []
    regime_bounds = []
    regime_timedelta = []
    work_bounds = []
    stop_bounds = []

    for i in range(1, this_file.shape[0]):
        this_time = this_file.index[i]
        this_value = this_file[regime_column][i]
        if this_value > 0:
            work_status.append(1)
        else:
            work_status.append(0)
        # print(this_value)
        time_delta = this_time - last_time
        # time_delta = this_file.index[i-1] - last_time
        if work_status[-1] != work_status[-2]:

            # print('Переключение')
            if work_status[-1] == 1:
                # print('Включение')
                stop_timedelta.append(time_delta.total_seconds() / 60)
                stop_bounds.append([last_time, this_time])

                regime_timedelta.append(time_delta.total_seconds() / 60)
                regime_bounds.append([last_time, this_time])
            else:
                # print('Выключение')
                work_timedelta.append(time_delta.total_seconds() / 60)
                work_bounds.append([last_time, this_time])

                regime_timedelta.append(time_delta.total_seconds() / 60)
                regime_bounds.append([last_time, this_time])

            last_time = this_time

    if work_status[-1] == 1:
        # print('Последний интервал работала')
        work_timedelta.append(time_delta.total_seconds() / 60)
        work_bounds.append([last_time, this_time])
    else:
        # print('Последний интервал не работала')
        work_timedelta.append(time_delta.total_seconds() / 60)
        work_bounds.append([last_time, this_time])

    work_time_median = np.median(work_timedelta)
    stop_timedelta_median = np.median(stop_timedelta)
    work_fraction_perc = np.sum(work_timedelta) / (np.sum(work_timedelta) + np.sum(stop_timedelta)) * 100
    stop_timedelta_np_array = np.array(stop_timedelta)
    amount_of_big_stops = len(stop_timedelta_np_array[stop_timedelta_np_array > stop_timedelta_median * 2])

    stats = {f"Медианное время работы ({regime_column}), мин": work_time_median,
                f"Медианное время накопления ({regime_column}), мин": stop_timedelta_median,
             f"Рабочая доля времени за весь период ({regime_column}), %": work_fraction_perc,
             f"Количество неплановых остановок ({regime_column}), %": amount_of_big_stops,
             f"Период записи данных ({regime_column}), timedelta": this_file.index[-1] - this_file.index[0],
             f"Количество записей  ({regime_column}), штук": this_file.shape[0]}


    if not return_all:
        return work_time_median, stop_timedelta_median
    else:
        return work_status, work_timedelta, stop_timedelta, work_bounds, stop_bounds, stats


def calc_integral(series, return_result_series = False):
    this_delta = series.index[-1] - series.index[0] + (series.index[1] - series.index[0])
    this_delta_to_rolling = this_delta
    result_integral = series.rolling(this_delta_to_rolling).apply(integrate.trapz)
    if return_result_series:
        return result_integral
    else:
        return result_integral[-1]


def get_new_df_with_instant_rate(df, nedeed_value = None):
    super_small_df = df.copy()
    def func_for_fsolve_inner(multiply, nedeed_value = None):
        #print(multiply)
        super_small_df['instant_rate'] = super_small_df[gn.work_status_number] * multiply
        new_integral_value = calc_integral(super_small_df['instant_rate'])
        #print(f"new_integral_value: {new_integral_value}")
        super_small_df[gn.q_liq_m3day + ' (created)'] = super_small_df['instant_rate'] * 24 * 60
        return nedeed_value - new_integral_value
    result = fsolve(func_for_fsolve_inner, x0 = 1, args=[nedeed_value])
    return super_small_df, result


def total_seconds(timedelta):
    """Convert timedeltas to seconds
    In Python, time differences can take many formats. This function can take
    timedeltas in any format and return the corresponding number of seconds, as
    a float.
    Beware! Representing timedeltas as floats is not as precise as representing
    them as a timedelta object in datetime, numpy, or pandas.
    Parameters
    ----------
    timedelta : various
        Time delta from python's datetime library or from numpy or pandas. If
        it is from numpy, it can be an ndarray with dtype datetime64. If it is
        from pandas, it can also be a Series of datetimes. However, this
        function cannot operate on entire pandas DataFrames. To convert a
        DataFrame, do df.apply(to_seconds)
    Returns
    -------
    seconds : various
        Returns the total seconds in the input timedelta object(s) as float.
        If the input is a numpy ndarray or pandas Series, the output is the
        same, but with a float datatype.
    """
    try:
        seconds = timedelta.total_seconds()
    except AttributeError:  # no method total_seconds
        one_second = np.timedelta64(1000000000, 'ns')
        # use nanoseconds to get highest possible precision in output
        seconds = timedelta / one_second
    return seconds


def get_true_median_value(df, column, except_zero=True):
    this_df = df.copy()
    this_df = this_df.resample('1s').mean()
    this_df = this_df.interpolate('linear')
    if except_zero:
        this_df = this_df[this_df[column] > 0]
    median_value = this_df[column].median()
    if df[column].median() > median_value:
        median_value = df[column].median()

    top_values_len = df[df[column] > df[column].max() * 0.9].shape[0]
    _, work_timedelta, _, _, _ = calculated_regime_time(df, regime_column=column, return_all=True)
    if len(work_timedelta) * 2 < top_values_len:
        median_value = df[df[column] > df[column].max() * 0.9][column].median()
    print(median_value)
    return median_value


def get_true_median_value_in_series(df, column, except_zero=True):
    this_df = df.copy()
    this_series = this_df[column]
    this_series = this_series.resample('1s').mean()
    this_series = this_series.interpolate('linear')
    if except_zero:
        this_series = this_series[this_series > 0]
    median_value = this_series.median()
    if df[column].median() > median_value:
        median_value = df[column].median()

    top_values_len = df[df[column] > df[column].max() * 0.9].shape[0]
    _, work_timedelta, _, _, _,_ = calculated_regime_time(df, regime_column=column, return_all=True)
    if len(work_timedelta) * 2 < top_values_len:
        median_value = df[df[column] > df[column].max() * 0.9][column].median()
    print(median_value)
    return median_value


def find_stucks_variant_zero(this_file):
    median_value = get_true_median_value(this_file, gn.i_a_motor_a)
    stuck_times = this_file[this_file[gn.i_a_motor_a] > median_value * 2]
    stucks = []
    if stuck_times.shape[0] > 0:
        left_boundary = stuck_times.index[0]
        this_stuck_interval = None
        for i in range(stuck_times.shape[0]-1):
            right_boundary = stuck_times.index[i+1]
            stuck_times_rows = stuck_times[(stuck_times.index >= left_boundary) & (stuck_times.index <= right_boundary)].shape[0]
            this_file_rows = this_file[(this_file.index >= left_boundary) & (this_file.index <= right_boundary)].shape[0]
            if stuck_times_rows == this_file_rows:
                this_stuck_interval = [left_boundary, right_boundary]
            else:
                stucks.append(this_stuck_interval)
                left_boundary = stuck_times.index[i+1]
            if i == stuck_times.shape[0]-2:
                stucks.append(this_stuck_interval)
    return stucks


def find_stucks(df):
    this_file = df.copy()
    this_file['Ток фазы А дельта'] = [0] + list(
        this_file[gn.i_a_motor_a].values[1::] - this_file[gn.i_a_motor_a].values[0:-1])

    time_series = this_file['Ток фазы А дельта']
    time_series = time_series[(time_series < np.inf) & (time_series > -np.inf)]
    work_status, work_timedelta, stop_timedelta, work_bounds, stop_bounds, stats = calculated_regime_time(this_file,
                                                                                                   regime_column=gn.i_a_motor_a,
                                                                                                   return_all=True)
    stucks = []

    not_all_stucks_saved = True

    value = time_series.min()
    while not_all_stucks_saved:
        index = time_series.where(time_series == value).dropna().index[0]

        for number, i in enumerate(work_bounds):
            if index >= i[0] and index <= i[1]:
                stuck_work_bounds = i
                normal_work_bounds = work_bounds[number - 1]
                stuck_work_series = time_series[
                    (time_series.index >= stuck_work_bounds[0]) & (time_series.index < stuck_work_bounds[1])]
                normal_work_series = time_series[
                    (time_series.index >= normal_work_bounds[0]) & (time_series.index < normal_work_bounds[1])]
                stuck_work_timedelta = stuck_work_series.index[-1] - stuck_work_series.index[0]
                normal_work_timedelta = normal_work_series.index[-1] - normal_work_series.index[0]
                if total_seconds(normal_work_timedelta) != 0:
                    if total_seconds(stuck_work_timedelta) / total_seconds(normal_work_timedelta) < 0.25:
                        median_check_df = this_file[
                            (this_file.index >= stuck_work_bounds[0] - 10 * normal_work_timedelta) &
                            (this_file.index <= stuck_work_bounds[1] + 10 * normal_work_timedelta)]
                        median_check_df = median_check_df[(median_check_df.index < stuck_work_bounds[0]) |
                                                          (median_check_df.index > stuck_work_bounds[1])]
                        median_median_value = get_true_median_value_in_series(median_check_df, gn.i_a_motor_a,
                                                                              except_zero=True)
                        max_check_df = this_file[(this_file.index >= stuck_work_bounds[0]) &
                                                 (this_file.index <= stuck_work_bounds[1])]
                        max_value = max_check_df[gn.i_a_motor_a].max()
                        if max_value >= median_median_value * 1.5:
                            stucks.append(stuck_work_bounds)
                            time_series = time_series[(time_series.index < i[0]) | (time_series.index > i[1])]
                            new_value = time_series.min()
        try:
            if new_value != value:
                value = new_value
            else:
                not_all_stucks_saved = False

        except:
            not_all_stucks_saved = False

    return stucks


def create_useful_inf(cs_file_name):
    info_dict = {}
    this_file = pd.read_csv(cs_file_name, index_col=[0], parse_dates=True)
    print(cs_file_name.split('\\')[-1].replace('_first_edit_cs.csv', ''))
    this_file = preproc_tool.rename_columns_by_dict(this_file)
    info_dict['Начало записи данных'] = [this_file.index[0]]
    info_dict['Конец записи данных'] = [this_file.index[-1]]
    info_dict['Продолжительность записи данных'] = [this_file.index[-1] - this_file.index[0]]
    info_dict['Общее число записей'] = [this_file.shape[0]]
    info_dict['Средняя дискретность, секунды'] = [
        ((this_file.index[-1] - this_file.index[0]) / this_file.shape[0]).seconds]
    info_dict['Медианное время работы, мин'], info_dict['Медианное время простаивания, мин'] = calculated_regime_time(
        this_file)
    if 'F Турб.вращ.,Гц' in this_file.columns:
        info_dict['Медианная частота турбинного вращения'] = [
            this_file[this_file['F Турб.вращ.,Гц'] > 0]['F Турб.вращ.,Гц'].median()]
        info_dict['Максимальная частота турбинного вращения'] = [this_file['F Турб.вращ.,Гц'].max()]
    else:
        info_dict['Медианная частота турбинного вращения'] = [-1]
        info_dict['Максимальная частота турбинного вращения'] = [-1]
    if gn.freq_hz in this_file.columns:
        this_file = this_file[this_file[gn.freq_hz] > 0]
    else:
        this_file = this_file[this_file[gn.i_a_motor_a] > 0]

    info_dict['Медианное значение загрузки (Р)'] = [this_file[gn.motor_load_perc].median()]
    info_dict['Максимальное значение загрузки (Р)'] = [this_file[gn.motor_load_perc].max()]

    info_dict['Медианное значение тока (Р)'] = [this_file[gn.i_a_motor_a].median()]
    info_dict['Максимальное значение тока (Р)'] = [this_file[gn.i_a_motor_a].max()]

    info_dict['Медианное значение мощности (Р)'] = [this_file[gn.active_power_kwt].median()]
    info_dict['Максимальное значение мощности (Р)'] = [this_file[gn.active_power_kwt].max()]

    if gn.freq_hz in this_file.columns:
        info_dict['Медианное значение частоты (Р)'] = [this_file[gn.freq_hz].median()]
        info_dict['Максимальное значение частоты (Р)'] = [this_file[gn.freq_hz].max()]
    else:
        info_dict['Медианное значение частоты (Р)'] = [-1]
        info_dict['Максимальное значение частоты (Р)'] = [-1]

    if gn.p_intake_atm in this_file.columns:
        info_dict['Медианное значение давления на приеме (Р)'] = [this_file[gn.p_intake_atm].median()]
        info_dict['Минимальное значение давления на приеме (Р)'] = [this_file[gn.p_intake_atm].min()]
    else:
        info_dict['Медианное значение давления на приеме (Р)'] = [-1]
        info_dict['Минимальное значение давления на приеме (Р)'] = [-1]

    if gn.t_motor_c in this_file.columns:
        info_dict['Медианное значение температуры двигателя (Р)'] = [this_file[gn.t_motor_c].median()]
        info_dict['Максимальное значение температуры двигателя (Р)'] = [this_file[gn.t_motor_c].max()]
    else:
        info_dict['Медианное значение температуры двигателя (Р)'] = [-1]
        info_dict['Максимальное значение температуры двигателя (Р)'] = [-1]

    info_dict['Медианное значение коэффициента мощности (Р)'] = [this_file[gn.cos_phi_d].median()]
    info_dict['Минимальное значение коэффициента мощности (Р)'] = [this_file[gn.cos_phi_d].min()]

    result_df = pd.DataFrame(info_dict)
    result_df.index = [cs_file_name.split('\\')[-1].replace('_first_edit_cs.csv', '')]
    result_df.index.name = 'Скважина'
    return result_df


def undim_index(time_index):
    time_index = time_index - time_index[0]
    time_index = time_index.total_seconds()
    time_index = time_index / time_index[-1]
    return time_index


def find_gas_periods(this_df, param=gn.i_a_motor_a):
    df = this_df.copy()
    work_status, work_timedelta, \
    stop_timedelta, work_bounds, stop_bounds, stats = calculated_regime_time(df, regime_column=param, return_all=True)
    df[gn.work_status_number + f" ({param.replace(' ','_')})"] = work_status

    work_periods = []
    for k in work_bounds:
        this_df = df[(df.index >= k[0]) & (df.index <= k[1])]
        work_periods.append(this_df)

    gas_periods = []
    gas_dfs = []
    if len(work_periods) > 2:
        for j, i in enumerate(work_periods):
            small_df = i.copy()
            small_df = small_df.dropna(subset=[param])
            if small_df.shape[0] > 0:
                small_df = small_df[param]
                small_df = small_df[small_df > 0]
                if len(small_df) > 0:
                    small_df = small_df / small_df.max()
                    # small_df = small_df[small_df>0.2]
                    small_df.index = undim_index(small_df.index)
                    small_df = small_df[small_df.index <= 0.95]
                    small_df = small_df[small_df.index > 0.5]

                    values = [0] + list(small_df.values[1::] - small_df.values[0:-1:])
                    np_values = np.array(values)
                    np_values_gas = np_values[np_values <= -0.12]
                    np_values_gas_up = np_values[np_values >= 0.06]
                    np_values_gas_down = np_values[np_values <= -0.04]
                    if len(np_values_gas) > 0 or (len(np_values_gas_up) > 0 and len(np_values_gas_down) > 0):
                        gas_dfs.append(i)
                        gas_periods.append(work_bounds[j])

    stats_with_gas = {
             f"Поступление газа по ({param}), раз": len(gas_periods),
             f"Доля нестабильных режимов по ({param}), %": len(gas_periods) / len(work_periods) * 100
    }
    stats_with_gas.update(stats)
    if len(gas_dfs) != 0:
        for j,i in enumerate(gas_dfs):
            #small_df = i[[param, gn.work_status_number + f" ({param})"]]
            #print(i.columns)
            small_df = i[[param, gn.work_status_number + f" ({param.replace(' ','_')})"]]
            small_df.columns = [f"Поступление газа в ЭЦН по {param}", gn.work_status_number + f" ({param.replace(' ','_')})"]
            #small_df[gn.work_status_number + f" ({param})"] = df[gn.work_status_number + f" ({param})"] * 0 + 2
            #small_df = small_df.drop(columns = [param])
            if j == 0:
                result_gas_df = small_df.copy()
            else:
                result_gas_df = result_gas_df.append(small_df)
        result_gas_df = result_gas_df.drop(columns = [gn.work_status_number + f" ({param.replace(' ','_')})"])
        df = df.join(result_gas_df, how = 'outer')
    return gas_periods, gas_dfs, stats_with_gas, df


parameters = [ gn.q_liq_m3day, gn.q_oil_mass_tday, gn.q_gas_m3day,
              gn.active_power_kwt, gn.i_a_motor_a, gn.motor_load_perc, gn.freq_hz, gn.cos_phi_d,
             gn.p_intake_atm, gn.p_lin_atm, gn.t_intake_c, gn.t_motor_c,
              gn.vibration_xy_msec2, gn.vibration_z_msec2,
             "Рабочая доля времени", gn.work_status_number]


def analyse_cs_data(this_file_name, parameters=parameters):
    try:
        df = pd.read_csv(this_file_name, index_col = [0], parse_dates = True, dayfirst = True)
        df = preproc_tool.rename_columns_by_dict(df)

        if df[gn.i_a_motor_a].min() != 0.1 and df[gn.i_a_motor_a].min() < 1:
            minimum_value = df[gn.i_a_motor_a].min()
            df[gn.i_a_motor_a] = df[gn.i_a_motor_a].replace(minimum_value, 0)
            df[gn.i_a_motor_a] = df[gn.i_a_motor_a].replace(0.2, 0)
            df[gn.i_a_motor_a] = df[gn.i_a_motor_a].replace(0.3, 0)
            df[gn.i_a_motor_a] = df[gn.i_a_motor_a].replace(0.4, 0)

        gas_borders, gas_dfs, stats, df = find_gas_periods(df, gn.i_a_motor_a)

        gas_borders_load, gas_dfs_load, stats_load, df = find_gas_periods(df, gn.motor_load_perc)
        stats.update(stats_load)

        stacks = find_stucks(df)
        stats['Количество перегрузок'] = len(stacks)

        borders = [gas_borders, gas_borders_load,stacks]

        banches = pltl_wf.create_banches_for_report(df, parameters, fuzzy_names=True)
        new_file_name = this_file_name.replace('.csv', '.html')
        new_file_name = new_file_name.replace('dataset_to_use', 'analysis_result')
        print(' ---> ' + new_file_name +  '\n')

        table = pd.DataFrame(stats, index = [this_file_name.split('\\')[-1]])

        table_for_plot = table.T
        table_for_plot.index.name = 'Название исходного файла'

        pltl_wf.create_report_html(df, banches,new_file_name , borders = borders, auto_open=False,
                                   df_for_table = table_for_plot)
        return table
    except:
        print(f"\n Ошибка в файле: {this_file_name}\n")
        return None


analyse_cs_data(r'E:\Данные\2020_04_ноябрьск_су\dataset_to_use\04_14_2020\_Суторма2_13_13_K_186_1680_0.csv')