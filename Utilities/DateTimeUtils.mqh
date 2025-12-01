//+------------------------------------------------------------------+
//| DateTimeUtils.mqh - Time and date utilities for Solara           |
//+------------------------------------------------------------------+
#ifndef DATETIMEUTILS_MQH
#define DATETIMEUTILS_MQH

#include "Logger.mqh"

//+------------------------------------------------------------------+
//| Trading session times                                            |
//+------------------------------------------------------------------+
struct TradingSession {
    string name;
    int startHour;
    int startMinute;
    int endHour;
    int endMinute;
    bool overnight; // Session crosses midnight
};

//+------------------------------------------------------------------+
//| Market hours configuration                                       |
//+------------------------------------------------------------------+
class CMarketHours {
private:
    TradingSession m_sessions[];
    string m_symbol;
    
public:
    CMarketHours(string symbol) : m_symbol(symbol) {
        InitializeSessions();
    }
    
    void InitializeSessions() {
        // Default sessions for major markets
        // Can be extended with actual market hours
        ArrayResize(m_sessions, 3);
        
        // Asian session
        m_sessions[0].name = "Asian";
        m_sessions[0].startHour = 0;
        m_sessions[0].startMinute = 0;
        m_sessions[0].endHour = 9;
        m_sessions[0].endMinute = 0;
        m_sessions[0].overnight = false;
        
        // European session
        m_sessions[1].name = "European";
        m_sessions[1].startHour = 8;
        m_sessions[1].startMinute = 0;
        m_sessions[1].endHour = 17;
        m_sessions[1].endMinute = 0;
        m_sessions[1].overnight = false;
        
        // US session
        m_sessions[2].name = "US";
        m_sessions[2].startHour = 14;
        m_sessions[2].startMinute = 0;
        m_sessions[2].endHour = 23;
        m_sessions[2].endMinute = 0;
        m_sessions[2].overnight = false;
    }
    
    bool IsMarketOpen() {
        MqlDateTime current;
        TimeCurrent(current);
        
        for(int i = 0; i < ArraySize(m_sessions); i++) {
            if(IsInSession(current, m_sessions[i])) {
                return true;
            }
        }
        return false;
    }
    
    string GetCurrentSession() {
        MqlDateTime current;
        TimeCurrent(current);
        
        for(int i = 0; i < ArraySize(m_sessions); i++) {
            if(IsInSession(current, m_sessions[i])) {
                return m_sessions[i].name;
            }
        }
        return "Closed";
    }
    
private:
    bool IsInSession(const MqlDateTime &dt, const TradingSession &session) {
        int currentMinutes = dt.hour * 60 + dt.min;
        int startMinutes = session.startHour * 60 + session.startMinute;
        int endMinutes = session.endHour * 60 + session.endMinute;
        
        if(session.overnight) {
            return currentMinutes >= startMinutes || currentMinutes <= endMinutes;
        } else {
            return currentMinutes >= startMinutes && currentMinutes <= endMinutes;
        }
    }
};

//+------------------------------------------------------------------+
//| CDateTimeUtils - Main date/time utility class                    |
//+------------------------------------------------------------------+
class CDateTimeUtils {
private:
    CLogger* m_logger;
    
public:
    CDateTimeUtils(void) {
        m_logger = GlobalLogger;
    }
    
    //+------------------------------------------------------------------+
    //| Time conversion methods                                          |
    //+------------------------------------------------------------------+
    datetime StringToTime(string timeStr) {
        return StringToTime(timeStr, TimeCurrent());
    }
    
    datetime StringToTime(string timeStr, datetime baseTime) {
        MqlDateTime baseDt;
        TimeToStruct(baseTime, baseDt);
        
        string parts[];
        int count = StringSplit(timeStr, ':', parts);
        
        if(count >= 1) baseDt.hour = (int)StringToInteger(parts[0]);
        if(count >= 2) baseDt.min = (int)StringToInteger(parts[1]);
        if(count >= 3) baseDt.sec = (int)StringToInteger(parts[2]);
        
        return StructToTime(baseDt);
    }
    
