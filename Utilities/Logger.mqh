//+------------------------------------------------------------------+
//| Logger.mqh - Comprehensive logging system for Solara Platform    |
//+------------------------------------------------------------------+
#ifndef LOGGER_MQH
#define LOGGER_MQH

#include <Arrays\ArrayString.mqh>

//+------------------------------------------------------------------+
//| Log levels enumeration                                           |
//+------------------------------------------------------------------+
enum ENUM_LOG_LEVEL {
    LOG_LEVEL_ERROR = 0,    // Critical errors only
    LOG_LEVEL_WARN  = 1,    // Warnings and errors
    LOG_LEVEL_INFO  = 2,    // Informational messages (default)
    LOG_LEVEL_DEBUG = 3,    // Debug information
    LOG_LEVEL_TRACE = 4     // Detailed tracing
};

//+------------------------------------------------------------------+
//| Log entry structure                                              |
//+------------------------------------------------------------------+
struct LogEntry {
    datetime timestamp;
    ENUM_LOG_LEVEL level;
    string message;
    string context;
    string component;
};

//+------------------------------------------------------------------+
//| CLogger - Main logging class                                     |
//+------------------------------------------------------------------+
class CLogger {
private:
    ENUM_LOG_LEVEL m_logLevel;
    string m_filename;
    bool m_writeToFile;
    bool m_printToConsole;
    bool m_enabled;
    int m_maxFileSizeKB;
    CArrayString m_logBuffer;
    int m_bufferSize;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CLogger(void) : 
        m_logLevel(LOG_LEVEL_INFO),
        m_writeToFile(true),
        m_printToConsole(true),
        m_enabled(true),
        m_maxFileSizeKB(1024), // 1MB max file size
        m_bufferSize(1000)     // Keep last 1000 messages in buffer
    {
        m_filename = "Solara_Log_" + IntegerToString(GetTickCount()) + ".txt";
        m_logBuffer.Clear();
    }
    
