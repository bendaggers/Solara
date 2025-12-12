//+------------------------------------------------------------------+
//| AlertSystem.mqh                                                  |
//| Description: Multi-channel alert and notification system         |
//+------------------------------------------------------------------+
#ifndef ALERTSYSTEM_MQH
#define ALERTSYSTEM_MQH

#include "..\Utilities\Logger.mqh"

//+------------------------------------------------------------------+
//| Alert priority levels                                            |
//+------------------------------------------------------------------+
enum ENUM_ALERT_PRIORITY {
    ALERT_INFO = 0,      // Informational
    ALERT_WARNING = 1,   // Warning
    ALERT_ERROR = 2,     // Error
    ALERT_CRITICAL = 3   // Critical - requires immediate attention
};

//+------------------------------------------------------------------+
//| Alert channel enumeration                                        |
//+------------------------------------------------------------------+
enum ENUM_ALERT_CHANNEL {
    CHANNEL_TERMINAL = 0,    // MetaTrader terminal alert
    CHANNEL_EMAIL = 1,       // Email notification
    CHANNEL_SMS = 2,         // SMS (reserved for future)
    CHANNEL_PUSH = 3,        // Push notification (reserved)
    CHANNEL_ALL = 4          // All channels
};

//+------------------------------------------------------------------+
//| Alert condition structure                                        |
//+------------------------------------------------------------------+
struct SAlertCondition {
    string conditionName;
    string conditionExpression;
    ENUM_ALERT_PRIORITY priority;
    bool enabled;
    datetime lastTriggered;
    int triggerCount;
    
    SAlertCondition() {
        conditionName = "";
        conditionExpression = "";
        priority = ALERT_INFO;
        enabled = true;
        lastTriggered = 0;
        triggerCount = 0;
    }
};

//+------------------------------------------------------------------+
//| Alert configuration                                              |
//+------------------------------------------------------------------+
struct SAlertConfig {
    bool enableTerminalAlerts;
    bool enableEmailAlerts;
    bool enableSMSAlerts;
    string emailAddress;
    string smtpServer;
    int smtpPort;
    string smtpLogin;
    string smtpPassword;
    string smsApiKey;        // Reserved for future
    string smsPhoneNumber;   // Reserved for future
    
    // Rate limiting
    int maxAlertsPerHour;
    int minSecondsBetweenSameAlert;
    
    SAlertConfig() {
        enableTerminalAlerts = true;
        enableEmailAlerts = false;
        enableSMSAlerts = false;
        emailAddress = "";
        smtpServer = "smtp.gmail.com";
        smtpPort = 587;
        smtpLogin = "";
        smtpPassword = "";
        smsApiKey = "";
        smsPhoneNumber = "";
        maxAlertsPerHour = 60;
        minSecondsBetweenSameAlert = 300; // 5 minutes
    }
};

//+------------------------------------------------------------------+
//| CAlertSystem - Main alert system class                           |
//+------------------------------------------------------------------+
class CAlertSystem {
private:
    // Configuration
    SAlertConfig m_config;
    
    // Components
    CLogger* m_logger;
    
    // Alert history
    struct SAlertRecord {
        datetime timestamp;
        ENUM_ALERT_PRIORITY priority;
        ENUM_ALERT_CHANNEL channel;
        string message;
        string source;
        bool sent;
    };
    
    SAlertRecord m_alertHistory[1000];
    int m_historyCount;
    
    // Rate limiting
    datetime m_lastAlertTimes[100];
    string m_lastAlertMessages[100];
    int m_alertTimeCount;
    int m_alertsThisHour;
    datetime m_hourStart;
    
    // Conditions
    SAlertCondition m_conditions[50];
    int m_conditionCount;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CAlertSystem() : 
        m_logger(NULL),
        m_historyCount(0),
        m_alertTimeCount(0),
        m_alertsThisHour(0),
        m_hourStart(TimeCurrent()),
        m_conditionCount(0)
    {
        // Initialize alert history (cannot use ArrayInitialize with custom structs)
        for(int i = 0; i < 1000; i++) {
            m_alertHistory[i].timestamp = 0;
            m_alertHistory[i].priority = ALERT_INFO;
            m_alertHistory[i].channel = CHANNEL_TERMINAL;
            m_alertHistory[i].message = "";
            m_alertHistory[i].source = "";
            m_alertHistory[i].sent = false;
        }
        
        // Initialize rate limiting arrays
        for(int i = 0; i < 100; i++) {
            m_lastAlertTimes[i] = 0;
            m_lastAlertMessages[i] = "";
        }
        
        // Initialize conditions
        for(int i = 0; i < 50; i++) {
            m_conditions[i].conditionName = "";
            m_conditions[i].conditionExpression = "";
            m_conditions[i].priority = ALERT_INFO;
            m_conditions[i].enabled = false;
            m_conditions[i].lastTriggered = 0;
            m_conditions[i].triggerCount = 0;
        }
    }
    
