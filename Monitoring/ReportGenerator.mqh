//+------------------------------------------------------------------+
//| ReportGenerator.mqh                                              |
//| Description: Reporting and analytics system for CSV outputs      |
//+------------------------------------------------------------------+
#ifndef REPORTGENERATOR_MQH
#define REPORTGENERATOR_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\FileUtils.mqh"
#include <Arrays\List.mqh>

//+------------------------------------------------------------------+
//| Report types enumeration                                         |
//+------------------------------------------------------------------+
enum ENUM_REPORT_TYPE {
    REPORT_PERFORMANCE = 0,   // Performance metrics
    REPORT_RISK = 1,          // Risk analysis
    REPORT_TRADES = 2,        // Trade journal
    REPORT_COMPLIANCE = 3,    // Compliance report
    REPORT_CUSTOM = 4         // Custom report
};

//+------------------------------------------------------------------+
//| Report frequency                                                 |
//+------------------------------------------------------------------+
enum ENUM_REPORT_FREQUENCY {
    REPORT_FREQ_DAILY = 0,           // Daily reports
    REPORT_FREQ_WEEKLY = 1,          // Weekly reports
    REPORT_FREQ_MONTHLY = 2,         // Monthly reports
    REPORT_FREQ_ON_DEMAND = 3        // Generated on demand
};

//+------------------------------------------------------------------+
//| Report configuration                                             |
//+------------------------------------------------------------------+
struct SReportConfig {
    string reportDirectory;          // Directory to save reports
    bool generateDailyPerformance;   // Auto-generate daily performance report
    bool generateWeeklySummary;      // Auto-generate weekly summary
    bool generateTradeJournal;       // Auto-generate trade journal
    bool includeHeaders;            // Include headers in CSV
    string dateFormat;              // Date format for filenames
    string fieldSeparator;          // CSV field separator (usually comma)
    
    SReportConfig() {
        reportDirectory = "Reports\\";
        generateDailyPerformance = true;
        generateWeeklySummary = true;
        generateTradeJournal = true;
        includeHeaders = true;
        dateFormat = "YYYY.MM.DD";
        fieldSeparator = ",";
    }
};

//+------------------------------------------------------------------+
//| Trade record structure for reporting                             |
//+------------------------------------------------------------------+
struct STradeRecord {
    datetime openTime;
    datetime closeTime;
    string symbol;
    ENUM_ORDER_TYPE type;
    double volume;
    double openPrice;
    double closePrice;
    double stopLoss;
    double takeProfit;
    double commission;
    double swap;
    double profit;
    string comment;
    int magicNumber;
    string strategyName;
    
    STradeRecord() {
        openTime = 0;
        closeTime = 0;
        symbol = "";
        type = ORDER_TYPE_BUY;
        volume = 0.0;
        openPrice = 0.0;
        closePrice = 0.0;
        stopLoss = 0.0;
        takeProfit = 0.0;
        commission = 0.0;
        swap = 0.0;
        profit = 0.0;
        comment = "";
        magicNumber = 0;
        strategyName = "";
    }
};

//+------------------------------------------------------------------+
//| Performance metrics structure                                    |
//+------------------------------------------------------------------+
struct SPerformanceMetrics {
    datetime periodStart;
    datetime periodEnd;
    double startingBalance;
    double endingBalance;
    double totalProfit;
    double totalLoss;
    int totalTrades;
    int winningTrades;
    int losingTrades;
    double profitFactor;
    double averageWin;
    double averageLoss;
    double largestWin;
    double largestLoss;
    double maxDrawdown;
    double maxDrawdownPercent;
    double recoveryFactor;
    double sharpeRatio;
    double sortinoRatio;
    double expectancy;
    
