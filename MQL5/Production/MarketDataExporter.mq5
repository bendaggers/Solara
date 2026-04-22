//+------------------------------------------------------------------+
//| MarketDataExporter_SHORT.mq5                                     |
//| Real-time Market Data Exporter with CSV Output                   |
//| VERSION: 6.6 - FIX: exports now actually fire                    |
//|                                                                   |
//| FIXES FROM 6.5:                                                   |
//|   FIXED: CountAvailableSymbols used SymbolSelect(...,false)       |
//|          so iTime() always returned 0 → avail was always 0       |
//|          → write condition never triggered. Now uses true.        |
//|   FIXED: Initial export dedup — symbolLastCandleTime was being    |
//|          set inside the same loop tick it was checked, causing    |
//|          race where tfProcessedCount never reached avail.         |
//|          Now uses a separate tfSymbolInitDone[] bool array.       |
//|   FIXED: processedCount increment now only happens once per       |
//|          symbol per cycle (guarded by per-key processed flag).    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property link      "https://www.mql5.com"
#property version   "6.6"

// ================== SIMPLIFIED SYMBOL SELECTION ==================
input group "Symbol Selection"
input bool Major = true;
input bool Minor = true;
input bool Crosses = true;
input bool Crypto = false;
input bool XAU = false;
input bool XAG = false;
input string AdditionalSymbols = "";

// ================== MULTIPLE TIMEFRAME SELECTION ==================
input group "Timeframe Selection"
input bool TF_W1 = true;
input string W1_Filename = "";
input bool TF_D1 = true;
input string D1_Filename = "";
input bool TF_H4 = true;
input string H4_Filename = "";
input bool TF_H1 = true;
input string H1_Filename = "";
input bool TF_M30 = false;
input string M30_Filename = "";
input bool TF_M15 = true;
input string M15_Filename = "";
input bool TF_M5 = false;
input string M5_Filename = "";
input bool TF_M1 = false;
input string M1_Filename = "";

// ================== TIMING SETTINGS ==================
input group "Timing Settings"
input int WaitSecondsAfterCandleClose = 5;

// ================== DATA RETENTION SETTINGS ==================
input group "Data Retention"
input int KeepLastNCandles = 350;

// ================== FIXED INDICATOR SETTINGS ==================
const int BB_Period           = 20;
const double BB_Deviation     = 2.0;
const int RSI_Period          = 14;
const int ATR_Period          = 14;
const int SMA_Short           = 50;
const int SMA_Long            = 200;
const int Volume_SMA_Period   = 20;
const int Touch_Lookback      = 20;
const int Resistance_Lookback = 20;
const int London_Start = 8;
const int London_End   = 17;
const int NY_Start     = 13;
const int NY_End       = 22;

// ================== GLOBALS ==================
string          symbols[];
ENUM_TIMEFRAMES selectedTimeframes[];
string          customFilenames[];

// Per-symbol-timeframe key tracking
string          symbolTimeframeKeys[];
datetime        symbolLastCandleTime[];
bool            symbolInitProcessed[];   // FIX: separate flag for initial-run dedup

// Per-timeframe state
datetime        tfLastWrittenCandleTime[];
int             tfProcessedCount[];
bool            tfInitialDone[];

int             keepCandles = 3;

// ================== CandleData struct ==================
struct CandleData
{
   datetime timestamp;
   string   symbol;
   double   open, high, low, close;
   long     volume;
   double   lower_band, middle_band, upper_band;
   double   bb_touch_strength;
   double   bb_position;
   double   bb_width_pct;
   double   rsi_value;
   int      rsi_divergence;
   double   volume_ratio;
   double   candle_rejection;
   double   candle_body_pct;
   double   atr_pct;
   double   trend_strength;
   double   prev_candle_body_pct;
   double   prev_volume_ratio;
   double   gap_from_prev_close;
   double   price_momentum;
   int      prev_was_rally;
   int      previous_touches;
   int      time_since_last_touch;
   double   resistance_distance_pct;
   int      session;
   double   support_distance_pct;
   int      prev_was_selloff;
   int      close_above_ubb;
   int      high_touch_ubb;
   int      no_upper_wick_bear_reject;
   int      failed_break_ubb;
   int      bb_event_type;
   double   ubb_distance_close;
};

struct SymbolCache
{
   string          symbol;
   ENUM_TIMEFRAMES timeframe;
   CandleData      candles[];
};

