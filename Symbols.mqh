// SymbolList.mqh - Symbol definitions for Solara Scanner
//+------------------------------------------------------------------+
//| Description: Contains array of symbols to scan                   |
//+------------------------------------------------------------------+
#ifndef SYMBOLLIST_MQH
#define SYMBOLLIST_MQH

//+------------------------------------------------------------------+
//| Symbol array                                                     |
//+------------------------------------------------------------------+
string SymbolList[] = 
{

    "AUDUSD", "EURUSD"
    //, "GBPUSD", "USDCAD", "USDCHF", "USDJPY",
    //"AUDCAD", "AUDCHF", "AUDNZD", "AUDSGD", "EURAUD", "EURCHF",
    //"EURGBP", "GBPAUD", "GBPCHF", "NZDUSD", "AUDJPY", "CADCHF",
    //"CADJPY", "CHFJPY", "EURCAD", "EURJPY", "EURNZD", "GBPCAD",
    //"GBPJPY", "GBPNZD", "NZDJPY", "CHFSGD", "EURCZK", "EURHUF",
    //"EURMXN", "EURNOK", "EURPLN", "EURSEK", "EURSGD", "EURTRY",
    //"EURZAR", "GBPMXN", "GBPNOK", "GBPSEK", "GBPSGD", "GBPTRY",
    //"NOKJPY", "NOKSEK", "NZDCAD", "NZDCHF", "SEKJPY", "SGDJPY",
    //"USDCNH", "USDCZK", "USDHUF", "USDMXN", "USDNOK", "USDPLN",
    //"USDSEK", "USDSGD", "USDTHB", "USDTRY", "USDZAR", "ZARJPY",
    //"USDHKD", "USDBRL", "USDIDR", "USDINR", "USDKRW", "USDCLP",
    //"USDCOP", "USDTWD", "AUDDKK", "AUDHUF", "AUDNOK", "AUDPLN",
    //"CADMXN", "CADSGD", "CHFDKK", "CHFHUF", "CHFNOK", "CHFPLN",
    //"CHFSEK", "EURCNH", "EURDKK", "GBPCNH", "GBPDKK", "GBPHUF",
    //"MXNJPY", "NZDCNH", "NZDHUF", "NZDSGD", "USDDKK", "EURILS",
    //"USDILS", "USDRON", "AUDCNH", "CNHJPY", "DOGEUSD", "SOLUSD",
    // "BTCAUD", "BTCEUR", "BTCGBP", "BTCUSD"

};

//+------------------------------------------------------------------+
//| Get number of symbols                                            |
//+------------------------------------------------------------------+
int GetSymbolCount()
{
    return ArraySize(SymbolList);
}

//+------------------------------------------------------------------+
//| Get symbol by index                                              |
//+------------------------------------------------------------------+
string GetSymbol(int index)
{
    if(index >= 0 && index < ArraySize(SymbolList))
        return SymbolList[index];
    return "";
}

#endif // SYMBOLLIST_MQH