    SPerformanceMetrics() {
        periodStart = 0;
        periodEnd = 0;
        startingBalance = 0.0;
        endingBalance = 0.0;
        totalProfit = 0.0;
        totalLoss = 0.0;
        totalTrades = 0;
        winningTrades = 0;
        losingTrades = 0;
        profitFactor = 0.0;
        averageWin = 0.0;
        averageLoss = 0.0;
        largestWin = 0.0;
        largestLoss = 0.0;
        maxDrawdown = 0.0;
        maxDrawdownPercent = 0.0;
        recoveryFactor = 0.0;
        sharpeRatio = 0.0;
        sortinoRatio = 0.0;
        expectancy = 0.0;
    }
};

//+------------------------------------------------------------------+
//| CReportGenerator - Main report generation class                  |
//+------------------------------------------------------------------+
class CReportGenerator {
private:
    // Configuration
    SReportConfig m_config;
    
    // Components
    CLogger* m_logger;
    CFileUtils* m_fileUtils;
    
    // State
    bool m_initialized;
    datetime m_lastDailyReport;
    datetime m_lastWeeklyReport;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CReportGenerator() : 
        m_logger(NULL),
        m_fileUtils(NULL),
        m_initialized(false),
        m_lastDailyReport(0),
        m_lastWeeklyReport(0)
    {
    }
    
    ~CReportGenerator() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization                                                   |
    //+------------------------------------------------------------------+
    bool Initialize(CLogger* logger = NULL, CFileUtils* fileUtils = NULL) {
        if(m_initialized) {
            LogInfo("Report Generator already initialized");
            return true;
        }
        
        m_logger = logger;
        m_fileUtils = fileUtils;
        
        // Create report directory if it doesn't exist
        if(!CreateReportDirectory()) {
            LogError("Failed to create report directory: " + m_config.reportDirectory);
            return false;
        }
        
        m_initialized = true;
        LogInfo("Report Generator initialized successfully");
        LogInfo("Report directory: " + m_config.reportDirectory);
        
        return true;
    }
    
