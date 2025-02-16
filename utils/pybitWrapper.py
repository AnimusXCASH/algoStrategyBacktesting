from pybit.unified_trading import HTTP
from pandas import DataFrame
import pandas as pd
from pprint import pprint
from decimal import Decimal, ROUND_HALF_UP

from pybit.unified_trading import HTTP
from pandas import DataFrame
import pandas as pd
from colorama import Fore, Style, init

init(autoreset=True)


class BybitWrapper:
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = False):
        self.instance = HTTP(api_key=api_key, api_secret=api_secret, testnet=testnet, log_requests=True)
        self.symbol = None
        self.category = None
        self.symbol_trading_info = dict()
        self.buy_leverage = None
        self.sell_leverage = None
        self.orders = []
    
    def symbol_setter(self, symbol: str ="BTCUSDT"):
        """
        This function needs to run after instantiation to create trading data for the symbol 
        """
        print(Fore.LIGHTYELLOW_EX + f'Setting up trading rules, category, class variables for {symbol}...')
        symbol_rules = self.__get_symbol_rules(symbol=symbol)
        if symbol_rules:
            self.symbol_trading_info = {
                # Quantity Information
                "qtyStep": float(symbol_rules["lotSizeFilter"]["qtyStep"]),
                "minOrderQty": float(symbol_rules["lotSizeFilter"]["minOrderQty"]),
                "maxOrderQty": float(symbol_rules["lotSizeFilter"]["maxOrderQty"]),
                "minNotionalValue": float(
                    symbol_rules["lotSizeFilter"]["minNotionalValue"]
                ),
                # Price Information
                "tickSize": float(symbol_rules["priceFilter"]["tickSize"]),
                "minPrice": float(symbol_rules["priceFilter"]["minPrice"]),
                "maxPrice": float(symbol_rules["priceFilter"]["maxPrice"]),
                "priceScale": int(
                    symbol_rules["priceScale"]
                ),  # Note: Convert to int for precision handling
                # Leverage Information
                "maxLeverage": float(symbol_rules["leverageFilter"]["maxLeverage"]),
                "minLeverage": float(symbol_rules["leverageFilter"]["minLeverage"]),
                "leverageStep": float(symbol_rules["leverageFilter"]["leverageStep"]),
            }

            self.symbol = symbol
            self.category = "inverse"
            print(Fore.GREEN + f"Successfully set trade info for symbol: {self.symbol}")
        else:
            print(Fore.RED + f"Failed to set trade info for symbol: {symbol}")
            exit()

        print(Fore.LIGHTYELLOW_EX + f'Reviewing open orders on account for {self.symbol}...')
        orders = self.get_realtime_orders(category=self.category, symbol=self.symbol)
        self.orders = [x['orderId'] for x in orders['result']['list']] if len(orders['result']['list']) > 0 else []

        if not self.orders or len(self.orders) == 0:
            print(Fore.GREEN + f"No active orders")
            # self.set_leverage(buyLeverage=1, sellLeverage=1)
        else:
            print(Fore.GREEN + 'Orders are already deployed. Continue monitoring')
        
    
    def round_to_step(self, value, step):
        """
        :param value: The original value to round.
        :param step: The step size to round to.
        :return: The value rounded to the nearest multiple of step.
        """
        d_value = Decimal(str(value))
        d_step = Decimal(str(step))
        number_of_steps = d_value / d_step
        rounded_steps = number_of_steps.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        adjusted_value = rounded_steps * d_step
        return float(adjusted_value)

    def __number_fmt(self, order_details):
        """
        Formats the order data according to exchange rules.

        :param order_details: Dictionary containing order data.
        :return: Formatted order data dictionary.
        """
        # Extract exchange parameters
        tick_size = self.symbol_trading_info["tickSize"]
        qty_step = self.symbol_trading_info["qtyStep"]
        min_price = self.symbol_trading_info["minPrice"]
        max_price = self.symbol_trading_info["maxPrice"]
        min_order_qty = self.symbol_trading_info["minOrderQty"]
        max_order_qty = self.symbol_trading_info["maxOrderQty"]
        min_notional_value = self.symbol_trading_info["minNotionalValue"]

        # Adjust prices
        price_keys = ["L_0", "L_1", "L_2", "TP_0", "TP_1", "TP_2", "SL"]
        for key in price_keys:
            value = order_details[key]
            adjusted_value = self.round_to_step(value, tick_size)
            # Ensure the price is within min and max limits
            adjusted_value = max(min_price, min(max_price, adjusted_value))
            order_details[key] = adjusted_value

        # Adjust quantities
        qty_keys = ["QTY_0", "QTY_1", "QTY_2"]
        for key in qty_keys:
            value = order_details[key]
            adjusted_value = self.round_to_step(value, qty_step)
            # Ensure the quantity is within min and max limits
            adjusted_value = max(min_order_qty, min(max_order_qty, adjusted_value))
            order_details[key] = adjusted_value

        # Check and adjust for minimum notional value (price * quantity >= minNotionalValue)
        for i in range(3):
            price_key = f"L_{i}"
            qty_key = f"QTY_{i}"
            price = order_details[price_key]
            qty = order_details[qty_key]
            notional_value = price * qty
            if notional_value < min_notional_value:
                # Adjust quantity to meet minNotionalValue
                adjusted_qty = min_notional_value / price
                adjusted_qty = self.round_to_step(adjusted_qty, qty_step)
                # Ensure the adjusted quantity is within limits
                adjusted_qty = max(min_order_qty, min(max_order_qty, adjusted_qty))
                order_details[qty_key] = adjusted_qty
                # Optionally, log or print a warning
                print(
                    f"Adjusted {qty_key} to meet minimum notional value: {adjusted_qty}"
                )

        return order_details

    def create_batch_orders(self, order_data: dict) -> None:
        """
        Function to execute batch limit orders to the Bybit exchange, including TP and SL based on the data from calculus class.
        the function itself handles also price and quantity formatting
        """
        # Format the order details according to exchange rules
        fmt_det = self.__number_fmt(order_details=order_data)

        if not hasattr(self, 'orders'):
            self.orders = []

        self.orders.clear()

        # Loop over the three orders
        for i in ["0", "1", "2"]:
            # Prepare order parameters
            order_params = {
                "category": "inverse",
                "symbol": self.symbol,
                "side": fmt_det["side"],
                "orderType": "Limit",
                "qty": str(fmt_det[f"QTY_{i}"]),
                "price": str(fmt_det[f"L_{i}"]),
                "timeInForce": "GTC",
                "positionIdx": 0,  # one way mode set
                "takeProfit": str(fmt_det[f"TP_{i}"]),
                "stopLoss": str(fmt_det["SL"]),
                "tpTriggerBy": "LastPrice",  
                "slTriggerBy": "LastPrice", # MarkPrice
            }

            # Place the order
            result = self.instance.place_order(**order_params)

            # Check for successful order placement
            if result.get("retMsg") == "OK" and result.get("result"):
                order_id = result["result"]["orderId"]
                self.orders.append(order_id)
                print(f"Order {i} placed successfully: Order ID {order_id}")
            else:
                print(f"Failed to place Order {i}: {result.get('retMsg')}")

        # AT position request there shoul always be three order id's in an array therefore if not successfull the script should remove others which were active and exit
        if len(self.orders) < 3:
            print("Not all orders were placed successfully. Canceling any placed orders.")
            # Cancel any previously placed orders
            for order_id in self.orders:
                cancel_result = self.instance.cancel_order(
                    category="inverse",
                    symbol=self.symbol,
                    orderId=order_id
                )
                if cancel_result.get("retMsg") == "OK":
                    print(f"Successfully canceled order {order_id}")
                else:
                    print(f"Failed to cancel order {order_id}: {cancel_result.get('retMsg')}")
            self.orders.clear()
            print("Exiting bot due to order placement failure.")
            exit()
        else:
            print("All orders placed successfully.")
            return self.orders

    def _get_dataframe(self, data: list) -> DataFrame:
        columns = ["start", "Open", "High", "Low", "Close", "Volume", "turnover"]
        df = pd.DataFrame(data, columns=columns)

        # Convert the 'start' column to numeric, then to datetime
        df["start"] = pd.to_numeric(df["start"], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["start"], unit="ms", errors="coerce")

        # Drop rows with invalid timestamps
        df = df.dropna(subset=["timestamp"])

        # Convert price/volume columns to numeric
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop unwanted columns
        df_cleaned = df.drop(columns=["start", "turnover"])

        # Reverse the order so that the earliest candle is at the top
        df_inversed = df_cleaned.iloc[::-1].reset_index(drop=True)

        # Remove the latest candle (last row) because it may be incomplete (not a closed candle)
        df_final = df_inversed.iloc[:-1].reset_index(drop=True)
        return df_final



    def __get_symbol_rules(self, symbol="BTCUSDT") -> dict:
        try:
            data = self.instance.get_instruments_info(category="inverse", symbol=symbol)
            if (
                "result" in data
                and "list" in data["result"]
                and len(data["result"]["list"]) > 0
            ):
                symbol_rules = data["result"]["list"][0]
                return symbol_rules
            else:
                print(
                    Fore.RED
                    + f"Error: Symbol {symbol} rules not found in response."
                    + Style.RESET_ALL
                )
                return {}
        except Exception as e:
            print(
                Fore.RED
                + f"An error occurred while fetching symbol rules: {e}"
                + Style.RESET_ALL
            )
            return {}

    def get_positions(self, category: str = "inverse") -> dict:
        """
        Get all positions for the symbol
        """
        try:
            position_data = self.instance.get_positions(
                category=category, symbol=self.symbol
            )
            return position_data["result"]["list"][0]
        except Exception as e:
            print(Fore.RED + f"Error fetching positions: {e}" + Style.RESET_ALL)
            return {}

    def set_leverage(self, category: str = "inverse", buyLeverage=10, sellLeverage=10):
        """
        #  USe this function to set the required leverage

        {
            "retCode": 0,
            "retMsg": "OK",
            "result": {},
            "retExtInfo": {},
            "time": 1672281607343
        }

        """

        self.buy_leverage = buyLeverage
        self.sell_leverage = sellLeverage
        try:
            result = self.instance.set_leverage(
                category=category,
                symbol=self.symbol,
                buyLeverage=str(self.buy_leverage),
                sellLeverage=str(self.sell_leverage),
            )
            if result["retMsg"] != "OK":
                print(Fore.RED + "Failed to set leverage." + Style.RESET_ALL)
                return True
            else:
                print(Fore.GREEN + "Leverage has been set." + Style.RESET_ALL)
                return True
        except Exception as e:
            print(Fore.RED + f"Error setting leverage: {e}" + Style.RESET_ALL)

    def get_wallet_balance(self, coin_balance: str = "USDT"):
        try:
            wallet_data = self.instance.get_wallet_balance(accountType="CONTRACT")
            coin_info = next(
                (
                    coin
                    for coin in wallet_data["result"]["list"][0]["coin"]
                    if coin["coin"] == coin_balance
                ),
                None,
            )
            return coin_info
        except Exception as e:
            print(Fore.RED + f"Error fetching wallet balance: {e}" + Style.RESET_ALL)
            return {}

    def get_kline_data(
        self,
        category="inverse",
        interval=1,
        limit=500,
        df_return=True,
        start=None,
        end=None,
    ):
        query = {
            "category": category,
            "symbol": self.symbol,
            "interval": str(interval),
            "limit": limit,
        }

        if start and start > 9999999999:
            start = start // 1000
        if end and end > 9999999999:
            end = end // 1000

        if start:
            query["start"] = start
        if end:
            query["end"] = end

        try:
            kline_data = self.instance.get_kline(**query)
            klines = kline_data["result"]["list"]
            if df_return:
                return self._get_dataframe(klines)
            else:
                return klines
        except Exception as e:
            print(Fore.RED + f"Error fetching kline data: {e}" + Style.RESET_ALL)
            return pd.DataFrame() if df_return else []

    def cancel_all_orders(self) -> None:
        """
        Cancels all open orders stored in self.orders based on their order IDs.

        For each order in self.orders:
            - Check if the order is still open (status: "New", "Active", "PartiallyFilled").
            - If open, attempt to cancel the order.
            - Remove the order ID from self.orders if cancellation is successful.
            - Log the result of each cancellation attempt.

        After processing all orders, self.orders will only contain IDs of orders that are not open or failed to cancel.
        """
        if not hasattr(self, 'orders') or not self.orders:
            print("No orders to cancel.")
            return

        print(f"Initiating cancellation of {len(self.orders)} orders...")

        for order_id in self.orders.copy():
            try:
                # Fetch order details to check its current status
                response = self.instance.get_open_orders(
                    category="inverse",
                    symbol=self.symbol,
                    orderId=order_id
                )
            except Exception as e:
                print(f"Exception occurred while fetching Order {order_id} status: {e}")
                continue  

            # Validate API response
            if response.get("retMsg") != "OK" or not response.get("result"):
                print(f"Failed to fetch status for Order {order_id}: {response.get('retMsg')}")
                continue  

            # Extract order status
            order_status = response["result"]["list"][0]["orderStatus"]
            print(f"Order {order_id} current status: {order_status}")

            open_statuses = ["New", "Active", "PartiallyFilled"]

            if order_status in open_statuses:
                try:
                    # Attempt to cancel the open order
                    cancel_response = self.instance.cancel_order(
                        category="inverse",
                        symbol=self.symbol,
                        orderId=order_id
                    )
                except Exception as e:
                    print(f"Exception occurred while canceling Order {order_id}: {e}")
                    continue  # Skip to the next order

                # Check if cancellation was successful
                if cancel_response.get("retMsg") == "OK" and cancel_response.get("result"):
                    print(f"Successfully canceled Order {order_id}.")
                    self.orders.remove(order_id)  # Remove from orders list
                else:
                    print(f"Failed to cancel Order {order_id}: {cancel_response.get('retMsg')}")
            else:
                print(f"Order {order_id} is already {order_status} and does not need to be canceled.")
                self.orders.remove(order_id)  # Remove non-open orders from the list

        print("Cancellation process completed.")

    def get_realtime_orders(self, category: str = "inverse", symbol: str = None) -> dict:
        """
        This gives all open order for the symbol
        """
        try:
            orders = self.instance.get_open_orders(category=category, symbol=symbol)
            return orders
        except Exception as e:
            print(Fore.RED + f"(get_realtime_orders()) -> Error fetching realtime orders: {e}")
            exit()

    def check_orders_status(self) -> int:
        """
        Checks the status of all placed orders.
        Returns:
            1 if at least one main order has been filled.
            2 if at least one TP or SL has been triggered.
            0 if none of the orders have been triggered yet.
        """

        if not self.orders:
            print("No orders active to be checked")
            return None

        triggered_main = False
        triggered_tp_sl = False

        for order_id in self.orders:
            try:
                # Fetch order details
                response = self.instance.get_open_orders(
                    category="inverse",
                    symbol=self.symbol,
                    orderId=order_id
                )
            except Exception as e:
                print(f"Exception occurred while fetching Order {order_id} status: {e}")
                continue  

            # Check if the API call was successful
            if response.get("retMsg") != "OK" or not response.get("result"):
                print(f"Failed to fetch status for Order {order_id}: {response.get('retMsg')}")
                continue  
            
            # Extract the order status
            order_status = response["result"]["list"][0]["orderStatus"]
            print(f"Order {order_id} status: {order_status}")

            # Check main order status
            if order_status in ["PartiallyFilled", "Filled"]:
                triggered_main = True

            if triggered_main:
                try:
                    position_info = self.instance.get_positions(
                        category=self.category,
                        symbol=self.symbol
                    )
                except Exception as e:
                    print(f"Exception occurred while fetching position status: {e}")
                    continue

                if position_info.get("retMsg") != "OK" or not position_info.get("result"):
                    print(f"Failed to fetch position status: {position_info.get('retMsg')}")
                    continue

                try:
                    position = position_info["result"]['list'][0]
                except (IndexError, KeyError) as e:
                    print(f"Error accessing position data: {e}")
                    continue
                
                # This has values either Buy, Sell if position is open or than string 'None" if there is no positoin anymore open which would indicate that either tp or sl has been reached already
                side = position.get("side")
                
                if side == 'None':
                    triggered_tp_sl = True

        if triggered_tp_sl:
            return 2  # At least one TP or SL has been triggered
        elif triggered_main:
            return 1  # At least one main order has been filled
        elif len(self.orders) == 0:
            return None
        else:
            return 0  # No orders have been triggered yet


