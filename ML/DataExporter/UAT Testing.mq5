//+------------------------------------------------------------------+
//| CSV Timestamp Vertical Line Plotter with Strength Booleans       |
//+------------------------------------------------------------------+
#property strict
#property version "1.70"

input string CSV_FolderPath = "";               // e.g. "Signals" or "" for MQL5/Files root
input string CSV_FileName   = "gbpusd_buy_signals.csv"; // CSV file name
input string TimeColumnName = "timestamp";      // Column to read for datetime
input color  LineColor      = clrGreen;
input int    LineWidth      = 1;

// Filter which strengths to plot
input bool PlotStrong = true;
input bool PlotMedium = true;
input bool PlotWeak   = false;

//+------------------------------------------------------------------+
int OnInit()
{
   // ===== Resolve full path =====
   string full_path = CSV_FileName;
   if(CSV_FolderPath != "")
   {
      string folder = CSV_FolderPath;
      StringTrimLeft(folder);
      StringTrimRight(folder);
      full_path = folder + "/" + CSV_FileName;
   }

   Print("Trying to open CSV file: ", full_path);

   // ===== Check if file exists =====
   if(!FileIsExist(full_path))
   {
      Print("ERROR: File does not exist: ", full_path);
      return(INIT_SUCCEEDED);
   }

   // ===== Open CSV =====
   int handle = FileOpen(full_path, FILE_READ | FILE_CSV | FILE_ANSI);
   if(handle == INVALID_HANDLE)
   {
      Print("ERROR: Failed to open CSV file. Error code: ", GetLastError());
      return(INIT_SUCCEEDED);
   }

   Print("CSV file opened successfully.");

   // ===== Read header =====
   string header_line = FileReadString(handle);
   string headers[];
   int colCount = StringSplit(header_line, ',', headers);

   for(int i = 0; i < colCount; i++)
   {
      if(StringGetCharacter(headers[i],0)==65279)  // Remove BOM
         headers[i] = StringSubstr(headers[i],1);

      StringTrimLeft(headers[i]);
      StringTrimRight(headers[i]);

      Print("Header[", i, "]: '", headers[i], "'");
   }

   // ===== Find timestamp column =====
   int timeCol = -1;
   for(int i=0;i<colCount;i++)
   {
      string header_lc = headers[i];
      string timecol_lc = TimeColumnName;
      StringToLower(header_lc);
      StringToLower(timecol_lc);
      if(header_lc==timecol_lc)
      {
         timeCol = i;
         break;
      }
   }

   if(timeCol == -1)
   {
      Print("ERROR: Timestamp column not found: ", TimeColumnName);
      FileClose(handle);
      return(INIT_SUCCEEDED);
   }
   Print("Timestamp column found at index: ", timeCol);

   // ===== Find strength column =====
   int strengthCol = -1;
   for(int i=0;i<colCount;i++)
   {
      string header_lc = headers[i];
      StringToLower(header_lc);
      if(header_lc=="strength")
      {
         strengthCol = i;
         break;
      }
   }
   if(strengthCol==-1)
      Print("WARNING: Strength column not found. All lines will be plotted.");

   // ===== Read remaining rows =====
   int lineIndex = 0;
   while(!FileIsEnding(handle))
   {
      string row_line = FileReadString(handle);
      StringTrimLeft(row_line);
      StringTrimRight(row_line);
      if(row_line=="") continue;

      string row[];
      int rowCount = StringSplit(row_line, ',', row);
      if(timeCol >= rowCount)
      {
         Print("WARNING: Row too short, skipped: ", row_line);
         continue;
      }

      // --- Get timestamp ---
      string time_str = row[timeCol];
      datetime dt = StringToTime(time_str);
      if(dt <= 0)
      {
         Print("WARNING: Invalid datetime skipped: ", time_str);
         continue;
      }

      // --- Get strength ---
      bool plotLine = true; // default
      if(strengthCol != -1)
      {
         if(strengthCol >= rowCount)
         {
            Print("WARNING: Strength column missing in row, skipped: ", row_line);
            continue;
         }

         string strength_val = row[strengthCol];
         StringTrimLeft(strength_val);
         StringTrimRight(strength_val);
         StringToUpper(strength_val);

         plotLine = false; // default to skip

         if(strength_val=="STRONG" && PlotStrong) plotLine = true;
         if(strength_val=="MEDIUM" && PlotMedium) plotLine = true;
         if(strength_val=="WEAK" && PlotWeak) plotLine = true;
      }

      if(!plotLine) continue;

      // --- Plot vertical line ---
      string objName = "CSV_VLINE_" + IntegerToString(lineIndex);
      if(ObjectCreate(0, objName, OBJ_VLINE, 0, dt, 0))
      {
         ObjectSetInteger(0, objName, OBJPROP_COLOR, LineColor);
         ObjectSetInteger(0, objName, OBJPROP_WIDTH, LineWidth);
         ObjectSetInteger(0, objName, OBJPROP_STYLE, STYLE_SOLID);
      }

      lineIndex++;
   }

   FileClose(handle);
   Print("Finished plotting ", lineIndex, " vertical lines.");
   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
