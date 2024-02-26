import backtrader as bt
import pandas as pd
import ccxt
import datetime
import numpy as np
from strategies.dca_size_multiplier_tp import DCAStrategyCompound2
from strategies.dca_macd import DCAMacd
from prettytable import PrettyTable
from customStats.profitAndLoss import PNLPercentage
from customStats.totalTestLengthStats import TotalTestLengthStats
from utils.other import CCXTData
from utils.dataManipulation import fetch_and_prepare_data

# exchange = ccxt.bybit({
#     'options': {'defaultType': 'swap',
#                 'defaultContractType': 'perpetual'},
#     'enableRateLimit': True
# })

exchange = ccxt.binance({
    'options': {'defaultType': 'swap',
                'defaultContractType': 'perpetual'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})



# Create the table with these keys as column headers
table = PrettyTable()


if __name__ == "__main__":

    '''
    Symbol settings 
    start_date = None Or  '2024-01-01T00:00:00Z'  for start
    end_date = None Or  '2024-02-024T00:00:00Z'  for start

    - if start adn end None it will take latest N candles returned fom exchange max in single api call 

    '''
    symbol = "ETH/USDT"
    timeframe = '1m'
    start_date = '2024-01-01T00:00:00Z'  # None Or  '2023-01-01T00:00:00Z'  for start
    end_date = None     # None Or  '2023-01-01T00:00:00Z'  for end

                                                   
    df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)

    data = CCXTData(dataname=df)
    

    # Initiate framework 
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    

    # Adding analyzer 
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='transactions')
    cerebro.addanalyzer(PNLPercentage, _name='pnl_percentage')
    cerebro.addanalyzer(TotalTestLengthStats, _name='totals_length')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

    cerebro.broker.set_cash(300)
    cerebro.broker.setcommission(commission=.002)


    '''
    Uncomment this code bellow to run single strategy test, and comment the optimizations section bellow after #########
    '''


    '''
    AVAX 1 Min
+--------------+-----------------------+-------------------------------+-----------------------+------------------------+------------------+--------------+--------------------+
|   Strategy   | price_drop_percentage | initial_trade_size_percentage | trade_size_multiplier | take_profit_percentage | Max Drawdown (%) | Transactions |        PNL%        |
+--------------+-----------------------+-------------------------------+-----------------------+------------------------+------------------+--------------+--------------------+
| Strategy 170 |          8.0          |              4.0              |          4.0          |          4.5           |       6.07       |      63      | 21.712118158938665 |
| Strategy 169 |          8.0          |              4.0              |          4.0          |          4.0           |       7.46       |      74      | 17.293545062380602 |
| Strategy 159 |          8.0          |              2.0              |          5.0          |          5.0           |       4.22       |      64      | 16.998701671600458 |
| Strategy 85  |          7.5          |              2.0              |          5.0          |          4.0           |       5.21       |      75      | 16.867600545438066 |
| Strategy 84  |          7.5          |              2.0              |          4.5          |          6.5           |       9.68       |      39      | 16.22270508570537  |

    '''
    # # STRATEGIES
    # cerebro.addstrategy(DCAStrategyCompound2, 
    #                     price_drop_percentage = 8,
    #                     initial_trade_size_percentage=2,
    #                     trade_size_multiplier=5,
    #                     take_profit_percentage=5,
    #                     log=False)


    # starting_portfolio_value = cerebro.broker.getvalue()
    # print(f'Starting Portfolio Value: {starting_portfolio_value:.2f}')
    # result = cerebro.run()
    # final_portfolio_value = cerebro.broker.getvalue()
    # print(f'Final Portfolio Value: {final_portfolio_value:.2f}')
    # # Correct way to access the analyzers for the first strategy instance
    # first_strategy = result[0]  # Access the first strategy instance

    # returns_analysis = first_strategy.analyzers.returns.get_analysis()
    # print("Max Drawdown:", first_strategy.analyzers.drawdown.get_analysis()['max']['drawdown'])
    # print(f"Total Return: {returns_analysis['rtot']:.4f} (Total return over the period)")
    # print(f"Average Daily Return: {returns_analysis['ravg']:.4f}")
    # print(f"Normalized Return: {returns_analysis['rnorm']:.4f} (Normalized over the period)")
    # print(f"Normalized Return over 100: {returns_analysis['rnorm100']:.2f}%")

    # pnl_percentage_analysis = first_strategy.analyzers.pnl_percentage.get_analysis()
    # print(f"PNL Percentage: {pnl_percentage_analysis['pnl_percentage']:.2f}% (Profit and Loss Percentage)")


    # sqn_analysis = first_strategy.analyzers.sqn.get_analysis()
    # print(f"SQN: {sqn_analysis['sqn']:.2f}")



    # total_duration_analysis = first_strategy.analyzers.totals_length.get_analysis()

    # results = {
    #     "results":{
    #         "totalDays": total_duration_analysis['total_days'],
    #         "totalWeeks": total_duration_analysis['total_weeks'],
    #         "totalMonths": total_duration_analysis['total_months'],
    #         "totalQuarters": total_duration_analysis['total_quarters'],
    #         "totalYears": total_duration_analysis['total_years'],

    #         "systemQualityNumber":sqn_analysis['sqn']
    #     }
    # }

    # from pprint import pprint
    # pprint(results)

    # cerebro.plot(style='candlestick')

