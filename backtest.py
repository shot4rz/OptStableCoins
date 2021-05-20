# plots and backtests eur price arbitrage against stable coins and usd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

plt.style.use('dark_background')

from datetime import datetime, timedelta
from binance.client import Client

# creates binance api client
client = Client('', '')

FOREX_DIR = 'forexdata'
BINANCE_DIR = 'binancedata'
FNAME_START, FNAME_END = 'DAT_MT_', '_M1_2021'
FNAME_2020 = 'DAT_MT_EURUSD_M1_2020'
# hard codes jan to april of 2021 for forex data
MONTHS_USED = '01 02 03 04'.split()
DF_COLUMNS = 'date time open high low close volume'.split()
# numbered columns will be deleted
DF_BINANCE_COLUMNS = 'datetime open high low close 0 1 2 3 4 5 6'.split()

FOREX_SYMBOLS = ['EURUSD']
STABLE_SYMBOLS = ['EURBUSD', 'EURUSDT']

USE_CUSTOM_FOREX_CSV = True
FILL_GAPS = False

DAYMINS = 1440
EMA_LENGTHS = (DAYMINS * 3, DAYMINS * 1, DAYMINS * 7)

# backtest params
# START_LONG = False # too much effort to implement
START_USD_BALANCE = 100
# BUY_DIFF = -0.006
# SELL_DIFF = 0.001
BUY_DIFF_P = -0.5
SELL_DIFF_P = -0.1
# binance fee when using BNB = 0.00075
FEE = 0.00075

LINE = '-----------------------------------------------------------------------'

# concats csvs of forex data into a df
def get_forex_df(symbol):
    forex_data = []
    # reads 2020 data and drops last column
    df = pd.read_csv(f'{FOREX_DIR}/{FNAME_2020}.csv', names=DF_COLUMNS).iloc[:, :-1]
    forex_data.append(df)
    for month_no in MONTHS_USED:
        file_name = f'{FNAME_START}{symbol}{FNAME_END}{month_no}.csv'
        file_path = f'{FOREX_DIR}/{file_name}'
        if os.path.isfile(file_path):
            # reads the csv and drops last column
            df = pd.read_csv(file_path, names=DF_COLUMNS).iloc[:, :-1]
            forex_data.append(df)
        else:
            print(f'No such file "{file_name}"')
    df = pd.concat(forex_data, ignore_index=True, axis = 0)
    # refactors index to datetime object
    # TODO: use parse dates when reading the csvs
    df['datetime'] = pd.to_datetime(df['date']+' '+df['time'])
    df.set_index('datetime', inplace=True)
    df.drop(['date', 'time'], axis=1, inplace=True)
    # removing rows with duplicate indexes
    df = df.loc[~df.index.duplicated(), :]
    return df

# gets stable coin data from binance
def get_stable_df(symbol, start, end):
    candles = client.get_historical_klines(symbol, '1m', start, end)
    df = pd.DataFrame(candles, dtype=float, columns = DF_BINANCE_COLUMNS)
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('datetime', inplace=True)
    # drops columns to match forex dataframe
    df.drop('0 1 2 3 4 5 6'.split(), axis=1, inplace=True)
    return df

# gets start and end timestamps (ms) from the forex data dfs
def get_start_and_end_ts_ms(forex_df):
    start = forex_df.index[0].timestamp() * 1000
    end = forex_df.index[-1].timestamp() * 1000
    # must be millisecond timestamps TYPE INT for binance api
    return int(start), int(end)

# checks for data directories
def make_dirs():
    if not os.path.isdir(FOREX_DIR):
        os.mkdir(FOREX_DIR)
    if not os.path.isdir(BINANCE_DIR):
        os.mkdir(BINANCE_DIR)