SymbolCache symbolCache[];
int         cacheCount = 0;

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
datetime GetNewestCandleTime(ENUM_TIMEFRAMES tf)
{
   datetime newest = 0;
   for(int i = 0; i < cacheCount; i++)
   {
      if(symbolCache[i].timeframe != tf) continue;
      int n = ArraySize(symbolCache[i].candles);
      if(n > 0 && symbolCache[i].candles[0].timestamp > newest)
         newest = symbolCache[i].candles[0].timestamp;
   }
   return newest;
}

string GetCustomFilename(ENUM_TIMEFRAMES tf)
{
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
      if(selectedTimeframes[i] == tf && i < ArraySize(customFilenames) && customFilenames[i] != "")
         return customFilenames[i];
   return "";
}

string GetFilenameForTimeframe(ENUM_TIMEFRAMES tf)
{
   string c = GetCustomFilename(tf);
   return (c != "") ? c + ".csv" : "marketdata_" + EnumToString(tf) + ".csv";
}

int GetTFIndex(ENUM_TIMEFRAMES tf)
{
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
      if(selectedTimeframes[i] == tf) return i;
   return -1;
}

int GetKeyIndex(string symbol, ENUM_TIMEFRAMES tf)
{
   string key = symbol + "|" + IntegerToString(tf);
   for(int i = 0; i < ArraySize(symbolTimeframeKeys); i++)
      if(symbolTimeframeKeys[i] == key) return i;
   int n = ArraySize(symbolTimeframeKeys) + 1;
   ArrayResize(symbolTimeframeKeys,   n);
   ArrayResize(symbolLastCandleTime,  n);
   ArrayResize(symbolInitProcessed,   n);   // FIX: keep in sync
   symbolTimeframeKeys[n-1]    = key;
   symbolLastCandleTime[n-1]   = 0;
   symbolInitProcessed[n-1]    = false;
   return n - 1;
}

int GetCacheIndex(string symbol, ENUM_TIMEFRAMES tf)
{
   for(int i = 0; i < cacheCount; i++)
      if(symbolCache[i].symbol == symbol && symbolCache[i].timeframe == tf) return i;
   return -1;
}

int GetOrCreateCache(string symbol, ENUM_TIMEFRAMES tf)
{
   int idx = GetCacheIndex(symbol, tf);
   if(idx == -1)
   {
      idx = cacheCount++;
      ArrayResize(symbolCache, cacheCount);
      symbolCache[idx].symbol    = symbol;
      symbolCache[idx].timeframe = tf;
      ArrayResize(symbolCache[idx].candles, 0);
   }
   return idx;
}

void UpdateCacheWithLatestCandles(string symbol, ENUM_TIMEFRAMES tf, CandleData &src[])
{
   int idx = GetOrCreateCache(symbol, tf);
   ArrayResize(symbolCache[idx].candles, 0);
   int n = MathMin(ArraySize(src), keepCandles);
   for(int i = 0; i < n; i++)
   {
      int s = ArraySize(symbolCache[idx].candles) + 1;
      ArrayResize(symbolCache[idx].candles, s);
      symbolCache[idx].candles[s-1] = src[i];
   }
}

int GetAllCandlesForTimeframe(ENUM_TIMEFRAMES tf, CandleData &result[])
{
   int total = 0;
   for(int i = 0; i < cacheCount; i++)
      if(symbolCache[i].timeframe == tf) total += ArraySize(symbolCache[i].candles);
   if(total == 0) { ArrayResize(result, 0); return 0; }
   ArrayResize(result, total);
   int idx = 0;
   for(int i = 0; i < cacheCount; i++)
      if(symbolCache[i].timeframe == tf)
         for(int j = 0; j < ArraySize(symbolCache[i].candles); j++)
            result[idx++] = symbolCache[i].candles[j];
   return total;
}

// FIX: was using SymbolSelect(..., false) which doesn't add to Market Watch,
//      so iTime() returned 0 for symbols not already present → avail was
//      always 0 → write condition never triggered.
//      Must use true to match the OnTimer loop's own SymbolSelect call.
int CountAvailableSymbols(ENUM_TIMEFRAMES tf)
{
   int count = 0;
   for(int s = 0; s < ArraySize(symbols); s++)
   {
      if(!SymbolSelect(symbols[s], true)) continue;   // FIX: was false
      if(iTime(symbols[s], tf, 1) != 0) count++;
   }
   return count;
}