    ~CAlertSystem() {
        // Cleanup if needed
    }
    
    //+------------------------------------------------------------------+
    //| Initialization                                                   |
    //+------------------------------------------------------------------+
    bool Initialize(CLogger* logger = NULL) {
        m_logger = logger;
        
        if(m_logger != NULL) {
            m_logger.Info("Alert System initialized", "AlertSystem");
        }
        
        // Load default alert conditions
        InitializeDefaultConditions();
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetConfig(const SAlertConfig &config) {
        m_config = config;
        
        if(m_logger != NULL) {
            m_logger.Info("Alert system configuration updated", "AlertSystem");
        }
    }
    
    SAlertConfig GetConfig() const {
        return m_config;
    }
    
    void EnableEmailAlerts(string email, string smtpServer, int port, 
                          string login, string password) {
        m_config.enableEmailAlerts = true;
        m_config.emailAddress = email;
        m_config.smtpServer = smtpServer;
        m_config.smtpPort = port;
        m_config.smtpLogin = login;
        m_config.smtpPassword = password;
        
        if(m_logger != NULL) {
            m_logger.Info("Email alerts enabled for: " + email, "AlertSystem");
        }
    }
    
    void DisableEmailAlerts() {
        m_config.enableEmailAlerts = false;
        if(m_logger != NULL) {
            m_logger.Info("Email alerts disabled", "AlertSystem");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Core alert sending methods                                       |
    //+------------------------------------------------------------------+
    bool SendAlert(string message, ENUM_ALERT_PRIORITY priority = ALERT_INFO, 
                  string source = "", ENUM_ALERT_CHANNEL channel = CHANNEL_ALL) {
        
        // Check rate limits
        if(!CheckRateLimits(message, priority)) {
            return false;
        }
        
        bool success = true;
        datetime now = TimeCurrent();
        
        // Terminal alerts (always if enabled)
        if(m_config.enableTerminalAlerts && 
           (channel == CHANNEL_ALL || channel == CHANNEL_TERMINAL)) {
            SendTerminalAlert(message, priority);
        }
        
        // Email alerts
        if(m_config.enableEmailAlerts && priority >= ALERT_WARNING &&
           (channel == CHANNEL_ALL || channel == CHANNEL_EMAIL)) {
            if(!SendEmailAlert(message, priority, source)) {
                success = false;
                if(m_logger != NULL) {
                    m_logger.Error("Failed to send email alert: " + message, "AlertSystem");
                }
            }
        }
        
        // SMS alerts (reserved for future)
        if(m_config.enableSMSAlerts && priority >= ALERT_CRITICAL &&
           (channel == CHANNEL_ALL || channel == CHANNEL_SMS)) {
            // Placeholder for SMS integration
            if(m_logger != NULL) {
                m_logger.Warn("SMS alerts not yet implemented", "AlertSystem");
            }
        }
        
        // Record in history
        RecordAlert(now, priority, channel, message, source, success);
        
        // Update rate limiting
        UpdateRateLimits(message, now);
        
        return success;
    }
    
    bool SendAlert(string message, string source = "") {
        return SendAlert(message, ALERT_INFO, source, CHANNEL_ALL);
    }
    
    //+------------------------------------------------------------------+
    //| Priority-specific alert methods                                  |
    //+------------------------------------------------------------------+
    bool SendInfo(string message, string source = "") {
        return SendAlert(message, ALERT_INFO, source);
    }
    
    bool SendWarning(string message, string source = "") {
        return SendAlert(message, ALERT_WARNING, source);
    }
    
    bool SendError(string message, string source = "") {
        return SendAlert(message, ALERT_ERROR, source);
    }
    
    bool SendCritical(string message, string source = "") {
        return SendAlert(message, ALERT_CRITICAL, source);
    }
    
    //+------------------------------------------------------------------+
    //| Alert condition management                                       |
    //+------------------------------------------------------------------+
    bool AddCondition(const SAlertCondition &condition) {
        if(m_conditionCount >= 50) {
            if(m_logger != NULL) {
                m_logger.Error("Maximum alert conditions reached (50)", "AlertSystem");
            }
            return false;
        }
        
        m_conditions[m_conditionCount] = condition;
        m_conditionCount++;
        
        if(m_logger != NULL) {
            m_logger.Info("Added alert condition: " + condition.conditionName, "AlertSystem");
        }
        
        return true;
    }
    
    bool RemoveCondition(string conditionName) {
        for(int i = 0; i < m_conditionCount; i++) {
            if(m_conditions[i].conditionName == conditionName) {
                // Shift remaining conditions
                for(int j = i; j < m_conditionCount - 1; j++) {
                    m_conditions[j] = m_conditions[j + 1];
                }
                m_conditionCount--;
                
                if(m_logger != NULL) {
                    m_logger.Info("Removed alert condition: " + conditionName, "AlertSystem");
                }
                return true;
            }
        }
        return false;
    }
    
    void EvaluateConditions() {
        for(int i = 0; i < m_conditionCount; i++) {
            if(m_conditions[i].enabled) {
                // In a real system, you would evaluate the conditionExpression
                // This is a placeholder for actual condition evaluation
                bool conditionMet = false; // Evaluate based on conditionExpression
                
                if(conditionMet) {
                    // Check if enough time has passed since last trigger
                    datetime now = TimeCurrent();
                    if(now - m_conditions[i].lastTriggered > m_config.minSecondsBetweenSameAlert) {
                        SendAlert("Condition triggered: " + m_conditions[i].conditionName,
                                 m_conditions[i].priority, "ConditionMonitor");
                        
                        m_conditions[i].lastTriggered = now;
                        m_conditions[i].triggerCount++;
                    }
                }
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Alert history and statistics                                    |
    //+------------------------------------------------------------------+
    int GetAlertCount(ENUM_ALERT_PRIORITY priority = -1, datetime fromTime = 0) const {
        int count = 0;
        for(int i = 0; i < m_historyCount; i++) {
            if((priority == -1 || m_alertHistory[i].priority == priority) &&
               (fromTime == 0 || m_alertHistory[i].timestamp >= fromTime)) {
                count++;
            }
        }
        return count;
    }
    
    void GetRecentAlerts(SAlertRecord &alerts[], int count = 10) {
        int startIdx = MathMax(0, m_historyCount - count);
        int numAlerts = MathMin(count, m_historyCount - startIdx);
        
        ArrayResize(alerts, numAlerts);
        for(int i = 0; i < numAlerts; i++) {
            alerts[i] = m_alertHistory[startIdx + i];
        }
    }
    
    void ClearHistory() {
        m_historyCount = 0;
        if(m_logger != NULL) {
            m_logger.Info("Alert history cleared", "AlertSystem");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Information and status                                           |
    //+------------------------------------------------------------------+
    void PrintStatus() {
        if(m_logger == NULL) return;
        
        string status = "=== Alert System Status ===\n" +
                       "Terminal Alerts: " + (m_config.enableTerminalAlerts ? "Enabled" : "Disabled") + "\n" +
                       "Email Alerts: " + (m_config.enableEmailAlerts ? "Enabled" : "Disabled") + "\n" +
                       "SMS Alerts: " + (m_config.enableSMSAlerts ? "Enabled" : "Disabled") + "\n" +
                       "Conditions Registered: " + IntegerToString(m_conditionCount) + "\n" +
                       "Total Alerts Sent: " + IntegerToString(m_historyCount) + "\n" +
                       "Alerts This Hour: " + IntegerToString(m_alertsThisHour) + "\n" +
                       "Info Alerts: " + IntegerToString(GetAlertCount(ALERT_INFO)) + "\n" +
                       "Warning Alerts: " + IntegerToString(GetAlertCount(ALERT_WARNING)) + "\n" +
                       "Error Alerts: " + IntegerToString(GetAlertCount(ALERT_ERROR)) + "\n" +
                       "Critical Alerts: " + IntegerToString(GetAlertCount(ALERT_CRITICAL)) + "\n" +
                       "============================";
        
        m_logger.Info(status, "AlertSystem");
    }
    
private:
    //+------------------------------------------------------------------+
    //| Private alert sending methods                                    |
    //+------------------------------------------------------------------+
    void SendTerminalAlert(string message, ENUM_ALERT_PRIORITY priority) {
        string prefix = GetPriorityPrefix(priority);
        Alert(prefix + " " + message);
        
        // Also print to experts journal
        Print(prefix + " " + message);
    }
    
    bool SendEmailAlert(string message, ENUM_ALERT_PRIORITY priority, string source) {
        // Note: MQL4/5 doesn't have built-in email with SMTP auth
        // This is a placeholder - you'd need to implement using DLL or WebRequest
        
        string subject = "Solara Alert: " + GetPriorityString(priority);
        if(source != "") {
            subject += " [" + source + "]";
        }
        
        // In MQL4, you can use SendMail() but it requires MT4/5 terminal email configuration
        // In MQL5, you might need to use WebRequest() to call an email API
        
        bool success = false;
        
        // Try MQL4/5 built-in SendMail (requires terminal email configuration)
        if(TerminalInfoInteger(TERMINAL_EMAIL_ENABLED)) {
            success = SendMail(subject, message);
        }
        
        // Alternative: Use WebRequest in MQL5 to call an email API
        // if(!success && MQLInfoInteger(MQL5_DLLS_ALLOWED)) {
        //     success = SendEmailViaAPI(subject, message);
        // }
        
        return success;
    }
    
    //+------------------------------------------------------------------+
    //| Rate limiting methods                                            |
    //+------------------------------------------------------------------+
    bool CheckRateLimits(string message, ENUM_ALERT_PRIORITY priority) {
        datetime now = TimeCurrent();
        
        // Reset hourly counter if new hour
        if(now - m_hourStart >= 3600) {
            m_alertsThisHour = 0;
            m_hourStart = now;
        }
        
        // Check hourly limit (skip for critical alerts)
        if(priority != ALERT_CRITICAL && m_alertsThisHour >= m_config.maxAlertsPerHour) {
            if(m_logger != NULL) {
                m_logger.Warn("Alert rate limit exceeded (" + IntegerToString(m_config.maxAlertsPerHour) + 
                             " per hour)", "AlertSystem");
            }
            return false;
        }
        
        // Check minimum time between identical alerts
        for(int i = 0; i < m_alertTimeCount; i++) {
            if(m_lastAlertMessages[i] == message && 
               (now - m_lastAlertTimes[i]) < m_config.minSecondsBetweenSameAlert) {
                return false; // Too soon for same alert
            }
        }
        
        return true;
    }
    
    void UpdateRateLimits(string message, datetime timestamp) {
        // Update hourly counter
        m_alertsThisHour++;
        
        // Update last alert times (circular buffer)
        if(m_alertTimeCount >= 100) {
            m_alertTimeCount = 0;
        }
        
        m_lastAlertTimes[m_alertTimeCount] = timestamp;
        m_lastAlertMessages[m_alertTimeCount] = message;
        m_alertTimeCount++;
    }
    
    //+------------------------------------------------------------------+
    //| History recording                                                |
    //+------------------------------------------------------------------+
    void RecordAlert(datetime timestamp, ENUM_ALERT_PRIORITY priority, 
                    ENUM_ALERT_CHANNEL channel, string message, 
                    string source, bool sent) {
        if(m_historyCount >= 1000) {
            // Shift history (remove oldest)
            for(int i = 0; i < 999; i++) {
                m_alertHistory[i] = m_alertHistory[i + 1];
            }
            m_historyCount = 999;
        }
        
        m_alertHistory[m_historyCount].timestamp = timestamp;
        m_alertHistory[m_historyCount].priority = priority;
        m_alertHistory[m_historyCount].channel = channel;
        m_alertHistory[m_historyCount].message = message;
        m_alertHistory[m_historyCount].source = source;
        m_alertHistory[m_historyCount].sent = sent;
        
        m_historyCount++;
    }
    
    //+------------------------------------------------------------------+
    //| Helper methods                                                   |
    //+------------------------------------------------------------------+
    string GetPriorityPrefix(ENUM_ALERT_PRIORITY priority) {
        switch(priority) {
            case ALERT_INFO: return "[INFO]";
            case ALERT_WARNING: return "[WARNING]";
            case ALERT_ERROR: return "[ERROR]";
            case ALERT_CRITICAL: return "[CRITICAL]";
            default: return "[UNKNOWN]";
        }
    }
    
    string GetPriorityString(ENUM_ALERT_PRIORITY priority) {
        switch(priority) {
            case ALERT_INFO: return "Information";
            case ALERT_WARNING: return "Warning";
            case ALERT_ERROR: return "Error";
            case ALERT_CRITICAL: return "Critical";
            default: return "Unknown";
        }
    }
    
    void InitializeDefaultConditions() {
        // Add some default alert conditions
        SAlertCondition condition;
        
        // Example: Equity drawdown condition
        condition.conditionName = "Equity Drawdown > 10%";
        condition.conditionExpression = "EquityDrawdown > 10";
        condition.priority = ALERT_WARNING;
        AddCondition(condition);
        
        // Example: Connection loss
        condition.conditionName = "Terminal Connection Lost";
        condition.conditionExpression = "IsConnected == false";
        condition.priority = ALERT_ERROR;
        AddCondition(condition);
        
        // Example: Margin level warning
        condition.conditionName = "Margin Level < 100%";
        condition.conditionExpression = "MarginLevel < 100";
        condition.priority = ALERT_CRITICAL;
        AddCondition(condition);
    }
    
    //+------------------------------------------------------------------+
    //| Email API method (placeholder for MQL5)                         |
    //+------------------------------------------------------------------+
    bool SendEmailViaAPI(string subject, string body) {
        // This would use WebRequest() to call an email API
        // Implementation depends on your email service provider
        return false; // Placeholder
    }
};

#endif // ALERTSYSTEM_MQH