# populates price data dict
def populate_data_dict():
    data = {}
    for forex_symbol in FOREX_SYMBOLS:
        file_path = f'{FOREX_DIR}/{forex_symbol}_1m.csv'
        if not os.path.isfile(file_path):
            data[forex_symbol] = get_forex_df(forex_symbol)
            data[forex_symbol].to_csv(file_path)
        elif USE_CUSTOM_FOREX_CSV:
            data[forex_symbol] = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
        else:
            data[forex_symbol] = get_forex_df(forex_symbol)
    start_ts_ms, end_ts_ms = get_start_and_end_ts_ms(data[FOREX_SYMBOLS[0]])
    for stable_symbol in STABLE_SYMBOLS:
        file_path = f'{BINANCE_DIR}/{stable_symbol}_1m.csv'
        # fetches stable coin price data if it is not yet present
        if not os.path.isfile(file_path):
            data[stable_symbol] = get_stable_df(stable_symbol, start_ts_ms, end_ts_ms)
            data[stable_symbol].to_csv(file_path)
        else:
            data[stable_symbol] = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
    '''
    # drops rows from forex df from before stable symbol listing
    stable_list_first_datetime = data[STABLE_SYMBOLS[0]].index[0]
    reached_first_datetime = False
    for datetime in data[FOREX_SYMBOLS[0]].index:
        if not reached_first_datetime:
            if datetime <= stable_list_first_datetime:
                data[FOREX_SYMBOLS[0]].drop(datetime, inplace=True)
            else:
                reached_first_datetime = True
    '''
    return data

# fills forex close prices during the weekend with last price
def fill_gaps(data):
    last_price_minute = 0
    for minute in data[STABLE_SYMBOLS[0]].index:
        if minute in data[FOREX_SYMBOLS[0]].index:
            last_price_minute = minute
        # if no price has been found yet, don't fill
        elif last_price_minute:
            data[FOREX_SYMBOLS[0]].loc[minute] = data[FOREX_SYMBOLS[0]].loc[last_price_minute]
    return data

# plots price and price difference
def plot_price_diff(data):
    # creates plot with 2 graphs
    fig = plt.figure()
    ax1 = fig.add_axes([0.07, 0.45, 0.9, 0.45])
    ax2 = fig.add_axes([0.07, 0.1, 0.9, 0.25])
    ax1.set_title('EUR 1m close price')
    # plots prices on top axis
    data['EURUSD'].plot(y='close', ax=ax1, label='USD', color='b', lw=0.5)
    data['EURUSDT'].plot(y='close', ax=ax1, label='USDT', color='g', lw=0.5)
    data['EURBUSD'].plot(y='close', ax=ax1, label='BUSD', color='y', lw=0.5)
    # calculates difference in price
    # data['EURUSDT']['diff'] = data['EURUSDT']['close'] - data['EURUSD']['close']
    # data['EURBUSD']['diff'] = data['EURBUSD']['close'] - data['EURUSD']['close']
    # calculates percentage difference in prices
    data['EURUSDT']['diff'] = ((data['EURUSDT']['close'] - data['EURUSD']['close'])/data['EURUSD']['close']) * 100
    data['EURBUSD']['diff'] = ((data['EURBUSD']['close'] - data['EURUSD']['close'])/data['EURUSD']['close']) * 100
    # adding diff movin average and std
    data['EURUSDT']['EMA'] = data['EURUSDT']['diff'].ewm(span=EMA_LENGTHS[2], adjust=False).mean()
    data['EURUSDT']['LOWB'] = data['EURUSDT']['EMA'] - data['EURUSDT']['diff'].ewm(EMA_LENGTHS[2]).std()
    data['EURUSDT']['HIGHB'] = data['EURUSDT']['EMA'] + data['EURUSDT']['diff'].ewm(EMA_LENGTHS[2]).std()
    # plots difference on axis 2
    data['EURUSDT'].plot(y='diff', ax=ax2, label='€USDT-€USD', color='g', lw=0.5)
    data['EURBUSD'].plot(y='diff', ax=ax2, label='€BUSD-€USD', color='y', lw=0.5)
    # plotting mas
    data['EURUSDT'].plot(y='EMA', ax=ax2, label='EMA')
    data['EURUSDT'].plot(y='LOWB', ax=ax2, label='LOWB')
    data['EURUSDT'].plot(y='HIGHB', ax=ax2, label='HIGHB')
    plt.show()
    return data

