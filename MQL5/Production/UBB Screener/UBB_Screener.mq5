//+------------------------------------------------------------------+
//|                                            UBB_Screener.mq5     |
//|                                                         Solara  |
//+------------------------------------------------------------------+
#property copyright "Solara"
#property link      ""
#property version   "1.06"
#property description "UBB Rejection Screener — 28 pairs × multiple timeframes"

//--- Inputs
input group "── Timeframes ────────────────────────────"
input bool InpUseM5  = false; // Monitor M5
input bool InpUseM15 = false; // Monitor M15
input bool InpUseH1  = true;  // Monitor H1
input bool InpUseH4  = true;  // Monitor H4
input bool InpUseD1  = false; // Monitor D1
input bool InpUseW1  = false; // Monitor W1

input group "── Bollinger Bands ───────────────────────"
input int    InpBBPeriod    = 20;   // Period
input double InpBBDeviation = 2.0;  // Deviation
input double InpBBThreshold = 0.85; // Near-UBB threshold (0.0–1.0)

input group "── Label ─────────────────────────────────"
input color InpLabelColor = clrDodgerBlue; // UBB label colour
input int   InpLabelSize  = 18;            // UBB label font size

//--- Constants
#define UBB_LABEL_NAME "UBB_Tag"

//--- Symbol list (28 pairs)
string g_symbols[] = {
   "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD",
   "EURGBP","EURJPY","EURCHF","EURAUD","EURCAD","EURNZD",
   "GBPJPY","GBPCHF","GBPAUD","GBPCAD","GBPNZD",
   "AUDJPY","AUDCHF","AUDCAD","AUDNZD",
   "NZDJPY","NZDCHF","NZDCAD",
   "CADJPY","CADCHF","CHFJPY"
};

//--- Screening slots — one per (symbol × timeframe)
struct SymTFSlot
{
   string           sym;
   ENUM_TIMEFRAMES  tf;
   int              bbHandle;
   datetime         lastBar;
};

SymTFSlot g_slots[];
int       g_slotCount = 0;

//--- Chart queue — setups detected this tick wait here to be opened one per tick
struct PendingChart
{
   string          sym;
   ENUM_TIMEFRAMES tf;
};

PendingChart g_queue[];
int          g_qHead = 0; // index of next item to process

//+------------------------------------------------------------------+
//| Helper: convert ENUM_TIMEFRAMES to a short readable string       |
//+------------------------------------------------------------------+
string TFToString(const ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M2:  return "M2";
      case PERIOD_M3:  return "M3";
      case PERIOD_M4:  return "M4";
      case PERIOD_M5:  return "M5";
      case PERIOD_M6:  return "M6";
      case PERIOD_M10: return "M10";
      case PERIOD_M12: return "M12";
      case PERIOD_M15: return "M15";
      case PERIOD_M20: return "M20";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H2:  return "H2";
      case PERIOD_H3:  return "H3";
      case PERIOD_H4:  return "H4";
      case PERIOD_H6:  return "H6";
      case PERIOD_H8:  return "H8";
      case PERIOD_H12: return "H12";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      case PERIOD_MN1: return "MN1";
      default:         return EnumToString(tf);
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   ENUM_TIMEFRAMES activeTFs[];
   if(InpUseM5)  { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_M5;  }
   if(InpUseM15) { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_M15; }
   if(InpUseH1)  { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_H1;  }
   if(InpUseH4)  { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_H4;  }
   if(InpUseD1)  { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_D1;  }
   if(InpUseW1)  { int n=ArraySize(activeTFs); ArrayResize(activeTFs,n+1); activeTFs[n]=PERIOD_W1;  }

   int tfCount = ArraySize(activeTFs);
   if(tfCount == 0) { Print("UBB Screener: no timeframe selected."); return INIT_FAILED; }

   int symCount = ArraySize(g_symbols);
   g_slotCount  = symCount * tfCount;
   ArrayResize(g_slots, g_slotCount);

   int idx = 0;
   for(int s = 0; s < symCount; s++)
   {
      SymbolSelect(g_symbols[s], true);
      for(int t = 0; t < tfCount; t++)
      {
         g_slots[idx].sym      = g_symbols[s];
         g_slots[idx].tf       = activeTFs[t];
         g_slots[idx].lastBar  = 0;
         g_slots[idx].bbHandle = iBands(g_symbols[s], activeTFs[t],
                                         InpBBPeriod, 0, InpBBDeviation, PRICE_CLOSE);
         if(g_slots[idx].bbHandle == INVALID_HANDLE)
         {
            PrintFormat("UBB Screener: failed BB handle for %s %s",
                        g_symbols[s], EnumToString(activeTFs[t]));
            return INIT_FAILED;
         }
         idx++;
      }
   }

   ArrayResize(g_queue, 0);
   g_qHead = 0;

   EventSetTimer(1);
   PrintFormat("UBB Screener ready — %d symbols × %d TF(s) = %d slots",
               symCount, tfCount, g_slotCount);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   for(int i = 0; i < g_slotCount; i++)
      if(g_slots[i].bbHandle != INVALID_HANDLE)
         IndicatorRelease(g_slots[i].bbHandle);
}