####################################### OPTIMIZATION ##############################################################

    '''
    Uncomment bellow code and comment above code for single test to run optimizations
    '''

    # Active filtering
    apply_filters = True  # Apply filter for strategies
    mdd_limit = 10  # mdd < mdd_limit
    pnl_perc_limit = 10  # PNL > pnl_perc_limit


    # Constructing the table
    all_keys = ["price_drop_percentage", "initial_trade_size_percentage", "trade_size_multiplier", 
                "take_profit_percentage", "Max Drawdown (%)", "Transactions", "PNL%"]
    
    table.field_names = ["Strategy"] + all_keys


    # Run cerebro
    cerebro.optstrategy(
        DCAStrategyCompound2,
        price_drop_percentage = np.arange(2.0, 8.0, 1),
        initial_trade_size_percentage=(2.0, 6.0, 1 ),
        trade_size_multiplier=np.arange(1.0, 6.0, 1),
        take_profit_percentage=np.arange(4.0, 7.0, 1)
    )

    optimized_runs = cerebro.run(maxcpus=4)
    strategy_count = 0

    # Store all strategies so they can be  ordered later
    all_strategies = []

    # Processed results
    for run in optimized_runs:
        for strategy in run:
            strategy_count += 1
            params = strategy.params._getkwargs()  
            params = strategy.params._getkwargs()  
            sharpe_ratio = strategy.analyzers.sharpe_ratio.get_analysis()
            drawdown = strategy.analyzers.drawdown.get_analysis()
            returns = strategy.analyzers.returns.get_analysis()
            transactions = strategy.analyzers.transactions.get_analysis()
            pnl_percentage = strategy.analyzers.pnl_percentage.get_analysis()
            
            condition = float(drawdown['max']['drawdown']) < mdd_limit and pnl_percentage['pnl_percentage'] > pnl_perc_limit
            if not apply_filters or (apply_filters and condition):
                metrics = {
                    "Max Drawdown (%)": f"{drawdown['max']['drawdown']:.2f}",
                    "Transactions": len(transactions),
                    "PNL%": pnl_percentage['pnl_percentage']  # Store as float for sorting
                }

                combined_info = {**params, **metrics, "Strategy Name": f"Strategy {strategy_count}"}

                # Append the combined info to the list instead of directly to the table
                all_strategies.append(combined_info)


    # sort strategies
    sorted_strategies = sorted(all_strategies, key=lambda x: float(x["PNL%"]), reverse=True)


    # Add each sorted strategy to the table
    for strategy_info in sorted_strategies:
        row = [strategy_info["Strategy Name"]]
        for key in all_keys:
            row_value = strategy_info.get(key, "N/A")
            row.append(row_value)
        table.add_row(row)

    print(table)





