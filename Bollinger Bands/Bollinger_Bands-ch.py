class Strategy(StrategyBase):
    def __init__(self):
        # 策略屬性
        self.subscribed_books = {}
        # 30 分鐘
        self.period = 30 * 60
        self.options = {}

        self.last_type = 'sell'
        self.ma_period = 20
        self.divide_quote = 0
        self.proportion = 0.2


    def on_order_state_change(self,  order):
        pass

    def trade(self, candles):
        exchange, pair, base, quote = CA.get_exchange_pair()
        
        close_price_history = [candle['close'] for candle in candles[exchange][pair]]
        high_price_history = [candle['high'] for candle in candles[exchange][pair]]
        low_price_history = [candle['low'] for candle in candles[exchange][pair]]

        # 將資料由舊到新排列
        close_price_history.reverse()
        high_price_history.reverse()
        low_price_history.reverse()

        # 轉換為 np.array
        close_price_history = np.array(close_price_history)
        high_price_history = np.array(high_price_history)
        low_price_history = np.array(low_price_history)

        close_price = close_price_history[-1]
        high_price = high_price_history[-1]

        upper, middle, lower = talib.BBANDS(close_price_history)
        ma = talib.SMA(close_price_history, self.ma_period)

        if len(ma) < 2 or len(upper) < 2:
            return []

        # 移動平均
        ma_curr = ma[-1]
        ma_prev = ma[-2]

        # 布林通道上線
        upper_curr = upper[-1]
        upper_prev = upper[-2]

        # 布林通道下線
        lower_curr = lower[-1]
        lower_prev = lower[-2]

        # 取得可用資產數量
        base_balance = CA.get_balance(exchange, base)
        quote_balance = CA.get_balance(exchange, quote)
        available_base_amount = base_balance.available
        available_quote_amount = quote_balance.available

        if self.divide_quote == 0:
            self.divide_quote = np.round(available_quote_amount* self.proportion, 5)

        # signal = 1 則買, 2 則賣, -1 賣空, -2 空單回補
        signal = 0
        amount = self.divide_quote/high_price

        # 多頭趨勢
        if ma_curr > ma_prev and upper_curr > upper_prev and lower_curr > lower_prev:
            
            # 空倉則建立多頭部位
            if available_base_amount< amount and available_base_amount > -amount:
                signal = 1

        # 超出上邊界則平倉了結獲利
        elif high_price_history[-1] > upper_curr:
            if available_base_amount > amount:
                signal = 2
                amount = available_base_amount
        
        # 空頭趨勢
        elif ma_curr < ma_prev and upper_curr < upper_prev and lower_curr < lower_prev:
            
            # 空倉則建立空頭部位做空
            if available_base_amount < amount and available_base_amount > -amount:
                signal = -1
            
            # 若持有多頭部位則賣一張
            elif available_base_amount > amount:
                signal = 2
                if available_base_amount < amount:
                    amount = available_base_amount
        
        # 超出下邊界則平倉了結獲利
        elif low_price_history[-1] < lower_curr:
            if available_base_amount < -amount:
                signal = -2
                amount = -available_base_amount
        
        # 送出訂單 - 賣空
        if signal == -1:
            self['is_shorting'] = 'true'
            amount = -amount * 1.1
            CA.log('賣空 ' + str(base))
            return [
                {
                    'exchange': exchange,
                    'amount': amount,
                    'price': -1,
                    'type': 'MARKET',
                    'pair': pair,
                    'margin': True,
                }
            ]

        # 送出訂單 - 空單回補
        elif signal == -2:
            self['is_shorting'] = 'true'
            self.divide_quote = 0
            CA.log('空單回補 ' + str(base))
            return [
                {
                    'exchange': exchange,
                    'amount': amount,
                    'price': -1,
                    'type': 'MARKET',
                    'pair': pair,
                    'margin': True,
                }
            ]

         
        # 送出訂單 - 買
        elif signal == 1:
            amount = amount * 1.1
            self['is_shorting'] = 'false'
            CA.log('買入 ' + base)
            self.last_type = 'buy'
            CA.buy(exchange, pair, amount, CA.OrderType.MARKET)
            
        # 送出訂單 - 賣
        elif signal == 2:
            self['is_shorting'] = 'false'
            self.last_type = 'sell'
            self.divide_quote = 0
            CA.log('賣出 ' + base)
            CA.sell(exchange, pair, amount, CA.OrderType.MARKET)

        return 