//+------------------------------------------------------------------+
void PrepareCustomFilenames()
{
   ArrayFree(customFilenames);
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
   {
      string cn = "";
      switch(selectedTimeframes[i])
      {
         case PERIOD_W1:  cn = W1_Filename;  break;
         case PERIOD_D1:  cn = D1_Filename;  break;
         case PERIOD_H4:  cn = H4_Filename;  break;
         case PERIOD_H1:  cn = H1_Filename;  break;
         case PERIOD_M30: cn = M30_Filename; break;
         case PERIOD_M15: cn = M15_Filename; break;
         case PERIOD_M5:  cn = M5_Filename;  break;
         case PERIOD_M1:  cn = M1_Filename;  break;
      }
      StringTrimLeft(cn); StringTrimRight(cn);
      ArrayResize(customFilenames, ArraySize(customFilenames)+1);
      customFilenames[ArraySize(customFilenames)-1] = cn;
   }
}

void PrepareTimeframeList()
{
   ArrayFree(selectedTimeframes);
   if(TF_W1)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_W1;  }
   if(TF_D1)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_D1;  }
   if(TF_H4)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_H4;  }
   if(TF_H1)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_H1;  }
   if(TF_M30) { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_M30; }
   if(TF_M15) { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_M15; }
   if(TF_M5)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_M5;  }
   if(TF_M1)  { ArrayResize(selectedTimeframes,ArraySize(selectedTimeframes)+1); selectedTimeframes[ArraySize(selectedTimeframes)-1]=PERIOD_M1;  }
   if(ArraySize(selectedTimeframes) == 0)
   {
      ArrayResize(selectedTimeframes,1); selectedTimeframes[0] = PERIOD_H4;
      Print("No timeframes selected, defaulting to H4");
   }
   PrepareCustomFilenames();
}

void PrepareSymbolList()
{
   ArrayFree(symbols);
   if(Major)
   {
      string maj[] = {"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD"};
      for(int i=0;i<ArraySize(maj);i++){ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]=maj[i];}
   }
   if(Minor)
   {
      string min[] = {"EURGBP","EURAUD","EURNZD","GBPAUD","GBPNZD","AUDNZD"};
      for(int i=0;i<ArraySize(min);i++){ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]=min[i];}
   }
   if(Crosses)
   {
      string cr[] = {"EURJPY","EURCHF","EURCAD","GBPJPY","GBPCHF","GBPCAD",
                     "AUDJPY","AUDCHF","AUDCAD","NZDJPY","NZDCHF","NZDCAD",
                     "CADJPY","CADCHF","CHFJPY"};
      for(int i=0;i<ArraySize(cr);i++){ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]=cr[i];}
   }
   if(Crypto) { ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]="BTCUSD";
                ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]="ETHUSD"; }
   if(XAU) { ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]="XAUUSD"; }
   if(XAG) { ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]="XAGUSD"; }
   if(AdditionalSymbols != "")
   {
      string extra[]; int n=StringSplit(AdditionalSymbols,',',extra);
      for(int i=0;i<n;i++){StringTrimLeft(extra[i]);StringTrimRight(extra[i]);
         if(extra[i]!=""){ArrayResize(symbols,ArraySize(symbols)+1);symbols[ArraySize(symbols)-1]=extra[i];}}
   }
   Print("Selected ",ArraySize(symbols)," symbols");
}

//+------------------------------------------------------------------+
void LogExportCompletion(string tfStr, int symbolsProcessed)
{
   string   fn  = "MarketDataExport_Log.csv";
   ushort   sep = StringGetCharacter(",", 0);
   MqlDateTime dt; TimeCurrent(dt);
   string ts = StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                            dt.year,dt.mon,dt.day,dt.hour,dt.min,dt.sec);
   int h = FileOpen(fn, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, sep);
   if(h == INVALID_HANDLE)
   {
      h = FileOpen(fn, FILE_WRITE|FILE_CSV|FILE_ANSI, sep);
      if(h != INVALID_HANDLE)
      {
         FileWrite(h, "Timestamp","Timeframe","Symbols_Processed","Candles_Kept");
         FileWrite(h, ts, tfStr, symbolsProcessed, keepCandles);
         FileClose(h);
      }
   }
   else { FileSeek(h, 0, SEEK_END); FileWrite(h, ts, tfStr, symbolsProcessed, keepCandles); FileClose(h); }
}


bool EnsureHistoryLoaded(string symbol, ENUM_TIMEFRAMES tf, int requiredBars)
{
   int attempts = 0;

   while(attempts < 5)
   {
      int bars = Bars(symbol, tf);

      if(bars >= requiredBars)
         return true;

      // Force download
      MqlRates rates[];
      CopyRates(symbol, tf, 0, requiredBars, rates);

      Sleep(200);
      attempts++;
   }

   Print("FAILED to load history: ", symbol, " ", EnumToString(tf),
         " bars=", Bars(symbol, tf), " required=", requiredBars);

   return false;
}