# simulates trades on the data and writes them in new columns of the df
def populate_trades(data):
    for stable_symbol in STABLE_SYMBOLS:
        df = data[stable_symbol]
        df['buy_signal'] = df['diff'] < BUY_DIFF_P
        df['sell_signal'] = df['diff'] > SELL_DIFF_P
        df['buy_price'] = np.nan
        df['sell_price'] = np.nan
        is_long = False
        for minute in df.index:
            if not is_long:
                # checks for buy signal
                if df['buy_signal'].loc[minute]:
                    # writes buy price with fees included
                    df.loc[minute, 'buy_price'] = df['close'].loc[minute] * (1 + FEE)
                    is_long = True
            elif df['sell_signal'].loc[minute]:
                df.loc[minute, 'sell_price'] = df['close'].loc[minute] * (1 - FEE)
                is_long = False
        # this is probably uncessary but it feels wrong not doing it
        data[stable_symbol] = df
    return data

# plots trades
def plot_trades(data):
    for stable_symbol in STABLE_SYMBOLS:
        fig = plt.figure()
        ax = fig.add_axes([0.07, 0.1, 0.85, 0.8])
        ax.set_title(f'{stable_symbol} trades')
        # plots prices and trades
        data['EURUSD'].plot(y='close', ax=ax, label='EURUSD', color='b', lw=0.5)
        data[stable_symbol].plot(y='close', ax=ax, label=stable_symbol, color='y', lw=0.5)
        # adds another index column so scatterplots work for some unknown reason
        data[stable_symbol]['time'] = data[stable_symbol].index
        data[stable_symbol].plot.scatter(x='time', y='buy_price', ax=ax, marker='^', c='g', s=50, label='buy')
        data[stable_symbol].plot.scatter(x='time', y='sell_price', ax=ax, marker='v', c='r', s=50, label='sell')
        plt.show()

