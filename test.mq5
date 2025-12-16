//+------------------------------------------------------------------+
//| Script: ListAllCurrencyPairs.mq5                                 |
//+------------------------------------------------------------------+
#property script_show_inputs

void OnStart()
{
   int total = SymbolsTotal(false); // false = ALL broker symbols
   int count = 0;

   Print("Total symbols from broker: ", total);
   Print("---- Currency Pairs ----");

   for(int i = 0; i < total; i++)
   {
      string symbol = SymbolName(i, false);

      // Basic FX detection: contains 6-letter currency base
      string base = StringSubstr(symbol, 0, 6);

      if(StringLen(base) == 6 && StringFind(base, ".") == -1)
      {
         Print(symbol);
         count++;
      }
   }

   Print("---- Total FX pairs found: ", count);
}