//+------------------------------------------------------------------+
//| OnTimer                                                          |
//+------------------------------------------------------------------+
void OnTimer()
{
   datetime now = TimeCurrent();

   for(int t = 0; t < ArraySize(selectedTimeframes); t++)
   {
      ENUM_TIMEFRAMES tf        = selectedTimeframes[t];
      int             periodSec = PeriodSeconds(tf);

      for(int s = 0; s < ArraySize(symbols); s++)
      {
         if(!SymbolSelect(symbols[s], true)) continue;

         datetime lastClosedBar  = iTime(symbols[s], tf, 1);
         if(lastClosedBar == 0) continue;

         datetime candleClosedAt = lastClosedBar + periodSec;
         if(now < candleClosedAt + WaitSecondsAfterCandleClose) continue;

         int ki = GetKeyIndex(symbols[s], tf);

         // -----------------------------------------------------------
         // Initial export: fire once per symbol per TF
         // FIX: use symbolInitProcessed[] instead of checking
         //      symbolLastCandleTime[ki]==0, because the old code set
         //      symbolLastCandleTime inside this same tick and then
         //      checked it again on the next tick — the count never
         //      reached avail reliably.
         // -----------------------------------------------------------
         if(!tfInitialDone[t])
         {
            if(!symbolInitProcessed[ki])
            {
               ProcessLastNCandles(symbols[s], tf);
               symbolLastCandleTime[ki]  = lastClosedBar;
               symbolInitProcessed[ki]   = true;   // FIX: set AFTER processing
               tfProcessedCount[t]++;
            }
         }
         // -----------------------------------------------------------
         // Live export: a new candle has closed since last write
         // -----------------------------------------------------------
         else if(lastClosedBar > tfLastWrittenCandleTime[t])
         {
            if(symbolLastCandleTime[ki] < lastClosedBar)
            {
               ProcessLastNCandles(symbols[s], tf);
               symbolLastCandleTime[ki] = lastClosedBar;
               tfProcessedCount[t]++;
            }
         }
      } // end symbol loop

      // ---------------------------------------------------------------
      // Write CSV when all available symbols collected for this TF
      // ---------------------------------------------------------------
      int avail = CountAvailableSymbols(tf);   // FIX: now returns correct count
      if(avail > 0 && tfProcessedCount[t] >= avail)
      {
         datetime newest = GetNewestCandleTime(tf);

         if(newest > tfLastWrittenCandleTime[t])
         {
            WriteCacheToCSV(tf);
            LogExportCompletion(EnumToString(tf), tfProcessedCount[t]);
            tfLastWrittenCandleTime[t] = newest;
            tfInitialDone[t]           = true;
            SaveStateToGlobals();
            Print(EnumToString(tf), " export complete — candle: ", TimeToString(newest),
                  " (", tfProcessedCount[t], "/", avail, " symbols)");
         }

         tfInitialDone[t]    = true;
         tfProcessedCount[t] = 0;
      }
   } // end TF loop
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   SaveStateToGlobals();
   Print("MarketDataExporter v6.6 stopped (reason=", reason, ") — state saved");
}