void OnTick() {}

//+------------------------------------------------------------------+
//| Every second:                                                    |
//|   1. Open ONE pending chart from the queue (if any)              |
//|   2. Scan all slots for new candles → queue any new setups       |
//+------------------------------------------------------------------+
void OnTimer()
{
   // ── Step 1: pop one item from the queue and open its chart ─────
   if(g_qHead < ArraySize(g_queue))
   {
      string          sym = g_queue[g_qHead].sym;
      ENUM_TIMEFRAMES tf  = g_queue[g_qHead].tf;
      g_qHead++;

      long cid = FindChart(sym, tf);
      if(cid < 0)
      {
         cid = ChartOpen(sym, tf);
         if(cid > 0) Sleep(350); // let the new chart finish rendering
      }
      if(cid > 0)
         AddUBBLabel(cid, tf); // <-- pass the timeframe through

      // Reset queue when fully consumed
      if(g_qHead >= ArraySize(g_queue))
      {
         ArrayResize(g_queue, 0);
         g_qHead = 0;
      }
   }

   // ── Step 2: scan for new candles and enqueue qualifying setups ──
   for(int i = 0; i < g_slotCount; i++)
   {
      string          sym = g_slots[i].sym;
      ENUM_TIMEFRAMES tf  = g_slots[i].tf;

      datetime t0 = iTime(sym, tf, 0);
      if(t0 == 0)                  continue;
      if(t0 == g_slots[i].lastBar) continue;
      g_slots[i].lastBar = t0;

      if(!CheckSetup(sym, tf, g_slots[i].bbHandle)) continue;

      PrintFormat("[UBB SETUP] %s  %s", sym, EnumToString(tf));

      // Add to queue — will be opened one per subsequent tick
      int n = ArraySize(g_queue);
      ArrayResize(g_queue, n + 1);
      g_queue[n].sym = sym;
      g_queue[n].tf  = tf;
   }
}

//+------------------------------------------------------------------+
long FindChart(const string sym, const ENUM_TIMEFRAMES tf)
{
   long id = ChartFirst();
   while(id >= 0)
   {
      if(ChartSymbol(id) == sym && ChartPeriod(id) == tf) return id;
      id = ChartNext(id);
   }
   return -1;
}

//+------------------------------------------------------------------+
bool CheckSetup(const string sym, const ENUM_TIMEFRAMES tf, const int bbHandle)
{
   // r[0] = forming  |  r[1] = candle-1  |  r[2] = candle-2
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(sym, tf, 0, 4, r) < 4) return false;

   double c2Open=r[2].open, c2Close=r[2].close;
   double c1Open=r[1].open, c1Close=r[1].close;

   if(c2Close <= c2Open)  return false; // C1: candle-2 green
   if(c1Close >= c1Open)  return false; // C3: candle-1 red

   double upper[], lower[];
   ArraySetAsSeries(upper, true);
   ArraySetAsSeries(lower, true);
   if(CopyBuffer(bbHandle, 1, 0, 4, upper) < 4) return false;
   if(CopyBuffer(bbHandle, 2, 0, 4, lower) < 4) return false;

   double bbUpper=upper[2], bbLower=lower[2], bbWidth=bbUpper-bbLower;
   if(bbWidth <= 0) return false;

   double bbPos = (c2Close - bbLower) / bbWidth;

   if(bbPos < InpBBThreshold) return false; // C2: above 85% of BB width
   if(c2Close >= bbUpper)     return false; // C4: below upper BB
   if(c1Close >= c2Close)     return false; // C5: candle-1 close < candle-2 close

   return true;
}

//+------------------------------------------------------------------+
//| Draw (or refresh) the "UBB - <TF>" label on the given chart      |
//+------------------------------------------------------------------+
void AddUBBLabel(const long chartId, const ENUM_TIMEFRAMES tf)
{
   ObjectDelete(chartId, UBB_LABEL_NAME);

   if(!ObjectCreate(chartId, UBB_LABEL_NAME, OBJ_LABEL, 0, 0, 0))
   {
      PrintFormat("AddUBBLabel: failed on chart %I64d  err=%d", chartId, GetLastError());
      return;
   }

   string labelText = "UBB - " + TFToString(tf); // e.g. "UBB - H4"

   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_CORNER,     CORNER_RIGHT_LOWER);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_ANCHOR,     ANCHOR_RIGHT_LOWER);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_XDISTANCE,  12);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_YDISTANCE,  12);
   ObjectSetString (chartId, UBB_LABEL_NAME, OBJPROP_TEXT,       labelText);
   ObjectSetString (chartId, UBB_LABEL_NAME, OBJPROP_FONT,       "Arial Bold");
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_FONTSIZE,   InpLabelSize);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_COLOR,      InpLabelColor);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_HIDDEN,     false);
   ObjectSetInteger(chartId, UBB_LABEL_NAME, OBJPROP_ZORDER,     100);

   ChartRedraw(chartId);
}
//+------------------------------------------------------------------+