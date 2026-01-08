//+------------------------------------------------------------------+
//| ExportVLineDates.mq5                                             |
//| MT5 - Export Vertical Line Dates                                 |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

void OnStart()
{
   string filename = "VerticalLineDates.csv";
   int file = FileOpen(filename, FILE_WRITE | FILE_CSV);

   if(file == INVALID_HANDLE)
   {
      Print("Failed to open file");
      return;
   }

   FileWrite(file, "ObjectName", "DateTime");

   long chart_id = ChartID();
   int total = ObjectsTotal(chart_id);

   for(int i = 0; i < total; i++)
   {
      string name = ObjectName(chart_id, i);

      if(ObjectGetInteger(chart_id, name, OBJPROP_TYPE) == OBJ_VLINE)
      {
         datetime t = (datetime)ObjectGetInteger(chart_id, name, OBJPROP_TIME);
         FileWrite(file, name, TimeToString(t, TIME_DATE | TIME_MINUTES));
      }
   }

   FileClose(file);
   Print("Export complete: ", filename);
}
