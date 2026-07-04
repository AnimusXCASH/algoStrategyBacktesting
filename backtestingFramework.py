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
import math


exchange = ccxt.binance({
    'options': {'defaultType': 'swap',
                'defaultContractType': 'perpetual'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})



# Create the table with these keys as column headers
table = PrettyTable()




if __name__ == "__main__":

    symbol = "SOL/USDT"
    timeframe = "15m"
    start_date = "2024-05-05T00:00:00Z"
    end_date = None

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
    cerebro.addobserver(bt.observers.BuySell)

    cerebro.broker.set_cash(10000)
    cerebro.broker.setcommission(commission=.002)


    cerebro.addstrategy(MyStrategy)


    starting_portfolio_value = cerebro.broker.getvalue()
    print(f'Starting Portfolio Value: {starting_portfolio_value:.2f}')
    result = cerebro.run()
    final_portfolio_value = cerebro.broker.getvalue()
    print(f'Final Portfolio Value: {final_portfolio_value:.2f}')
    first_strategy = result[0]  # Access the first strategy instance

    returns_analysis = first_strategy.analyzers.returns.get_analysis()
    print("Max Drawdown:", first_strategy.analyzers.drawdown.get_analysis()['max']['drawdown'])
    print(f"Total Return: {returns_analysis['rtot']:.4f} (Total return over the period)")
    print(f"Average Daily Return: {returns_analysis['ravg']:.4f}")
    print(f"Normalized Return: {returns_analysis['rnorm']:.4f} (Normalized over the period)")
    print(f"Normalized Return over 100: {returns_analysis['rnorm100']:.2f}%")

    pnl_percentage_analysis = first_strategy.analyzers.pnl_percentage.get_analysis()
    print(f"PNL Percentage: {pnl_percentage_analysis['pnl_percentage']:.2f}% (Profit and Loss Percentage)")


    sqn_analysis = first_strategy.analyzers.sqn.get_analysis()
    print(f"SQN: {sqn_analysis['sqn']:.2f}")



    total_duration_analysis = first_strategy.analyzers.totals_length.get_analysis()

    results = {
        "results":{
            "totalDays": total_duration_analysis['total_days'],
            "totalWeeks": total_duration_analysis['total_weeks'],
            "totalMonths": total_duration_analysis['total_months'],
            "totalQuarters": total_duration_analysis['total_quarters'],
            "totalYears": total_duration_analysis['total_years'],

            "systemQualityNumber":sqn_analysis['sqn']
        }
    }

    from pprint import pprint
    pprint(results)

    cerebro.plot(style='candlestick', trades=True)




# ####################################### OPTIMIZATION ##############################################################

#     # Active filtering
#     apply_filters = False  # Apply filter for strategies
#     mdd_limit = 20  # mdd < mdd_limit
#     pnl_perc_limit = 0  # PNL > pnl_perc_limit


#     # Constructing the table
#     all_keys = ["cycle_strength_threshold", "bullish_cycle_range", "bearish_cycle_range", "Max Drawdown (%)", "Transactions", "PNL%"]
    
#     table.field_names = ["Strategy"] + all_keys


#     cycle_strength_threshold_range = np.arange(10,50,2)



#     # Calculate the number of values for each parameter
    
#     # num_price_drop_percentage = len(cycle_strength_threshold_range) + len(period_range) + len(bins_range)


#     # Calculate the total number of tests
#     # total_tests = (num_price_drop_percentage)
#     # print(f"Total number of tests: {total_tests}")

#     # Run cerebro
#     # cerebro.optstrategy(
#     #     EBTIStrategy,
#     #     entropy_threshold =entropy_threshold_range,
#     #     period=period_range, 
#     #     bins=bins_range
#     # )
#     cerebro.optstrategy(
#         CycleStrategy,
#         cycle_strength_threshold=range(5, 15, 5),  # Example: Optimizing from 5 to 10 in steps of 5
#         bullish_cycle_start=range(10, 15, 5),  # Adjust ranges as needed
#         bullish_cycle_end=range(15, 25, 5),
#         bearish_cycle_start=range(20, 25, 5),
#         bearish_cycle_end=range(25, 35, 5),
#     )

#     optimized_runs = cerebro.run(maxcpus=4)
#     strategy_count = 0

#     # Store all strategies so they can be  ordered later
#     all_strategies = []

#     # Processed results
#     for run in optimized_runs:
#         for strategy in run:
#             strategy_count += 1
#             params = strategy.params._getkwargs()  
#             params = strategy.params._getkwargs()  
#             sharpe_ratio = strategy.analyzers.sharpe_ratio.get_analysis()
#             drawdown = strategy.analyzers.drawdown.get_analysis()
#             returns = strategy.analyzers.returns.get_analysis()
#             transactions = strategy.analyzers.transactions.get_analysis()
#             pnl_percentage = strategy.analyzers.pnl_percentage.get_analysis()
            
#             condition = float(drawdown['max']['drawdown']) < mdd_limit and pnl_percentage['pnl_percentage'] > pnl_perc_limit
#             if not apply_filters or (apply_filters and condition):
#                 metrics = {
#                     "Max Drawdown (%)": f"{drawdown['max']['drawdown']:.2f}",
#                     "Transactions": len(transactions),
#                     "PNL%": pnl_percentage['pnl_percentage']  # Store as float for sorting
#                 }

#                 combined_info = {**params, **metrics, "Strategy Name": f"Strategy {strategy_count}"}

#                 # Append the combined info to the list instead of directly to the table
#                 all_strategies.append(combined_info)


#     # sort strategies
#     sorted_strategies = sorted(all_strategies, key=lambda x: float(x["PNL%"]), reverse=True)


#     # Add each sorted strategy to the table
#     for strategy_info in sorted_strategies:
#         row = [strategy_info["Strategy Name"]]
#         for key in all_keys:
#             row_value = strategy_info.get(key, "N/A")
#             row.append(row_value)
#         table.add_row(row)

#     print(table)