//+------------------------------------------------------------------+
void ProcessLastNCandles(string symbol, ENUM_TIMEFRAMES tf)
{
   datetime lcs = iTime(symbol, tf, 1);
   if(lcs == 0) return;

   if(TimeCurrent() < lcs + PeriodSeconds(tf) + WaitSecondsAfterCandleClose)
      return;

   int maxP = MathMax(MathMax(BB_Period,RSI_Period),
              MathMax(ATR_Period,MathMax(SMA_Long,Volume_SMA_Period)));

   // ✅ FIX: DO NOT include keepCandles in lookback
   int lookback = maxP + Touch_Lookback + Resistance_Lookback + 50;

   int requiredBars = lookback + keepCandles + 10;

   // ✅ FORCE history availability
   if(!EnsureHistoryLoaded(symbol, tf, requiredBars))
      return;

   MqlRates rates[];
   int bars = CopyRates(symbol, tf, 0, requiredBars, rates);

   if(bars < requiredBars)
   {
      Print("Still insufficient: ", symbol,
            " got=", bars, " need=", requiredBars);
      return;
   }

   // ✅ find target candle safely
   // CopyRates (non-series): rates[0]=oldest, rates[bars-1]=newest.
   // Search BACKWARDS to find the most recent bar whose time <= lcs.
   // Searching forward always matches rates[0] (oldest), giving tgt=0
   // and done=1 in the export loop — that was the "Only 1/350" bug.
   int tgt = -1;
   for(int i = bars-1; i >= 0; i--)
   {
      if(rates[i].time <= lcs)
      {
         tgt = i;
         break;
      }
   }
   if(tgt == -1) return;

   double bbU[],bbM[],bbL[],rsi[],volSMA[],atr[],smaS[],smaL2[];
   int touchUp[]; double rHigh[], rLow[];

   ArrayResize(bbU,bars);ArrayResize(bbM,bars);ArrayResize(bbL,bars);
   ArrayResize(rsi,bars);ArrayResize(volSMA,bars);ArrayResize(atr,bars);
   ArrayResize(smaS,bars);ArrayResize(smaL2,bars);
   ArrayResize(touchUp,bars);ArrayResize(rHigh,bars);ArrayResize(rLow,bars);

   double cl[]; ArrayResize(cl,bars);
   for(int i=0;i<bars;i++) cl[i]=rates[i].close;

   // === INDICATORS (UNCHANGED) ===
   for(int i=0;i<bars;i++)
   {
      if(i+1<BB_Period){bbM[i]=bbU[i]=bbL[i]=0;continue;}
      double s=0; for(int j=i-BB_Period+1;j<=i;j++) s+=cl[j];
      double ma=s/BB_Period;
      double v=0; for(int j=i-BB_Period+1;j<=i;j++) v+=MathPow(cl[j]-ma,2);
      double sd=MathSqrt(v/BB_Period);
      bbM[i]=ma; bbU[i]=ma+BB_Deviation*sd; bbL[i]=ma-BB_Deviation*sd;
   }

   for(int i=0;i<bars;i++) rsi[i]=0;
   double gS=0,lS=0;
   for(int i=1;i<=RSI_Period;i++){double c=cl[i]-cl[i-1];if(c>0)gS+=c;else lS-=c;}
   double aG=gS/RSI_Period,aL=lS/RSI_Period;
   rsi[RSI_Period]=(aL==0)?100:100-(100/(1+aG/aL));
   for(int i=RSI_Period+1;i<bars;i++)
   {
      double c=cl[i]-cl[i-1],g=(c>0)?c:0,l=(c<0)?-c:0;
      aG=(aG*(RSI_Period-1)+g)/RSI_Period;
      aL=(aL*(RSI_Period-1)+l)/RSI_Period;
      rsi[i]=(aL==0)?100:100-(100/(1+aG/aL));
   }

   for(int i=0;i<bars;i++)
   {
      if(i+1<Volume_SMA_Period){volSMA[i]=(double)rates[i].tick_volume;continue;}
      double s=0; for(int j=i-Volume_SMA_Period+1;j<=i;j++) s+=(double)rates[j].tick_volume;
      volSMA[i]=s/(double)Volume_SMA_Period;
   }

   for(int i=0;i<bars;i++)
   {
      if(i==0){atr[i]=rates[i].high-rates[i].low;continue;}
      double tr=MathMax(rates[i].high-rates[i].low,
               MathMax(MathAbs(rates[i].high-rates[i-1].close),
                       MathAbs(rates[i].low-rates[i-1].close)));
      atr[i]=(i<ATR_Period)?(atr[i-1]*i+tr)/(i+1):(atr[i-1]*(ATR_Period-1)+tr)/ATR_Period;
   }

   for(int i=0;i<bars;i++)
   {
      if(i+1<SMA_Short){smaS[i]=cl[i];continue;}
      double s=0; for(int j=i-SMA_Short+1;j<=i;j++) s+=cl[j];
      smaS[i]=s/SMA_Short;
   }

   for(int i=0;i<bars;i++)
   {
      if(i+1<SMA_Long){smaL2[i]=cl[i];continue;}
      double s=0; for(int j=i-SMA_Long+1;j<=i;j++) s+=cl[j];
      smaL2[i]=s/SMA_Long;
   }

   for(int i=0;i<bars;i++)
   {
      touchUp[i]=0;
      if(i>=Touch_Lookback)
      {
         int tc=0;
         for(int j=i-Touch_Lookback+1;j<=i;j++)
            if(rates[j].high>=bbU[j]) tc++;
         touchUp[i]=tc;
      }
   }

   for(int i=0;i<bars;i++)
   {
      int f=(i<Resistance_Lookback)?0:i-Resistance_Lookback+1;
      double mx=rates[f].high;
      for(int j=f;j<=i;j++) if(rates[j].high>mx) mx=rates[j].high;
      rHigh[i]=mx;
   }

   for(int i=0;i<bars;i++)
   {
      int f=(i<Resistance_Lookback)?0:i-Resistance_Lookback+1;
      double mn=rates[f].low;
      for(int j=f;j<=i;j++) if(rates[j].low<mn) mn=rates[j].low;
      rLow[i]=mn;
   }

   CandleData buf[]; ArrayResize(buf,0);
   int done=0;

   // ✅ STRICT 350 candles — fill OHLCV + all indicator fields
   for(int i=tgt; i>=0 && done<keepCandles; i--)
   {
      int ns=ArraySize(buf)+1; ArrayResize(buf,ns); int x=ns-1;

      // ── OHLCV ────────────────────────────────────────────────────────────
      buf[x].timestamp = rates[i].time;
      buf[x].symbol    = symbol;
      buf[x].open      = rates[i].open;
      buf[x].high      = rates[i].high;
      buf[x].low       = rates[i].low;
      buf[x].close     = rates[i].close;
      buf[x].volume    = rates[i].tick_volume;

      // ── Bollinger Bands ───────────────────────────────────────────────────
      buf[x].lower_band  = bbL[i];
      buf[x].middle_band = bbM[i];
      buf[x].upper_band  = bbU[i];

      double bbRange = bbU[i] - bbL[i];
      // BB position: 0=at lower band, 0.5=at midline, 1=at upper band
      buf[x].bb_position  = (bbRange > 0) ? (rates[i].close - bbL[i]) / bbRange : 0.5;
      // BB width pct: width relative to midline (volatility measure)
      buf[x].bb_width_pct = (bbM[i]   > 0) ? (bbRange / bbM[i]) * 100.0        : 0.0;

      // ── RSI ───────────────────────────────────────────────────────────────
      buf[x].rsi_value = rsi[i];

      // ── Volume ratio: current volume vs SMA ───────────────────────────────
      buf[x].volume_ratio = (volSMA[i] > 0)
                            ? (double)rates[i].tick_volume / volSMA[i]
                            : 1.0;

      // ── ATR pct: ATR normalised to close ──────────────────────────────────
      buf[x].atr_pct = (rates[i].close > 0) ? atr[i] / rates[i].close * 100.0 : 0.0;

      // ── Candle structure ──────────────────────────────────────────────────
      double candleRange = rates[i].high - rates[i].low;
      double body        = MathAbs(rates[i].close - rates[i].open);
      double upperWick   = rates[i].high - MathMax(rates[i].open, rates[i].close);

      buf[x].candle_body_pct = (candleRange > 0) ? body        / candleRange : 0.0;
      // Short-side candle rejection: upper wick relative to body
      buf[x].candle_rejection = (body > 0) ? upperWick / body : 0.0;

      // ── Trend strength: SMA50 / SMA200 - 1 ───────────────────────────────
      buf[x].trend_strength = (smaL2[i] > 0) ? (smaS[i] / smaL2[i]) - 1.0 : 0.0;

      // ── Previous-candle features ──────────────────────────────────────────
      if(i > 0)
      {
         double pRange = rates[i-1].high - rates[i-1].low;
         double pBody  = MathAbs(rates[i-1].close - rates[i-1].open);
         buf[x].prev_candle_body_pct = (pRange > 0) ? pBody / pRange : 0.0;
         buf[x].prev_volume_ratio    = (volSMA[i-1] > 0)
                                       ? (double)rates[i-1].tick_volume / volSMA[i-1]
                                       : 1.0;
         buf[x].gap_from_prev_close  = rates[i].open - rates[i-1].close;
         buf[x].prev_was_rally       = (rates[i-1].close > rates[i-1].open) ? 1 : 0;
         buf[x].prev_was_selloff     = (rates[i-1].close < rates[i-1].open) ? 1 : 0;
      }
      else
      {
         buf[x].prev_candle_body_pct = 0.0;
         buf[x].prev_volume_ratio    = 1.0;
         buf[x].gap_from_prev_close  = 0.0;
         buf[x].prev_was_rally       = 0;
         buf[x].prev_was_selloff     = 0;
      }

      // ── Price momentum: 4-bar close-over-close % ─────────────────────────
      buf[x].price_momentum = (i >= 4 && rates[i-4].close > 0)
                              ? (rates[i].close - rates[i-4].close) / rates[i-4].close * 100.0
                              : 0.0;

      // ── Upper-BB touch count (last Touch_Lookback bars) ───────────────────
      buf[x].previous_touches = touchUp[i];

      // ── BB touch strength (short side): high / upper_band ────────────────
      buf[x].bb_touch_strength = (bbU[i] > 0) ? rates[i].high / bbU[i] : 0.0;

      // ── RSI divergence (short side, 5-bar): price↑ but RSI↓ = 1 ─────────
      if(i >= 5 && rsi[i] > 0 && rsi[i-5] > 0)
         buf[x].rsi_divergence = (rates[i].close > rates[i-5].close && rsi[i] < rsi[i-5]) ? 1 : 0;
      else
         buf[x].rsi_divergence = 0;

      // ── Time since last upper-BB touch ────────────────────────────────────
      {
         int tsl = 0;
         for(int k = i-1; k >= 0 && tsl < Touch_Lookback; k--)
         {
            if(rates[k].high >= bbU[k]) break;
            tsl++;
         }
         buf[x].time_since_last_touch = tsl;
      }

      // ── Resistance / Support distance % ──────────────────────────────────
      buf[x].resistance_distance_pct = (rates[i].close > 0)
                                       ? (rHigh[i] - rates[i].close) / rates[i].close * 100.0
                                       : 0.0;
      buf[x].support_distance_pct    = (rates[i].close > 0)
                                       ? (rates[i].close - rLow[i])  / rates[i].close * 100.0
                                       : 0.0;

      // ── UBB event features ────────────────────────────────────────────────
      buf[x].close_above_ubb = (rates[i].close > bbU[i]) ? 1 : 0;
      buf[x].high_touch_ubb  = (rates[i].high >= bbU[i]) ? 1 : 0;
      buf[x].failed_break_ubb = (rates[i].high >= bbU[i] && rates[i].close < bbU[i]) ? 1 : 0;
      buf[x].no_upper_wick_bear_reject = (candleRange > 0
                                          && upperWick / candleRange < 0.15
                                          && rates[i].close >= rates[i].open) ? 1 : 0;

      // bb_event_type: 0=normal, 1=touch only, 2=close above UBB, 3=failed break
      if(buf[x].close_above_ubb)       buf[x].bb_event_type = 2;
      else if(buf[x].failed_break_ubb) buf[x].bb_event_type = 3;
      else if(buf[x].high_touch_ubb)   buf[x].bb_event_type = 1;
      else                              buf[x].bb_event_type = 0;

      // UBB distance: signed distance from close to upper band, in ATR units
      buf[x].ubb_distance_close = (atr[i] > 0) ? (rates[i].close - bbU[i]) / atr[i] : 0.0;

      // ── Session ───────────────────────────────────────────────────────────
      {
         MqlDateTime dt;
         TimeToStruct(rates[i].time, dt);
         int hour      = dt.hour;
         bool inLondon = (hour >= London_Start && hour < London_End);
         bool inNY     = (hour >= NY_Start     && hour < NY_End);
         if(inLondon && inNY)  buf[x].session = 3;   // London/NY overlap
         else if(inLondon)     buf[x].session = 1;   // London only
         else if(inNY)         buf[x].session = 2;   // NY only
         else                  buf[x].session = 0;   // Off-session
      }

      done++;
   }

   // 🚨 HARD REQUIREMENT
   if(done < keepCandles)
   {
      Print("ERROR: Only ", done, "/", keepCandles,
            " candles for ", symbol, " ", EnumToString(tf));
      return;
   }

   UpdateCacheWithLatestCandles(symbol, tf, buf);
}