    string TimeToString(datetime time, bool includeSeconds = false) {
        MqlDateTime dt;
        TimeToStruct(time, dt);
        
        if(includeSeconds) {
            return StringFormat("%02d:%02d:%02d", dt.hour, dt.min, dt.sec);
        } else {
            return StringFormat("%02d:%02d", dt.hour, dt.min);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Time comparison methods                                          |
    //+------------------------------------------------------------------+
    bool IsSameDay(datetime time1, datetime time2) {
        MqlDateTime dt1, dt2;
        TimeToStruct(time1, dt1);
        TimeToStruct(time2, dt2);
        
        return (dt1.year == dt2.year && dt1.mon == dt2.mon && dt1.day == dt2.day);
    }
    
    bool IsSameHour(datetime time1, datetime time2) {
        MqlDateTime dt1, dt2;
        TimeToStruct(time1, dt1);
        TimeToStruct(time2, dt2);
        
        return (dt1.year == dt2.year && dt1.mon == dt2.mon && 
                dt1.day == dt2.day && dt1.hour == dt2.hour);
    }
    
    bool IsSameMinute(datetime time1, datetime time2) {
        MqlDateTime dt1, dt2;
        TimeToStruct(time1, dt1);
        TimeToStruct(time2, dt2);
        
        return (dt1.year == dt2.year && dt1.mon == dt2.mon && 
                dt1.day == dt2.day && dt1.hour == dt2.hour && dt1.min == dt2.min);
    }
    
    //+------------------------------------------------------------------+
    //| Time arithmetic methods                                          |
    //+------------------------------------------------------------------+
    datetime AddDays(datetime time, int days) {
        return time + (days * 86400);
    }
    
    datetime AddHours(datetime time, int hours) {
        return time + (hours * 3600);
    }
    
    datetime AddMinutes(datetime time, int minutes) {
        return time + (minutes * 60);
    }
    
    datetime AddSeconds(datetime time, int seconds) {
        return time + seconds;
    }
    
    //+------------------------------------------------------------------+
    //| Business day calculations                                        |
    //+------------------------------------------------------------------+
    bool IsWeekend(datetime time) {
        MqlDateTime dt;
        TimeToStruct(time, dt);
        return (dt.day_of_week == 0 || dt.day_of_week == 6); // Sunday or Saturday
    }
    
    bool IsWeekday(datetime time) {
        return !IsWeekend(time);
    }
    
    datetime GetNextBusinessDay(datetime time) {
        datetime nextDay = AddDays(time, 1);
        while(IsWeekend(nextDay)) {
            nextDay = AddDays(nextDay, 1);
        }
        return nextDay;
    }
    
    datetime GetPreviousBusinessDay(datetime time) {
        datetime prevDay = AddDays(time, -1);
        while(IsWeekend(prevDay)) {
            prevDay = AddDays(prevDay, -1);
        }
        return prevDay;
    }
    
    //+------------------------------------------------------------------+
    //| Bar time calculations                                            |
    //+------------------------------------------------------------------+
    datetime GetBarOpenTime(ENUM_TIMEFRAMES timeframe, int shift = 0) {
        return iTime(_Symbol, timeframe, shift);
    }
    
    datetime GetBarCloseTime(ENUM_TIMEFRAMES timeframe, int shift = 0) {
        datetime openTime = GetBarOpenTime(timeframe, shift);
        return openTime + GetTimeframeSeconds(timeframe);
    }
    
    bool IsNewBar(ENUM_TIMEFRAMES timeframe, datetime &lastBarTime) {
        datetime currentBarTime = GetBarOpenTime(timeframe, 0);
        if(currentBarTime != lastBarTime) {
            lastBarTime = currentBarTime;
            return true;
        }
        return false;
    }
    
    int GetTimeframeSeconds(ENUM_TIMEFRAMES timeframe) {
        switch(timeframe) {
            case PERIOD_M1: return 60;
            case PERIOD_M5: return 300;
            case PERIOD_M15: return 900;
            case PERIOD_M30: return 1800;
            case PERIOD_H1: return 3600;
            case PERIOD_H4: return 14400;
            case PERIOD_D1: return 86400;
            case PERIOD_W1: return 604800;
            case PERIOD_MN1: return 2592000; // Approximate
            default: return 0;
        }
    }
    
    string TimeframeToString(ENUM_TIMEFRAMES timeframe) {
        switch(timeframe) {
            case PERIOD_M1: return "M1";
            case PERIOD_M5: return "M5";
            case PERIOD_M15: return "M15";
            case PERIOD_M30: return "M30";
            case PERIOD_H1: return "H1";
            case PERIOD_H4: return "H4";
            case PERIOD_D1: return "D1";
            case PERIOD_W1: return "W1";
            case PERIOD_MN1: return "MN1";
            default: return "Unknown";
        }
    }
    
    //+------------------------------------------------------------------+
    //| Timezone conversion methods                                      |
    //+------------------------------------------------------------------+
    datetime ConvertTimeZone(datetime sourceTime, int sourceOffset, int targetOffset) {
        return sourceTime + (targetOffset - sourceOffset) * 3600;
    }
    
    datetime ServerToGMT(datetime serverTime) {
        // Convert server time to GMT (server time is usually GMT+2 or GMT+3)
        MqlDateTime serverDt;
        TimeToStruct(serverTime, serverDt);
        return serverTime - serverDt.hour * 3600; // Simple conversion
    }
    
    datetime GMTToServer(datetime gmtTime) {
        MqlDateTime gmtDt;
        TimeToStruct(gmtTime, gmtDt);
        return gmtTime + gmtDt.hour * 3600;
    }
    
    //+------------------------------------------------------------------+
    //| Time validation methods                                          |
    //+------------------------------------------------------------------+
    bool IsValidTime(string timeStr) {
        string parts[];
        int count = StringSplit(timeStr, ':', parts);
        
        if(count < 2 || count > 3) return false;
        
        int hour = (int)StringToInteger(parts[0]);
        int minute = (int)StringToInteger(parts[1]);
        int second = (count == 3) ? (int)StringToInteger(parts[2]) : 0;
        
        return (hour >= 0 && hour <= 23 && 
                minute >= 0 && minute <= 59 && 
                second >= 0 && second <= 59);
    }
    
    bool IsFutureTime(datetime time) {
        return time > TimeCurrent();
    }
    
    bool IsPastTime(datetime time) {
        return time < TimeCurrent();
    }
    
    //+------------------------------------------------------------------+
    //| Duration calculations                                            |
    //+------------------------------------------------------------------+
    double GetDurationMinutes(datetime startTime, datetime endTime) {
        return (endTime - startTime) / 60.0;
    }
    
    double GetDurationHours(datetime startTime, datetime endTime) {
        return (endTime - startTime) / 3600.0;
    }
    
    double GetDurationDays(datetime startTime, datetime endTime) {
        return (endTime - startTime) / 86400.0;
    }
    
    string FormatDuration(double minutes) {
        if(minutes < 60) {
            return StringFormat("%.0f minutes", minutes);
        } else if(minutes < 1440) {
            return StringFormat("%.1f hours", minutes / 60);
        } else {
            return StringFormat("%.1f days", minutes / 1440);
        }
    }
};

//+------------------------------------------------------------------+
//| Global date/time utils instance                                  |
//+------------------------------------------------------------------+
CDateTimeUtils* GlobalDateTimeUtils = NULL;

//+------------------------------------------------------------------+
//| Date/time utils initialization                                   |
//+------------------------------------------------------------------+
void InitializeGlobalDateTimeUtils() {
    if(GlobalDateTimeUtils == NULL) {
        GlobalDateTimeUtils = new CDateTimeUtils();
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global date/time utils initialized", "DateTimeUtils");
        }
    }
}

//+------------------------------------------------------------------+
//| Date/time utils cleanup                                          |
//+------------------------------------------------------------------+
void CleanupGlobalDateTimeUtils() {
    if(GlobalDateTimeUtils != NULL) {
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global date/time utils cleanup", "DateTimeUtils");
        }
        delete GlobalDateTimeUtils;
        GlobalDateTimeUtils = NULL;
    }
}

#endif