# back tests strategy
def backtest(data):
    for stable_symbol in STABLE_SYMBOLS:
        df = data[stable_symbol]
        usd_bal = START_USD_BALANCE
        eur_bal = 0
        eur_start = START_USD_BALANCE / df['close'].iloc[0]
        eur_start_str = '{:0.0{}f}'.format(eur_start, 2)
        print(f'\n\n{LINE}')
        print(f'{stable_symbol} backtest performance:\n{LINE}')
        print(f'Starting balance value:\nUSD: ${usd_bal}\nEUR: {eur_start_str}€\n{LINE}')
        is_long = False
        trade_count = 0
        long_trade_count = 0
        short_trade_count = 0
        # init an empty column
        df['EUR balance'] = np.nan
        df['USD balance'] = np.nan
        # plotting balance and calculating drawdown
        max_eur_bal = 0
        max_eur_drawdown = 0
        current_eur_drawdown = 0
        max_usd_bal = 0
        max_usd_drawdown = 0
        current_usd_drawdown = 0
        last_buy_minute = False
        last_sell_minute = False
        total_long_time = timedelta()
        total_short_time = timedelta()
        short_trade_win_count = 0
        long_trade_win_count = 0
        for minute in df.index:
            if not is_long:
                if df['buy_signal'].loc[minute]:
                    # buy
                    trade_count += 1
                    eur_bal = usd_bal / df['buy_price'].loc[minute]
                    usd_str = '{:0.0{}f}'.format(usd_bal, 2)
                    eur_str = '{:0.0{}f}'.format(eur_bal, 2)
                    print(f'{trade_count}. buy {eur_str}EUR for {usd_str}USD')
                    is_long = True
                    df.loc[minute, 'EUR balance'] = eur_bal
                    df.loc[minute, 'USD balance'] = usd_bal
                    usd_bal = 0
                    # calculates trade durations
                    last_buy_minute = minute
                    # if we have already sold before
                    if last_sell_minute:
                        short_trade_count += 1
                        total_short_time += minute - last_sell_minute
                        if df.loc[last_sell_minute, 'close'] > df.loc[minute, 'close']:
                            short_trade_win_count += 1
            else:
                if df['sell_signal'].loc[minute]:
                    # sell
                    trade_count += 1
                    usd_bal = eur_bal * df['sell_price'].loc[minute]
                    usd_str = '{:0.0{}f}'.format(usd_bal, 2)
                    eur_str = '{:0.0{}f}'.format(eur_bal, 2)
                    print(f'{trade_count}. sell {eur_str}EUR for {usd_str}USD')
                    eur_bal = 0
                    is_long = False
                    last_sell_minute = minute
                    # if there was a buy already
                    if last_buy_minute:
                        long_trade_count += 1
                        total_long_time += minute - last_buy_minute
                        if df.loc[last_buy_minute, 'close'] < df.loc[minute, 'close']:
                            long_trade_win_count += 1

            # balance graph and drawdown logic
            if df['EUR balance'].loc[minute]:
                current_eur_balance = df['EUR balance'].loc[minute]
                current_usd_balance = df.loc[minute, 'USD balance']
                if max_eur_bal != 0:
                    current_eur_drawdown = ((max_eur_bal-current_eur_balance)/max_eur_bal) * 100
                if current_eur_balance > max_eur_bal:
                    max_eur_bal = current_eur_balance
                elif current_eur_drawdown > max_eur_drawdown:
                    max_eur_drawdown = current_eur_drawdown

                if max_usd_bal != 0:
                    current_usd_drawdown = ((max_usd_bal-current_usd_balance)/max_usd_bal) * 100
                if current_usd_balance > max_usd_bal:
                    max_usd_bal = current_usd_balance
                elif current_usd_drawdown > max_usd_drawdown:
                    max_usd_drawdown = current_usd_drawdown

        average_long_trade_duration = total_long_time / long_trade_count
        average_short_trade_duration = total_short_time / short_trade_count
        print(LINE)
        print(f'Trade count (buys + sells): {trade_count}')
        print(f'Average long trade duration (buy -> sell): {average_long_trade_duration}')
        print(f'Long trade wins/losses: {long_trade_win_count}/{long_trade_count-long_trade_win_count} = {long_trade_win_count/long_trade_count*100}% winrate')
        print(f'Average short trade duration (sell -> buy): {average_short_trade_duration}')
        print(f'Short trade wins/losses: {short_trade_win_count}/{short_trade_count-short_trade_win_count} = {short_trade_win_count/short_trade_count * 100}% winrate')
        print(f'Overall winrate: {(long_trade_win_count+short_trade_win_count)/(short_trade_count+long_trade_count)*100}%')
        if is_long:
            usd_value = eur_bal * df["close"].iloc[-1]
            profit_usd = ((usd_value - START_USD_BALANCE)/START_USD_BALANCE) * 100
            profit_eur = ((eur_bal - eur_start)/eur_start) * 100
            print('Profit (USD%): {:0.0{}f}%'.format(profit_usd, 2))
            print('Profit (EUR%): {:0.0{}f}%'.format(profit_eur, 2))
            usd_str = '{:0.0{}f}'.format(usd_value, 2)
            eur_str = '{:0.0{}f}'.format(eur_bal, 2)
            print(f'Final balance value:\nUSD: ${usd_str}\nEUR: {eur_str}€')
        else:
            eur_value = usd_bal / df["close"].iloc[-1]
            profit_usd = ((usd_bal - START_USD_BALANCE)/START_USD_BALANCE) * 100
            profit_eur = ((eur_value - eur_start)/eur_start) * 100
            print('Profit (USD%): {:0.0{}f}%'.format(profit_usd, 2))
            print('Profit (EUR%): {:0.0{}f}%'.format(profit_eur, 2))
            usd_str = '{:0.0{}f}'.format(usd_bal, 2)
            eur_str = '{:0.0{}f}'.format(eur_value, 2)
            print(f'Final balance values:\nUSD: ${usd_str}\nEUR: {eur_str}€')
        print('Max drawdown (USD%): {:0.0{}f}%'.format(max_usd_drawdown, 2))
        print('Max drawdown (EUR%): {:0.0{}f}%'.format(max_eur_drawdown, 2))

        # plotting balance graph
        fig = plt.figure()
        ax = fig.add_axes([0.07, 0.1, 0.85, 0.8])
        ax.set_title(f'{stable_symbol} backtest balance graph in EUR and USD (not normalized %)')
        # plots prices and trades
        df[df['EUR balance'] > 0].plot(y='EUR balance', ax=ax, label='EUR', color='b')
        df[df['USD balance'] > 0].plot(y='USD balance', ax=ax, label='USD', color='g')
        plt.show()

def main():
    make_dirs()
    data = populate_data_dict()
    if FILL_GAPS:
        data = fill_gaps(data)
    data = plot_price_diff(data)
    data = populate_trades(data)
    plot_trades(data)
    backtest(data)

if __name__ == '__main__':
    main()