//+------------------------------------------------------------------+
void WriteCacheToCSV(ENUM_TIMEFRAMES tf)
{
   CandleData candles[]; int count=GetAllCandlesForTimeframe(tf,candles);
   if(count==0) return;

   string fn=GetFilenameForTimeframe(tf);
   ushort sep=StringGetCharacter(",",0);
   int h=FileOpen(fn,FILE_WRITE|FILE_CSV|FILE_ANSI,sep);
   if(h==INVALID_HANDLE) return;

   FileWrite(h,
      "timestamp","pair",
      "open","high","low","close","volume",
      "lower_band","middle_band","upper_band",
      "bb_touch_strength","bb_position","bb_width_pct",
      "rsi_value","rsi_divergence",
      "volume_ratio","candle_rejection","candle_body_pct","atr_pct",
      "trend_strength","prev_candle_body_pct","prev_volume_ratio",
      "gap_from_prev_close","price_momentum",
      "prev_was_rally","prev_was_selloff",
      "previous_touches","time_since_last_touch",
      "resistance_distance_pct","support_distance_pct",
      "close_above_ubb","high_touch_ubb",
      "no_upper_wick_bear_reject","failed_break_ubb",
      "bb_event_type","ubb_distance_close",
      "session"
   );

   for(int i=0;i<count;i++)
   {
      CandleData d=candles[i];
      FileWrite(h,
         TimeToString(d.timestamp,TIME_DATE|TIME_SECONDS), d.symbol,
         DoubleToString(d.open,6),  DoubleToString(d.high,6),
         DoubleToString(d.low,6),   DoubleToString(d.close,6),
         IntegerToString(d.volume),
         DoubleToString(d.lower_band,6),  DoubleToString(d.middle_band,6), DoubleToString(d.upper_band,6),
         DoubleToString(d.bb_touch_strength,6), DoubleToString(d.bb_position,6), DoubleToString(d.bb_width_pct,6),
         DoubleToString(d.rsi_value,2),   IntegerToString(d.rsi_divergence),
         DoubleToString(d.volume_ratio,6), DoubleToString(d.candle_rejection,6),
         DoubleToString(d.candle_body_pct,6), DoubleToString(d.atr_pct,6),
         DoubleToString(d.trend_strength,6),
         DoubleToString(d.prev_candle_body_pct,6), DoubleToString(d.prev_volume_ratio,6),
         DoubleToString(d.gap_from_prev_close,6), DoubleToString(d.price_momentum,6),
         IntegerToString(d.prev_was_rally),    IntegerToString(d.prev_was_selloff),
         IntegerToString(d.previous_touches),  IntegerToString(d.time_since_last_touch),
         DoubleToString(d.resistance_distance_pct,6), DoubleToString(d.support_distance_pct,6),
         IntegerToString(d.close_above_ubb),   IntegerToString(d.high_touch_ubb),
         IntegerToString(d.no_upper_wick_bear_reject), IntegerToString(d.failed_break_ubb),
         IntegerToString(d.bb_event_type),     DoubleToString(d.ubb_distance_close,6),
         IntegerToString(d.session)
      );
   }
   FileClose(h);
   Print("CSV written: ",fn," — ",count," candles");
}

