//+------------------------------------------------------------------+
//|                                                  ML_Backtest.mq5 |
//|                        Copyright 2024, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, ML Backtest EA"
#property link      "https://www.mql5.com"
#property version   "1.00"

//--- Input parameters
input string   CSVFileName = "ml_predictions.csv";  // CSV file name
input int      SignalColumn = 1;                    // Column index for signals (0-based)
input int      TimestampColumn = 0;                 // Column index for timestamps
input string   TimestampFormat = "yyyy.MM.dd HH:mm:ss"; // Timestamp format
input double   LotSize = 0.1;                       // Fixed lot size
input int      Slippage = 3;                        // Slippage in points
input int      MagicNumber = 2024;                  // Magic number for trades
input string   CommentText = "ML Model Trade";       // Trade comment
input bool     UseStopLoss = true;                  // Use stop loss
input double   StopLossPoints = 100;                // Stop loss in points
input bool     UseTakeProfit = true;                // Use take profit
input double   TakeProfitPoints = 200;              // Take profit in points
input bool     CloseOnOppositeSignal = true;        // Close on opposite signal
input bool     VerboseLogging = true;               // Enable verbose logging

//--- Global variables
string csvArray[][100];     // 2D array for CSV data (max 100 columns)
int    totalRows;           // Total rows in CSV
int    currentRow = 0;      // Current row being processed
datetime lastProcessedTime = 0;  // Last processed timestamp
bool   csvLoaded = false;   // CSV loaded flag
int    fileHandle;          // File handle
int    maxColumns = 0;      // Maximum columns found
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Initialize CSV data
   if(!LoadCSVData())
   {
      Print("Failed to load CSV file: ", CSVFileName);
      return(INIT_FAILED);
   }
   
   Print("CSV file loaded successfully. Total rows: ", totalRows);
   Print("Column ", SignalColumn, " will be used for trade signals.");
   Print("Column ", TimestampColumn, " will be used for timestamps.");
   
   if(VerboseLogging)
   {
      // Display first few rows for verification
      Print("Sample data (first 5 rows):");
      for(int i=0; i<MathMin(5, totalRows); i++)
      {
         string rowData = "Row " + IntegerToString(i) + ": Time=" + csvArray[i][TimestampColumn] + ", Signal=" + csvArray[i][SignalColumn];
         Print(rowData);
      }
   }
   
   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   //--- Clean up
   if(fileHandle != INVALID_HANDLE)
      FileClose(fileHandle);
   
   ArrayFree(csvArray);
   Print("EA deinitialized");
}
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Only process at the beginning of a new bar
   if(!IsNewBar())
      return;
   
   //--- Check if we have more data to process
   if(currentRow >= totalRows)
   {
      if(VerboseLogging)
         Print("All CSV data processed. Total rows: ", totalRows);
      return;
   }
   
   //--- Get current time
   datetime currentTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   
   //--- Process signals for the current time
   ProcessSignals(currentTime);
}
//+------------------------------------------------------------------+
//| Load CSV data into array                                         |
//+------------------------------------------------------------------+
bool LoadCSVData()
{
   ResetLastError();
   
   //--- Open CSV file
   fileHandle = FileOpen(CSVFileName, FILE_READ|FILE_ANSI|FILE_CSV, ',');
   
   if(fileHandle == INVALID_HANDLE)
   {
      int error = GetLastError();
      Print("Error opening file: ", CSVFileName, " Error: ", error);
      return false;
   }
   
   //--- First pass: count rows and find max columns
   int rowCount = 0;
   maxColumns = 0;
   
   // Create a temporary list to store rows
   string tempRows[];
   string tempColumns[][];
   
   while(!FileIsEnding(fileHandle))
   {
      string line = FileReadString(fileHandle);
      
      if(line == "")
         continue;
      
      // Split line by comma
      string values[];
      int splitCount = StringSplit(line, ',', values);
      
      if(splitCount > 0)
      {
         // Update max columns
         if(splitCount > maxColumns)
            maxColumns = splitCount;
         
         // Resize tempColumns to hold this row
         ArrayResize(tempColumns, rowCount + 1);
         ArrayResize(tempColumns[rowCount], splitCount);
         
         // Store values
         for(int j = 0; j < splitCount; j++)
         {
            tempColumns[rowCount][j] = values[j];
         }
         
         rowCount++;
      }
   }
   
   //--- Reset file pointer and close
   FileClose(fileHandle);
   
   //--- Now resize the main array
   if(rowCount > 0)
   {
      // Resize the first dimension (rows)
      ArrayResize(csvArray, rowCount);
      
      // Copy data from temp array
      for(int i = 0; i < rowCount; i++)
      {
         // Resize the second dimension for this row
         ArrayResize(csvArray[i], maxColumns);
         
         // Copy values
         for(int j = 0; j < ArraySize(tempColumns[i]); j++)
         {
            csvArray[i][j] = tempColumns[i][j];
         }
         
         // Fill remaining columns with empty strings if needed
         for(int j = ArraySize(tempColumns[i]); j < maxColumns; j++)
         {
            csvArray[i][j] = "";
         }
      }
      
      totalRows = rowCount;
      csvLoaded = true;
      
      Print("CSV loaded: ", totalRows, " rows, ", maxColumns, " max columns");
      return true;
   }
   
   return false;
}
//+------------------------------------------------------------------+
//| Process signals for given time                                   |
//+------------------------------------------------------------------+
void ProcessSignals(datetime currentTime)
{
   //--- Check multiple rows in case of multiple signals at same time
   while(currentRow < totalRows)
   {
      string csvTimeStr = csvArray[currentRow][TimestampColumn];
      
      //--- Try to parse the CSV time
      datetime csvTime = StringToTime(csvTimeStr);
      
      if(csvTime == 0)
      {
         // Try alternative parsing if default fails
         csvTime = ParseCustomTime(csvTimeStr);
      }
      
      //--- If CSV time is in the future, stop processing
      if(csvTime > currentTime)
         break;
      
      //--- Process signal if time matches
      if(csvTime <= currentTime && csvTime > lastProcessedTime)
      {
         string signalStr = csvArray[currentRow][SignalColumn];
         int signal = (int)StringToInteger(signalStr);
         
         Print("Processing signal at ", TimeToString(csvTime), 
               ", Signal: ", signal, 
               ", Row: ", currentRow);
         
         //--- Execute trade based on signal
         ExecuteTrade(signal, csvTime);
         
         lastProcessedTime = csvTime;
      }
      
      currentRow++;
   }
}
//+------------------------------------------------------------------+
//| Parse custom time format                                         |
//+------------------------------------------------------------------+
datetime ParseCustomTime(string timeStr)
{
   //--- Remove any quotes or extra characters
   StringReplace(timeStr, "\"", "");
   StringReplace(timeStr, "'", "");
   StringTrimLeft(timeStr);
   StringTrimRight(timeStr);
   
   //--- Try to parse as datetime
   datetime result = StringToTime(timeStr);
   
   if(result == 0)
   {
      // Try common alternative formats
      string formats[] = {
         "%Y.%m.%d %H:%M:%S",
         "%Y-%m-%d %H:%M:%S",
         "%d.%m.%Y %H:%M:%S",
         "%m/%d/%Y %H:%M:%S",
         "%Y%m%d %H:%M:%S"
      };
      
      for(int i = 0; i < ArraySize(formats); i++)
      {
         result = StringToTimeEx(timeStr, formats[i]);
         if(result != 0)
            break;
      }
   }
   
   return result;
}
//+------------------------------------------------------------------+
//| Enhanced StringToTime function                                   |
//+------------------------------------------------------------------+
datetime StringToTimeEx(string timeStr, string format)
{
   string formatPatterns[] = {
      "%Y.%m.%d %H:%M:%S",  // yyyy.MM.dd HH:mm:ss
      "%Y-%m-%d %H:%M:%S",  // yyyy-MM-dd HH:mm:ss
      "%d.%m.%Y %H:%M:%S",  // dd.MM.yyyy HH:mm:ss
      "%m/%d/%Y %H:%M:%S",  // MM/dd/yyyy HH:mm:ss
      "%Y%m%d %H:%M:%S"     // yyyyMMdd HH:mm:ss
   };
   
   string formatReplacements[] = {
      "yyyy.MM.dd HH:mm:ss",
      "yyyy-MM-dd HH:mm:ss",
      "dd.MM.yyyy HH:mm:ss",
      "MM/dd/yyyy HH:mm:ss",
      "yyyyMMdd HH:mm:ss"
   };
   
   // Find matching format
   for(int i = 0; i < ArraySize(formatPatterns); i++)
   {
      if(format == formatReplacements[i])
      {
         // Parse using standard MQL function
         return StringToTime(timeStr);
      }
   }
   
   return 0;
}
//+------------------------------------------------------------------+
//| Execute trade based on signal                                    |
//+------------------------------------------------------------------+
void ExecuteTrade(int signal, datetime tradeTime)
{
   //--- Signal interpretation:
   // 1 = Buy/Long
   // 0 = No signal/Neutral
   // -1 = Sell/Short or Close (if CloseOnOppositeSignal is true)
   
   if(signal == 1) // Buy signal
   {
      if(CloseOnOppositeSignal)
      {
         CloseAllPositions(POSITION_TYPE_SELL);
      }
      
      // Check if we already have a buy position
      if(!HasOpenPosition(POSITION_TYPE_BUY))
      {
         OpenBuyPosition(tradeTime);
      }
   }
   else if(signal == -1) // Sell signal or close signal
   {
      if(CloseOnOppositeSignal)
      {
         CloseAllPositions(POSITION_TYPE_BUY);
      }
      else
      {
         // Close all positions on sell signal
         CloseAllPositions();
      }
   }
   // Signal = 0 does nothing
}
//+------------------------------------------------------------------+
//| Open buy position                                                |
//+------------------------------------------------------------------+
bool OpenBuyPosition(datetime tradeTime)
{
   double sl = 0, tp = 0;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   //--- Calculate stop loss and take profit
   if(UseStopLoss && StopLossPoints > 0)
      sl = ask - StopLossPoints * point;
   
   if(UseTakeProfit && TakeProfitPoints > 0)
      tp = ask + TakeProfitPoints * point;
   
   //--- Prepare trade request
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = NormalizeDouble(LotSize, 2);
   request.type = ORDER_TYPE_BUY;
   request.price = NormalizeDouble(ask, _Digits);
   request.deviation = Slippage;
   request.magic = MagicNumber;
   request.comment = CommentText + " Time: " + TimeToString(tradeTime);
   request.type_filling = ORDER_FILLING_FOK;
   
   // Set SL and TP if specified
   if(sl > 0)
      request.sl = NormalizeDouble(sl, _Digits);
   
   if(tp > 0)
      request.tp = NormalizeDouble(tp, _Digits);
   
   //--- Send order
   bool success = OrderSend(request, result);
   
   if(success && result.retcode == TRADE_RETCODE_DONE)
   {
      Print("Buy order opened. Ticket: ", result.order, 
            ", Price: ", result.price,
            ", Time: ", TimeToString(tradeTime));
   }
   else
   {
      Print("Failed to open buy order. Error: ", result.retcode,
            ", Time: ", TimeToString(tradeTime));
   }
   
   return success;
}
//+------------------------------------------------------------------+
//| Close all positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions(int type = -1) // -1 means all types
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(type == -1 || PositionGetInteger(POSITION_TYPE) == type)
         {
            ClosePosition(ticket);
         }
      }
   }
}
//+------------------------------------------------------------------+
//| Close individual position                                        |
//+------------------------------------------------------------------+
bool ClosePosition(ulong ticket)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   string symbol = PositionGetString(POSITION_SYMBOL);
   double volume = PositionGetDouble(POSITION_VOLUME);
   ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   
   request.action = TRADE_ACTION_DEAL;
   request.position = ticket;
   request.symbol = symbol;
   request.volume = NormalizeDouble(volume, 2);
   request.deviation = Slippage;
   request.magic = MagicNumber;
   request.comment = "Closed by ML EA";
   
   if(posType == POSITION_TYPE_BUY)
   {
      request.type = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(symbol, SYMBOL_BID);
   }
   else
   {
      request.type = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   }
   
   request.type_filling = ORDER_FILLING_FOK;
   
   bool success = OrderSend(request, result);
   
   if(success && result.retcode == TRADE_RETCODE_DONE)
   {
      Print("Position closed. Ticket: ", ticket);
   }
   else
   {
      Print("Failed to close position. Ticket: ", ticket, ", Error: ", result.retcode);
   }
   
   return success;
}
//+------------------------------------------------------------------+
//| Check if there's an open position of specified type             |
//+------------------------------------------------------------------+
bool HasOpenPosition(ENUM_POSITION_TYPE type)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetInteger(POSITION_TYPE) == type &&
            PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         {
            return true;
         }
      }
   }
   return false;
}
//+------------------------------------------------------------------+
//| Check if new bar has formed                                      |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   
   if(lastBarTime != currentBarTime)
   {
      lastBarTime = currentBarTime;
      return true;
   }
   return false;
}
//+------------------------------------------------------------------+