    ~CLogger(void) {
        FlushBufferToFile();
        m_logBuffer.Clear();
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetLogLevel(ENUM_LOG_LEVEL level) { m_logLevel = level; }
    void SetWriteToFile(bool enable) { m_writeToFile = enable; }
    void SetPrintToConsole(bool enable) { m_printToConsole = enable; }
    void SetEnabled(bool enable) { m_enabled = enable; }
    void SetMaxFileSize(int sizeKB) { m_maxFileSizeKB = sizeKB; }
    void SetFilename(string filename) { m_filename = filename; }
    
    ENUM_LOG_LEVEL GetLogLevel() const { return m_logLevel; }
    bool GetWriteToFile() const { return m_writeToFile; }
    bool GetPrintToConsole() const { return m_printToConsole; }
    bool GetEnabled() const { return m_enabled; }
    
    //+------------------------------------------------------------------+
    //| Public logging methods                                           |
    //+------------------------------------------------------------------+
    void Error(string message, string context = "", string component = "") {
        LogInternal(LOG_LEVEL_ERROR, message, context, component);
    }
    
    void Warn(string message, string context = "", string component = "") {
        LogInternal(LOG_LEVEL_WARN, message, context, component);
    }
    
    void Info(string message, string context = "", string component = "") {
        LogInternal(LOG_LEVEL_INFO, message, context, component);
    }
    
    void Debug(string message, string context = "", string component = "") {
        LogInternal(LOG_LEVEL_DEBUG, message, context, component);
    }
    
    void Trace(string message, string context = "", string component = "") {
        LogInternal(LOG_LEVEL_TRACE, message, context, component);
    }
    
    //+------------------------------------------------------------------+
    //| Buffer management                                                |
    //+------------------------------------------------------------------+
    void FlushBufferToFile() {
        if(m_logBuffer.Total() == 0) return;
        
        int file_handle = FileOpen(m_filename, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI);
        if(file_handle == INVALID_HANDLE) {
            Print("Logger: Cannot open file for flushing: ", m_filename);
            return;
        }
        
        FileSeek(file_handle, 0, SEEK_END);
        for(int i = 0; i < m_logBuffer.Total(); i++) {
            FileWrite(file_handle, m_logBuffer.At(i));
        }
        FileClose(file_handle);
        
        m_logBuffer.Clear();
    }
    
    void ClearBuffer() {
        m_logBuffer.Clear();
    }
    
    int GetBufferSize() const {
        return m_logBuffer.Total();
    }
    
    void GetLastLogs(int count, string &result[]) {
        int total = m_logBuffer.Total();
        int start = MathMax(0, total - count);
        int size = total - start;
        
        ArrayResize(result, size);
        for(int i = 0; i < size; i++) {
            result[i] = m_logBuffer.At(start + i);
        }
    }

private:
    //+------------------------------------------------------------------+
    //| Internal logging implementation                                  |
    //+------------------------------------------------------------------+
    void LogInternal(ENUM_LOG_LEVEL level, string message, string context, string component) {
        if(!m_enabled || level > m_logLevel) return;
        
        string formatted = FormatMessage(level, message, context, component);
        
        // Add to buffer
        if(m_logBuffer.Total() >= m_bufferSize) {
            m_logBuffer.Delete(0);
        }
        m_logBuffer.Add(formatted);
        
        // Print to console
        if(m_printToConsole) {
            Print(formatted);
        }
        
        // Write to file (with buffering)
        if(m_writeToFile && m_logBuffer.Total() >= 10) { // Flush every 10 messages
            FlushBufferToFile();
        }
    }
    
    //+------------------------------------------------------------------+
    //| Message formatting                                               |
    //+------------------------------------------------------------------+
    string FormatMessage(ENUM_LOG_LEVEL level, string message, string context, string component) {
        string levelStr = "";
        switch(level) {
            case LOG_LEVEL_ERROR: levelStr = "ERROR"; break;
            case LOG_LEVEL_WARN:  levelStr = "WARN "; break;
            case LOG_LEVEL_INFO:  levelStr = "INFO "; break;
            case LOG_LEVEL_DEBUG: levelStr = "DEBUG"; break;
            case LOG_LEVEL_TRACE: levelStr = "TRACE"; break;
        }
        
        string timestamp = GetTimestamp();
        string componentStr = (component == "") ? "SOLARA" : component;
        string contextStr = (context == "") ? "" : " [" + context + "]";
        
        return StringFormat("%s | %s | %s | %s%s", 
                           timestamp, levelStr, componentStr, message, contextStr);
    }
    
    //+------------------------------------------------------------------+
    //| Timestamp generation                                             |
    //+------------------------------------------------------------------+
    string GetTimestamp() {
        MqlDateTime dt;
        TimeCurrent(dt);
        return StringFormat("%04d.%02d.%02d %02d:%02d:%02d", 
                           dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
    }
    
    //+------------------------------------------------------------------+
    //| File size management                                             |
    //+------------------------------------------------------------------+
    bool CheckFileSize() {
        if(!FileIsExist(m_filename)) return true;
        
        int file_handle = FileOpen(m_filename, FILE_READ|FILE_ANSI);
        if(file_handle == INVALID_HANDLE) return false;
        
        long size = (long)FileSize(file_handle); // Fixed: Added explicit cast
        FileClose(file_handle);
        
        return (size / 1024) < m_maxFileSizeKB;
    }
};

//+------------------------------------------------------------------+
//| Global logger instance                                           |
//+------------------------------------------------------------------+
CLogger* GlobalLogger = NULL;

//+------------------------------------------------------------------+
//| Logger initialization function                                   |
//+------------------------------------------------------------------+
void InitializeGlobalLogger(ENUM_LOG_LEVEL level = LOG_LEVEL_INFO) {
    if(GlobalLogger == NULL) {
        GlobalLogger = new CLogger();
        GlobalLogger.SetLogLevel(level);
        GlobalLogger.Info("Global logger initialized", "Logger");
    }
}

//+------------------------------------------------------------------+
//| Logger cleanup function                                          |
//+------------------------------------------------------------------+
void CleanupGlobalLogger() {
    if(GlobalLogger != NULL) {
        GlobalLogger.Info("Global logger cleanup", "Logger");
        GlobalLogger.FlushBufferToFile();
        delete GlobalLogger;
        GlobalLogger = NULL;
    }
}

#endif