//+------------------------------------------------------------------+
string GVKey(ENUM_TIMEFRAMES tf, string suffix)
{
   return "MDE_" + IntegerToString((int)tf) + "_" + suffix;
}

void SaveStateToGlobals()
{
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
   {
      ENUM_TIMEFRAMES tf = selectedTimeframes[i];
      GlobalVariableSet(GVKey(tf,"lwt"),  (double)tfLastWrittenCandleTime[i]);
      GlobalVariableSet(GVKey(tf,"init"), (double)(tfInitialDone[i] ? 1 : 0));
   }
}

void LoadStateFromGlobals()
{
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
   {
      ENUM_TIMEFRAMES tf = selectedTimeframes[i];
      string kLwt  = GVKey(tf,"lwt");
      string kInit = GVKey(tf,"init");

      if(GlobalVariableCheck(kLwt))
         tfLastWrittenCandleTime[i] = (datetime)GlobalVariableGet(kLwt);
      else
         tfLastWrittenCandleTime[i] = 0;

      if(GlobalVariableCheck(kInit))
         tfInitialDone[i] = (GlobalVariableGet(kInit) > 0);
      else
         tfInitialDone[i] = false;
   }
}

void ClearStateGlobals()
{
   for(int i = 0; i < ArraySize(selectedTimeframes); i++)
   {
      ENUM_TIMEFRAMES tf = selectedTimeframes[i];
      GlobalVariableDel(GVKey(tf,"lwt"));
      GlobalVariableDel(GVKey(tf,"init"));
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   Print("MarketDataExporter v6.6");
   keepCandles = KeepLastNCandles;
   if(keepCandles < 1 || keepCandles > 5000) { keepCandles = 350; Print("Invalid KeepLastNCandles, using 350"); }

   PrepareSymbolList();
   PrepareTimeframeList();

   // FIX: initialise all three parallel key arrays together
   ArrayResize(symbolTimeframeKeys,  0);
   ArrayResize(symbolLastCandleTime, 0);
   ArrayResize(symbolInitProcessed,  0);

   int n = ArraySize(selectedTimeframes);
   ArrayResize(tfLastWrittenCandleTime, n);
   ArrayResize(tfProcessedCount,        n);
   ArrayResize(tfInitialDone,           n);

   for(int i = 0; i < n; i++)
      tfProcessedCount[i] = 0;

   LoadStateFromGlobals();

   Print("State restored:");
   for(int i = 0; i < n; i++)
      Print("  ", EnumToString(selectedTimeframes[i]),
            " initialDone=", tfInitialDone[i],
            "  lastWritten=", TimeToString(tfLastWrittenCandleTime[i]));

   EventSetTimer(1);
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+