import backtrader as bt
import pandas as pd
import ccxt
import numpy as np
from strategies.dca_size_multiplier_tp import DCAStrategyCompound2
from prettytable import PrettyTable
from customStats.profitAndLoss import PNLPercentage
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

symbol = "BTC/USDT"
timeframe = '1h'


# Create the table with these keys as column headers
table = PrettyTable()


if __name__ == "__main__":

    df = fetch_and_prepare_data(exchange, symbol, timeframe)
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


    cerebro.broker.set_cash(100)
    cerebro.broker.setcommission(commission=.002)


    '''
    Uncomment this code bellow to run single strategy test, and comment the optimizations section bellow after #########
    '''
    # STRATEGIES
    # cerebro.addstrategy(DCAStrategyCompound2, 
    #                     price_drop_percentage = 5,
    #                     initial_trade_size_percentage=3,
    #                     trade_size_multiplier=3,
    #                     take_profit_percentage=2,
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

    # cerebro.plot(style='candlestick')

####################################### OPTIMIZATION ##############################################################

    '''
    Uncomment bellow code and comment above code for single test to run optimizations
    '''

    # Define a list of all possible parameters and metrics you want to include in the table
    all_keys = ["price_drop_percentage", "initial_trade_size_percentage", "trade_size_multiplier", 
                "take_profit_percentage", "Max Drawdown (%)", "Annualized Return (%)", 
                "Transactions", "PNL%"]
    
    table.field_names = ["Strategy"] + all_keys

    cerebro.optstrategy(
        DCAStrategyCompound2,
        price_drop_percentage = np.arange(1.0, 10.0, 1),
        initial_trade_size_percentage=np.arange(1.0, 10.0, 1),
        trade_size_multiplier=np.arange(1.0, 10.0, 1),
        take_profit_percentage=np.arange(1.0, 10.0, 1)
    )

    optimized_runs = cerebro.run(maxcpus=4)
    strategy_count = 0

    apply_filters = True  # Apply filter for strategies

    
    # Process results of each strategy in a run
    for run in optimized_runs:
        for strategy in run:
            strategy_count += 1
            params = strategy.params._getkwargs()  
            sharpe_ratio = strategy.analyzers.sharpe_ratio.get_analysis()
            drawdown = strategy.analyzers.drawdown.get_analysis()
            returns = strategy.analyzers.returns.get_analysis()
            transactions = strategy.analyzers.transactions.get_analysis()
            pnl_percentage = strategy.analyzers.pnl_percentage.get_analysis()

            # Finterss condition
            condition = float(drawdown['max']['drawdown']) < 15 and pnl_percentage['pnl_percentage'] > 5

            if not apply_filters or (apply_filters and condition):
                metrics = {
                    "Max Drawdown (%)": f"{drawdown['max']['drawdown']:.2f}",
                    "Annualized Return (%)": f"{returns['rnorm100']:.2f}",
                    "Transactions": len(transactions),
                    "PNL%": f"{pnl_percentage['pnl_percentage']:.2f}%"
                }

                combined_info = {**params, **metrics}

                # Prepare a row for the current strategy for the table
                row = [f"Strategy {strategy_count}"]
                for key in all_keys:
                    row_value = combined_info.get(key, "N/A") 
                    row.append(row_value)

                table.add_row(row)

    # Print the table after filling it with all strategies
    print(table)