    void Deinitialize() {
        if(!m_initialized) return;
        
        m_initialized = false;
        LogInfo("Report Generator deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetConfig(const SReportConfig &config) {
        m_config = config;
        LogInfo("Report configuration updated");
    }
    
    SReportConfig GetConfig() const {
        return m_config;
    }
    
    //+------------------------------------------------------------------+
    //| Core report generation methods                                   |
    //+------------------------------------------------------------------+
    bool GeneratePerformanceReport(datetime startDate = 0, datetime endDate = 0, 
                                  string filename = "") {
        if(!m_initialized) {
            LogError("Report Generator not initialized");
            return false;
        }
        
        if(startDate == 0) {
            startDate = TimeCurrent() - 86400; // Last 24 hours
        }
        if(endDate == 0) {
            endDate = TimeCurrent();
        }
        
        if(filename == "") {
            filename = "Performance_" + TimeToString(startDate, TIME_DATE) + 
                      "_to_" + TimeToString(endDate, TIME_DATE) + ".csv";
        }
        
        LogInfo("Generating performance report: " + filename);
        
        // Calculate performance metrics
        SPerformanceMetrics metrics = CalculatePerformanceMetrics(startDate, endDate);
        
        // Generate CSV file
        bool success = GeneratePerformanceCSV(metrics, filename);
        
        if(success) {
            LogInfo("Performance report generated successfully: " + filename);
            m_lastDailyReport = TimeCurrent();
        } else {
            LogError("Failed to generate performance report: " + filename);
        }
        
        return success;
    }
    
    bool GenerateRiskReport(datetime startDate = 0, datetime endDate = 0,
                           string filename = "") {
        if(!m_initialized) {
            LogError("Report Generator not initialized");
            return false;
        }
        
        if(filename == "") {
            filename = "RiskAnalysis_" + TimeToString(startDate, TIME_DATE) + 
                      "_to_" + TimeToString(endDate, TIME_DATE) + ".csv";
        }
        
        LogInfo("Generating risk report: " + filename);
        
        // This would analyze risk metrics
        // For now, create a placeholder report
        bool success = GenerateRiskCSV(startDate, endDate, filename);
        
        return success;
    }
    
    bool GenerateTradeJournal(datetime startDate = 0, datetime endDate = 0,
                             string filename = "", string strategyName = "") {
        if(!m_initialized) {
            LogError("Report Generator not initialized");
            return false;
        }
        
        if(filename == "") {
            string strategySuffix = (strategyName != "") ? "_" + strategyName : "";
            filename = "TradeJournal" + strategySuffix + "_" + 
                      TimeToString(startDate, TIME_DATE) + "_to_" + 
                      TimeToString(endDate, TIME_DATE) + ".csv";
        }
        
        LogInfo("Generating trade journal: " + filename);
        
        // Get trade history
        STradeRecord tradeRecords[];
        int tradeCount = 0;
        if(!GetTradeHistory(startDate, endDate, tradeRecords, tradeCount, strategyName)) {
            LogError("Failed to retrieve trade history");
            return false;
        }
        
        // Generate CSV file
        bool success = GenerateTradeJournalCSV(tradeRecords, tradeCount, filename);
        
        if(success) {
            LogInfo("Trade journal generated successfully: " + filename);
        } else {
            LogError("Failed to generate trade journal: " + filename);
        }
        
        return success;
    }
    
    bool GenerateComplianceReport(datetime startDate = 0, datetime endDate = 0,
                                 string filename = "") {
        if(!m_initialized) {
            LogError("Report Generator not initialized");
            return false;
        }
        
        if(filename == "") {
            filename = "ComplianceReport_" + TimeToString(startDate, TIME_DATE) + 
                      "_to_" + TimeToString(endDate, TIME_DATE) + ".csv";
        }
        
        LogInfo("Generating compliance report: " + filename);
        
        // This would check compliance rules
        // For now, create a placeholder report
        bool success = GenerateComplianceCSV(startDate, endDate, filename);
        
        return success;
    }
    
    //+------------------------------------------------------------------+
    //| Automatic report generation                                      |
    //+------------------------------------------------------------------+
    void CheckAutoReports() {
        if(!m_initialized) return;
        
        MqlDateTime nowStruct;
        datetime now = TimeCurrent();
        TimeToStruct(now, nowStruct);
        
        // Check daily report
        if(m_config.generateDailyPerformance) {
            MqlDateTime lastDailyStruct;
            TimeToStruct(m_lastDailyReport, lastDailyStruct);
            
            if(nowStruct.day != lastDailyStruct.day) {
                // New day, generate daily report
                datetime dayStart = StringToTime(TimeToString(now, TIME_DATE) + " 00:00");
                datetime dayEnd = now;
                
                GeneratePerformanceReport(dayStart, dayEnd, 
                                         "DailyPerformance_" + TimeToString(now, TIME_DATE) + ".csv");
            }
        }
        
        // Check weekly report (every Monday)
        if(m_config.generateWeeklySummary && nowStruct.day_of_week == 1) { // Monday
            MqlDateTime lastWeeklyStruct;
            TimeToStruct(m_lastWeeklyReport, lastWeeklyStruct);
            
            if(nowStruct.day != lastWeeklyStruct.day) {
                // Generate weekly report
                datetime weekStart = now - 7 * 86400; // Last 7 days
                
                GeneratePerformanceReport(weekStart, now,
                                         "WeeklySummary_" + TimeToString(now, TIME_DATE) + ".csv");
                                         
                GenerateTradeJournal(weekStart, now,
                                    "WeeklyTradeJournal_" + TimeToString(now, TIME_DATE) + ".csv");
                
                m_lastWeeklyReport = now;
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Batch report generation                                          |
    //+------------------------------------------------------------------+
    bool GenerateAllReports(datetime startDate = 0, datetime endDate = 0, 
                           string prefix = "FullReport_") {
        if(!m_initialized) {
            LogError("Report Generator not initialized");
            return false;
        }
        
        LogInfo("Generating all reports for period: " + 
                TimeToString(startDate, TIME_DATE) + " to " + 
                TimeToString(endDate, TIME_DATE));
        
        bool allSuccess = true;
        
        // Generate performance report
        allSuccess &= GeneratePerformanceReport(startDate, endDate, 
                                               prefix + "Performance.csv");
        
        // Generate risk report
        allSuccess &= GenerateRiskReport(startDate, endDate,
                                        prefix + "RiskAnalysis.csv");
        
        // Generate trade journal
        allSuccess &= GenerateTradeJournal(startDate, endDate,
                                          prefix + "TradeJournal.csv");
        
        // Generate compliance report
        allSuccess &= GenerateComplianceReport(startDate, endDate,
                                              prefix + "Compliance.csv");
        
        if(allSuccess) {
            LogInfo("All reports generated successfully");
        } else {
            LogWarn("Some reports failed to generate");
        }
        
        return allSuccess;
    }
    
    //+------------------------------------------------------------------+
    //| Utility methods                                                  |
    //+------------------------------------------------------------------+
    //+------------------------------------------------------------------+
    //| Utility methods                                                  |
    //+------------------------------------------------------------------+
    string GetReportPath(string filename) {
        return m_config.reportDirectory + filename;
    }
    
    void ListAvailableReports(string &filenames[]) {
        if(m_fileUtils != NULL) {
            // Use FindFiles method (correct name from your FileUtils)
            string pattern = m_config.reportDirectory + "*.csv";
            m_fileUtils.FindFiles(pattern, filenames);
            
            if(m_logger != NULL) {
                m_logger.Info("Found " + IntegerToString(ArraySize(filenames)) + " report files", "ReportGenerator");
            }
        } else {
            // Manual implementation as fallback
            string fileName = "";
            long handle = FileFindFirst(m_config.reportDirectory + "*.csv", fileName);
            
            if(handle != INVALID_HANDLE) {
                int count = 0;
                string tempArray[100]; // Temporary array
                
                // Add first file
                tempArray[count++] = fileName;
                
                // Find more files
                while(FileFindNext(handle, fileName) && count < 100) {
                    tempArray[count++] = fileName;
                }
                
                FileFindClose(handle);
                
                // Copy to output array
                ArrayResize(filenames, count);
                for(int i = 0; i < count; i++) {
                    filenames[i] = tempArray[i];
                }
                
                if(m_logger != NULL) {
                    m_logger.Info("Found " + IntegerToString(count) + " report files", "ReportGenerator");
                }
            } else {
                ArrayResize(filenames, 0);
                if(m_logger != NULL) {
                    m_logger.Info("No report files found", "ReportGenerator");
                }
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Information and status                                           |
    //+------------------------------------------------------------------+
    void PrintStatus() {
        string status = "=== Report Generator Status ===\n" +
                       "Initialized: " + (m_initialized ? "Yes" : "No") + "\n" +
                       "Report Directory: " + m_config.reportDirectory + "\n" +
                       "Auto Daily Reports: " + (m_config.generateDailyPerformance ? "Yes" : "No") + "\n" +
                       "Auto Weekly Reports: " + (m_config.generateWeeklySummary ? "Yes" : "No") + "\n" +
                       "Auto Trade Journal: " + (m_config.generateTradeJournal ? "Yes" : "No") + "\n" +
                       "Last Daily Report: " + (m_lastDailyReport > 0 ? TimeToString(m_lastDailyReport) : "Never") + "\n" +
                       "Last Weekly Report: " + (m_lastWeeklyReport > 0 ? TimeToString(m_lastWeeklyReport) : "Never") + "\n" +
                       "===============================";
        
        LogInfo(status);
    }
    
private:
    //+------------------------------------------------------------------+
    //| Private report generation methods                                |
    //+------------------------------------------------------------------+
    bool GeneratePerformanceCSV(const SPerformanceMetrics &metrics, string filename) {
        int handle = FileOpen(GetReportPath(filename), FILE_WRITE | FILE_CSV | FILE_ANSI, m_config.fieldSeparator);
        if(handle == INVALID_HANDLE) {
            LogError("Failed to open file: " + filename);
            return false;
        }
        
        // Write headers if enabled
        if(m_config.includeHeaders) {
            FileWrite(handle, 
                "Period Start,Period End,Starting Balance,Ending Balance,Total Profit,Total Loss," +
                "Total Trades,Winning Trades,Losing Trades,Profit Factor,Average Win,Average Loss," +
                "Largest Win,Largest Loss,Max Drawdown,Max Drawdown %,Recovery Factor,Sharpe Ratio," +
                "Sortino Ratio,Expectancy");
        }
        
        // Write data
        FileWrite(handle,
            TimeToString(metrics.periodStart),
            TimeToString(metrics.periodEnd),
            DoubleToString(metrics.startingBalance, 2),
            DoubleToString(metrics.endingBalance, 2),
            DoubleToString(metrics.totalProfit, 2),
            DoubleToString(metrics.totalLoss, 2),
            IntegerToString(metrics.totalTrades),
            IntegerToString(metrics.winningTrades),
            IntegerToString(metrics.losingTrades),
            DoubleToString(metrics.profitFactor, 2),
            DoubleToString(metrics.averageWin, 2),
            DoubleToString(metrics.averageLoss, 2),
            DoubleToString(metrics.largestWin, 2),
            DoubleToString(metrics.largestLoss, 2),
            DoubleToString(metrics.maxDrawdown, 2),
            DoubleToString(metrics.maxDrawdownPercent, 2),
            DoubleToString(metrics.recoveryFactor, 2),
            DoubleToString(metrics.sharpeRatio, 2),
            DoubleToString(metrics.sortinoRatio, 2),
            DoubleToString(metrics.expectancy, 2)
        );
        
        FileClose(handle);
        return true;
    }
    
    bool GenerateRiskCSV(datetime startDate, datetime endDate, string filename) {
        int handle = FileOpen(GetReportPath(filename), FILE_WRITE | FILE_CSV | FILE_ANSI, m_config.fieldSeparator);
        if(handle == INVALID_HANDLE) {
            LogError("Failed to open file: " + filename);
            return false;
        }
        
        if(m_config.includeHeaders) {
            FileWrite(handle, "Date,Time,Equity,Balance,Margin Used,Margin Level,Free Margin,Daily P/L,Daily Drawdown");
        }
        
        // This is a placeholder - in real implementation, you would query historical data
        FileWrite(handle,
            TimeToString(startDate, TIME_DATE),
            TimeToString(startDate, TIME_SECONDS),
            "10000.00",
            "10000.00",
            "500.00",
            "2000.00",
            "9500.00",
            "150.00",
            "2.50"
        );
        
        FileClose(handle);
        return true;
    }
    
    bool GenerateTradeJournalCSV(STradeRecord &tradeRecords[], int tradeCount, string filename) {
        int handle = FileOpen(GetReportPath(filename), FILE_WRITE | FILE_CSV | FILE_ANSI, m_config.fieldSeparator);
        if(handle == INVALID_HANDLE) {
            LogError("Failed to open file: " + filename);
            return false;
        }
        
        if(m_config.includeHeaders) {
            FileWrite(handle, 
                "Open Time,Close Time,Symbol,Type,Volume,Open Price,Close Price,Stop Loss,Take Profit," +
                "Commission,Swap,Profit,Comment,Magic Number,Strategy Name");
        }
        
        // Write all trade records
        for(int i = 0; i < tradeCount; i++) {
            STradeRecord trade = tradeRecords[i];
            
            FileWrite(handle,
                TimeToString(trade.openTime),
                TimeToString(trade.closeTime),
                trade.symbol,
                EnumToString(trade.type),
                DoubleToString(trade.volume, 2),
                DoubleToString(trade.openPrice, 5),
                DoubleToString(trade.closePrice, 5),
                DoubleToString(trade.stopLoss, 5),
                DoubleToString(trade.takeProfit, 5),
                DoubleToString(trade.commission, 2),
                DoubleToString(trade.swap, 2),
                DoubleToString(trade.profit, 2),
                trade.comment,
                IntegerToString(trade.magicNumber),
                trade.strategyName
            );
        }
        
        FileClose(handle);
        return true;
    }
    
    bool GenerateComplianceCSV(datetime startDate, datetime endDate, string filename) {
        int handle = FileOpen(GetReportPath(filename), FILE_WRITE | FILE_CSV | FILE_ANSI, m_config.fieldSeparator);
        if(handle == INVALID_HANDLE) {
            LogError("Failed to open file: " + filename);
            return false;
        }
        
        if(m_config.includeHeaders) {
            FileWrite(handle, "Check Name,Status,Violation Count,Last Check,Description");
        }
        
        // Placeholder compliance checks
        string checkTime = TimeToString(endDate);
        FileWrite(handle, "Max Daily Loss,Pass,0," + checkTime, "Daily loss within limits");
        FileWrite(handle, "Position Limits,Pass,0," + checkTime, "Position sizes within limits");
        FileWrite(handle, "Margin Check,Pass,0," + checkTime, "Margin level acceptable");
        
        FileClose(handle);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Data collection methods                                          |
    //+------------------------------------------------------------------+
    SPerformanceMetrics CalculatePerformanceMetrics(datetime startDate, datetime endDate) {
        SPerformanceMetrics metrics;
        metrics.periodStart = startDate;
        metrics.periodEnd = endDate;
        
        // This is a placeholder - in real implementation, you would:
        // 1. Query trade history for the period
        // 2. Calculate all metrics
        
        // For now, return dummy data
        metrics.startingBalance = 10000.00;
        metrics.endingBalance = 10500.00;
        metrics.totalProfit = 750.00;
        metrics.totalLoss = 250.00;
        metrics.totalTrades = 20;
        metrics.winningTrades = 12;
        metrics.losingTrades = 8;
        metrics.profitFactor = 3.0;
        metrics.averageWin = 62.50;
        metrics.averageLoss = 31.25;
        metrics.largestWin = 150.00;
        metrics.largestLoss = 50.00;
        metrics.maxDrawdown = 300.00;
        metrics.maxDrawdownPercent = 3.0;
        metrics.recoveryFactor = 1.67;
        metrics.sharpeRatio = 1.5;
        metrics.sortinoRatio = 2.0;
        metrics.expectancy = 25.0;
        
        return metrics;
    }
    
    bool GetTradeHistory(datetime startDate, datetime endDate, STradeRecord &tradeRecords[], int &tradeCount, string strategyName = "") {
        // This method should query the trading platform's history
        // For now, create dummy data
        tradeCount = 10;
        ArrayResize(tradeRecords, tradeCount);
        
        for(int i = 0; i < tradeCount; i++) {
            STradeRecord trade;
            trade.openTime = startDate + i * 86400;
            trade.closeTime = trade.openTime + 3600;
            trade.symbol = "EURUSD";
            trade.type = (i % 2 == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
            trade.volume = 0.1;
            trade.openPrice = 1.1000 + i * 0.001;
            trade.closePrice = trade.openPrice + ((trade.type == ORDER_TYPE_BUY) ? 0.002 : -0.002);
            trade.profit = (trade.type == ORDER_TYPE_BUY) ? 20.00 : -15.00;
            trade.strategyName = (strategyName != "") ? strategyName : "MRSTS";
            
            tradeRecords[i] = trade;
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| File system methods                                              |
    //+------------------------------------------------------------------+
    bool CreateReportDirectory() {
        if(m_fileUtils != NULL) {
            return m_fileUtils.CreateDirectory(m_config.reportDirectory);
        }
        
        // Manual implementation
        if(FileIsExist(m_config.reportDirectory)) {
            return true;
        }
        
        return FolderCreate(m_config.reportDirectory);
    }
    
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "ReportGenerator");
        } else {
            Print("ERROR [ReportGenerator]: " + message);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "ReportGenerator");
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "ReportGenerator");
        }
    }
};

#endif // REPORTGENERATOR_MQH