// PositionManager.mqh - Comprehensive position management for Solara Platform
//+------------------------------------------------------------------+
//| Description: Manages all open positions, provides position       |
//|              analytics, handles position modifications, and      |
//|              ensures proper position tracking across strategies  |
//+------------------------------------------------------------------+
#ifndef POSITIONMANAGER_MQH
#define POSITIONMANAGER_MQH

#include "..\Utilities\Logger.mqh"
#include "..\Utilities\DateTimeUtils.mqh"
#include "..\Utilities\MathUtils.mqh"
#include "..\Utilities\ArrayUtils.mqh"
#include "..\Data\MarketData.mqh"

//+------------------------------------------------------------------+
//| Position status enumeration                                      |
//+------------------------------------------------------------------+
enum ENUM_POSITION_STATUS {
    POSITION_STATUS_OPEN,           // Position is open
    POSITION_STATUS_CLOSED,         // Position is closed
    POSITION_STATUS_MODIFIED,       // Position was modified
    POSITION_STATUS_PENDING_CLOSE,  // Position pending close
    POSITION_STATUS_ERROR           // Position in error state
};

//+------------------------------------------------------------------+
//| Position data structure                                          |
//+------------------------------------------------------------------+
struct SPositionData {
    // Core identification
    ulong           ticket;            // Position ticket
    ulong           magic;             // Magic number (strategy ID)
    string          symbol;            // Symbol name
    ENUM_POSITION_TYPE type;           // Position type (buy/sell)
    double          volume;            // Position volume
    datetime        openTime;          // Position open time
    double          openPrice;         // Position open price
    
    // Current state
    double          currentPrice;      // Current price (bid/ask depending on type)
    double          profit;            // Current profit/loss
    double          swap;              // Swap value
    double          commission;        // Commission
    
    // Exit levels
    double          stopLoss;          // Stop loss price
    double          takeProfit;        // Take profit price
    double          breakEvenPrice;    // Break-even price (if modified)
    
    // Management
    ENUM_POSITION_STATUS status;       // Position status
    string          comment;           // Position comment
    string          strategyName;      // Strategy that opened position
    int             modifications;     // Number of modifications
    
    // Risk metrics
    double          riskAmount;        // Risk amount in account currency
    double          riskPercent;       // Risk percentage of account
    double          maxFavorable;      // Maximum favorable excursion
    double          maxAdverse;        // Maximum adverse excursion
    double          currentDrawdown;   // Current drawdown from peak
    
    // Statistics
    double          peakProfit;        // Peak profit reached
    double          valleyProfit;      // Lowest profit reached
    datetime        lastUpdate;        // Last update time
    
    // Default constructor
    SPositionData() : 
        ticket(0),
        magic(0),
        symbol(""),
        type(POSITION_TYPE_BUY),
        volume(0),
        openTime(0),
        openPrice(0),
        currentPrice(0),
        profit(0),
        swap(0),
        commission(0),
        stopLoss(0),
        takeProfit(0),
        breakEvenPrice(0),
        status(POSITION_STATUS_OPEN),
        comment(""),
        strategyName(""),
        modifications(0),
        riskAmount(0),
        riskPercent(0),
        maxFavorable(0),
        maxAdverse(0),
        currentDrawdown(0),
        peakProfit(0),
        valleyProfit(0),
        lastUpdate(0)
    {}
    
    // Copy constructor for MQL5 compatibility
    SPositionData(const SPositionData &other) {
        this = other;
    }
    
    // Assignment operator
    void operator=(const SPositionData &other) {
        ticket = other.ticket;
        magic = other.magic;
        symbol = other.symbol;
        type = other.type;
        volume = other.volume;
        openTime = other.openTime;
        openPrice = other.openPrice;
        currentPrice = other.currentPrice;
        profit = other.profit;
        swap = other.swap;
        commission = other.commission;
        stopLoss = other.stopLoss;
        takeProfit = other.takeProfit;
        breakEvenPrice = other.breakEvenPrice;
        status = other.status;
        comment = other.comment;
        strategyName = other.strategyName;
        modifications = other.modifications;
        riskAmount = other.riskAmount;
        riskPercent = other.riskPercent;
        maxFavorable = other.maxFavorable;
        maxAdverse = other.maxAdverse;
        currentDrawdown = other.currentDrawdown;
        peakProfit = other.peakProfit;
        valleyProfit = other.valleyProfit;
        lastUpdate = other.lastUpdate;
    }
    
    // Check if position is buy
    bool IsBuy() const { return type == POSITION_TYPE_BUY; }
    
    // Check if position is sell
    bool IsSell() const { return type == POSITION_TYPE_SELL; }
    
    // Check if position has stop loss
    bool HasStopLoss() const { return stopLoss > 0; }
    
    // Check if position has take profit
    bool HasTakeProfit() const { return takeProfit > 0; }
    
    // Check if position is profitable
    bool IsProfitable() const { return profit > 0; }
    
    // Get position age in seconds
    long GetAgeSeconds() const { return TimeCurrent() - openTime; }
    
    // Get position age in minutes
    double GetAgeMinutes() const { return GetAgeSeconds() / 60.0; }
    
    // Get position age in hours
    double GetAgeHours() const { return GetAgeSeconds() / 3600.0; }
    
    // Get distance to stop loss in points
    double GetStopLossDistance() const {
        if(!HasStopLoss()) return 0;
        
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        if(point <= 0) return 0;
        
        if(IsBuy()) {
            return (openPrice - stopLoss) / point;
        } else {
            return (stopLoss - openPrice) / point;
        }
    }
    
    // Get distance to take profit in points
    double GetTakeProfitDistance() const {
        if(!HasTakeProfit()) return 0;
        
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        if(point <= 0) return 0;
        
        if(IsBuy()) {
            return (takeProfit - openPrice) / point;
        } else {
            return (openPrice - takeProfit) / point;
        }
    }
    
    // Get current price distance from open in points
    double GetCurrentDistance() const {
        double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
        if(point <= 0) return 0;
        
        if(IsBuy()) {
            return (currentPrice - openPrice) / point;
        } else {
            return (openPrice - currentPrice) / point;
        }
    }
};

//+------------------------------------------------------------------+
//| Position group structure (for basket/hedge positions)            |
//+------------------------------------------------------------------+
struct SPositionGroup {
    string          groupId;           // Unique group identifier
    string          symbol;            // Symbol for group
    double          netVolume;         // Net volume (positive = net long, negative = net short)
    double          avgOpenPrice;      // Average open price
    double          totalProfit;       // Total profit for group
    int             positionCount;     // Number of positions in group
    ulong           tickets[];         // Position tickets in group
    datetime        createdTime;       // Group creation time
    
    // Default constructor
    SPositionGroup() : 
        groupId(""),
        symbol(""),
        netVolume(0),
        avgOpenPrice(0),
        totalProfit(0),
        positionCount(0),
        createdTime(0)
    {
        ArrayResize(tickets, 0);
    }
    
    // Copy constructor
    SPositionGroup(const SPositionGroup &other) {
        groupId = other.groupId;
        symbol = other.symbol;
        netVolume = other.netVolume;
        avgOpenPrice = other.avgOpenPrice;
        totalProfit = other.totalProfit;
        positionCount = other.positionCount;
        createdTime = other.createdTime;
        
        int size = ArraySize(other.tickets);
        ArrayResize(tickets, size);
        for(int i = 0; i < size; i++) {
            tickets[i] = other.tickets[i];
        }
    }
    
    // Assignment operator
    void operator=(const SPositionGroup &other) {
        groupId = other.groupId;
        symbol = other.symbol;
        netVolume = other.netVolume;
        avgOpenPrice = other.avgOpenPrice;
        totalProfit = other.totalProfit;
        positionCount = other.positionCount;
        createdTime = other.createdTime;
        
        int size = ArraySize(other.tickets);
        ArrayResize(tickets, size);
        for(int i = 0; i < size; i++) {
            tickets[i] = other.tickets[i];
        }
    }
};

//+------------------------------------------------------------------+
//| Position statistics structure                                     |
//+------------------------------------------------------------------+
struct SPositionStats {
    int             totalPositions;    // Total positions managed
    int             openPositions;     // Currently open positions
    int             closedPositions;   // Closed positions
    int             winningPositions;  // Winning positions
    int             losingPositions;   // Losing positions
    
    double          totalProfit;       // Total profit from all positions
    double          totalLoss;         // Total loss from all positions
    double          netProfit;         // Net profit/loss
    double          largestWin;        // Largest winning position
    double          largestLoss;       // Largest losing position
    
    double          avgWin;            // Average win amount
    double          avgLoss;           // Average loss amount
    double          avgPositionTime;   // Average position time in hours
    double          winRate;           // Win rate percentage
    
    int             modifications;     // Total modifications made
    int             partialCloses;     // Partial closes performed
    
    datetime        lastUpdate;        // Last statistics update
    
    // Default constructor
    SPositionStats() {
        Reset();
    }
    
    void Reset() {
        totalPositions = 0;
        openPositions = 0;
        closedPositions = 0;
        winningPositions = 0;
        losingPositions = 0;
        totalProfit = 0;
        totalLoss = 0;
        netProfit = 0;
        largestWin = 0;
        largestLoss = 0;
        avgWin = 0;
        avgLoss = 0;
        avgPositionTime = 0;
        winRate = 0;
        modifications = 0;
        partialCloses = 0;
        lastUpdate = TimeCurrent();
    }
    
    // Copy constructor
    SPositionStats(const SPositionStats &other) {
        totalPositions = other.totalPositions;
        openPositions = other.openPositions;
        closedPositions = other.closedPositions;
        winningPositions = other.winningPositions;
        losingPositions = other.losingPositions;
        totalProfit = other.totalProfit;
        totalLoss = other.totalLoss;
        netProfit = other.netProfit;
        largestWin = other.largestWin;
        largestLoss = other.largestLoss;
        avgWin = other.avgWin;
        avgLoss = other.avgLoss;
        avgPositionTime = other.avgPositionTime;
        winRate = other.winRate;
        modifications = other.modifications;
        partialCloses = other.partialCloses;
        lastUpdate = other.lastUpdate;
    }
    
    // Assignment operator
    void operator=(const SPositionStats &other) {
        totalPositions = other.totalPositions;
        openPositions = other.openPositions;
        closedPositions = other.closedPositions;
        winningPositions = other.winningPositions;
        losingPositions = other.losingPositions;
        totalProfit = other.totalProfit;
        totalLoss = other.totalLoss;
        netProfit = other.netProfit;
        largestWin = other.largestWin;
        largestLoss = other.largestLoss;
        avgWin = other.avgWin;
        avgLoss = other.avgLoss;
        avgPositionTime = other.avgPositionTime;
        winRate = other.winRate;
        modifications = other.modifications;
        partialCloses = other.partialCloses;
        lastUpdate = other.lastUpdate;
    }
};

//+------------------------------------------------------------------+
//| CPositionManager - Main position management class                 |
//+------------------------------------------------------------------+
class CPositionManager {
private:
    // Core storage
    SPositionData   m_positions[];     // All positions (open and recently closed)
    SPositionGroup  m_positionGroups[]; // Position groups
    SPositionStats  m_stats;           // Position statistics
    
    // Configuration
    int             m_maxPositions;    // Maximum positions to track
    int             m_maxHistory;      // Maximum closed positions to keep
    bool            m_trackClosed;     // Track closed positions
    bool            m_enableGroups;    // Enable position grouping
    
    // State tracking
    bool            m_initialized;
    bool            m_autoUpdate;
    datetime        m_lastSyncTime;
    
    // Components
    CLogger*        m_logger;
    CDateTimeUtils* m_dateTimeUtils;
    CArrayUtils*    m_arrayUtils;
    CMathUtils*     m_mathUtils;
    CMarketData*    m_marketData;
    
    // Indexes for fast lookup
    ulong           m_ticketIndex[];   // Ticket to array index mapping
    ulong           m_magicIndex[];    // Magic to tickets mapping
    
public:
    //+------------------------------------------------------------------+
    //| Constructor/Destructor                                           |
    //+------------------------------------------------------------------+
    CPositionManager() :
        m_maxPositions(1000),
        m_maxHistory(500),
        m_trackClosed(true),
        m_enableGroups(true),
        m_initialized(false),
        m_autoUpdate(true),
        m_lastSyncTime(0),
        m_logger(NULL),
        m_dateTimeUtils(NULL),
        m_arrayUtils(NULL),
        m_mathUtils(NULL),
        m_marketData(NULL)
    {
        ArrayResize(m_positions, 0);
        ArrayResize(m_positionGroups, 0);
        ArrayResize(m_ticketIndex, 0);
        ArrayResize(m_magicIndex, 0);
        
        m_stats.Reset();
    }
    
    ~CPositionManager() {
        Deinitialize();
    }
    
    //+------------------------------------------------------------------+
    //| Initialization methods                                           |
    //+------------------------------------------------------------------+
    bool Initialize() {
        if(m_initialized) {
            LogInfo("Position Manager already initialized");
            return true;
        }
        
        // Initialize components
        m_logger = GlobalLogger;
        m_dateTimeUtils = GlobalDateTimeUtils;
        m_arrayUtils = GlobalArrayUtils;
        m_mathUtils = GlobalMathUtils;
        
        if(m_logger == NULL) {
            Print("ERROR: Logger not initialized");
            return false;
        }
        
        // Initialize market data for default symbol
        m_marketData = new CMarketData(_Symbol, PERIOD_M1);
        if(!m_marketData.Initialize()) {
            LogError("Failed to initialize MarketData");
            delete m_marketData;
            m_marketData = NULL;
        }
        
        // Load existing positions from terminal
        if(!LoadExistingPositions()) {
            LogError("Failed to load existing positions");
            return false;
        }
        
        m_initialized = true;
        LogInfo("Position Manager initialized successfully");
        LogInfo(StringFormat("Tracking %d positions, Max history: %d", 
                            m_stats.openPositions, m_maxHistory));
        
        return true;
    }
    
    void Deinitialize() {
        if(!m_initialized) return;
        
        LogInfo("Deinitializing Position Manager...");
        
        if(m_marketData != NULL) {
            m_marketData.Deinitialize();
            delete m_marketData;
            m_marketData = NULL;
        }
        
        ArrayFree(m_positions);
        ArrayFree(m_positionGroups);
        ArrayFree(m_ticketIndex);
        ArrayFree(m_magicIndex);
        
        m_initialized = false;
        LogInfo("Position Manager deinitialized");
    }
    
    //+------------------------------------------------------------------+
    //| Core position management methods                                 |
    //+------------------------------------------------------------------+
    bool AddPosition(ulong ticket, ulong magic = 0, string strategyName = "") {
        if(!m_initialized) {
            LogError("Cannot add position - not initialized");
            return false;
        }
        
        // Check if position already exists
        if(FindPositionIndex(ticket) >= 0) {
            LogWarn(StringFormat("Position already tracked: %I64u", ticket));
            return false;
        }
        
        // Get position data from terminal
        if(!PositionSelectByTicket(ticket)) {
            LogError(StringFormat("Cannot select position: %I64u", ticket));
            return false;
        }
        
        // Create new position entry
        int index = ArraySize(m_positions);
        if(index >= m_maxPositions) {
            // Remove oldest closed position if we're at limit
            if(!RemoveOldestClosedPosition()) {
                LogError("Cannot add position - maximum limit reached");
                return false;
            }
            index = ArraySize(m_positions);
        }
        
        ArrayResize(m_positions, index + 1);
        SPositionData pos;
        
        // Populate position data
        pos.ticket = ticket;
        pos.magic = magic;
        pos.symbol = PositionGetString(POSITION_SYMBOL);
        pos.type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
        pos.volume = PositionGetDouble(POSITION_VOLUME);
        pos.openTime = (datetime)PositionGetInteger(POSITION_TIME);
        pos.openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        pos.stopLoss = PositionGetDouble(POSITION_SL);
        pos.takeProfit = PositionGetDouble(POSITION_TP);
        pos.comment = PositionGetString(POSITION_COMMENT);
        pos.strategyName = strategyName;
        
        m_positions[index] = pos;
        
        // Update current state
        UpdatePosition(index);
        
        // Update ticket index
        UpdateTicketIndex(ticket, index);
        
        // Update statistics
        m_stats.totalPositions++;
        m_stats.openPositions++;
        
        // Update groups if enabled
        if(m_enableGroups) {
            UpdatePositionGroups(pos);
        }
        
        LogInfo(StringFormat("Position added: %I64u (%s %.2f %s)", 
                            ticket, pos.symbol, pos.volume, 
                            pos.IsBuy() ? "BUY" : "SELL"));
        
        return true;
    }
    
    bool UpdatePosition(ulong ticket) {
        int index = FindPositionIndex(ticket);
        if(index < 0) {
            // Try to add it if not found
            return AddPosition(ticket);
        }
        
        return UpdatePosition(index);
    }
    
    bool ClosePosition(ulong ticket, double volume = 0, string comment = "") {
        int index = FindPositionIndex(ticket);
        if(index < 0) {
            LogError(StringFormat("Cannot close - position not found: %I64u", ticket));
            return false;
        }
        
        SPositionData pos = m_positions[index];
        
        // Check if position is already closed
        if(pos.status == POSITION_STATUS_CLOSED) {
            LogWarn(StringFormat("Position already closed: %I64u", ticket));
            return true;
        }
        
        // Update position status
        pos.status = POSITION_STATUS_PENDING_CLOSE;
        pos.comment = comment;
        
        m_positions[index] = pos;
        
        LogInfo(StringFormat("Closing position: %I64u (%s %.2f)", 
                            ticket, pos.symbol, volume > 0 ? volume : pos.volume));
        
        // The actual closing would be handled by the execution engine
        // This method just updates our tracking
        
        return true;
    }
    
    bool ModifyPosition(ulong ticket, double sl = 0, double tp = 0, string comment = "") {
        int index = FindPositionIndex(ticket);
        if(index < 0) {
            LogError(StringFormat("Cannot modify - position not found: %I64u", ticket));
            return false;
        }
        
        SPositionData pos = m_positions[index];
        
        // Check if values are different
        bool slChanged = (sl > 0 && MathAbs(pos.stopLoss - sl) > 0.00001);
        bool tpChanged = (tp > 0 && MathAbs(pos.takeProfit - tp) > 0.00001);
        bool commentChanged = (comment != "" && pos.comment != comment);
        
        if(!slChanged && !tpChanged && !commentChanged) {
            LogDebug(StringFormat("No changes for position: %I64u", ticket));
            return true;
        }
        
        // Update position data
        if(slChanged) pos.stopLoss = sl;
        if(tpChanged) pos.takeProfit = tp;
        if(commentChanged) pos.comment = comment;
        
        pos.status = POSITION_STATUS_MODIFIED;
        pos.modifications++;
        pos.lastUpdate = TimeCurrent();
        
        m_positions[index] = pos;
        
        m_stats.modifications++;
        
        LogInfo(StringFormat("Position modified: %I64u (SL: %.5f, TP: %.5f)", 
                            ticket, sl, tp));
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Position query methods                                           |
    //+------------------------------------------------------------------+
    SPositionData GetPosition(ulong ticket) {
        int index = FindPositionIndex(ticket);
        if(index < 0) {
            SPositionData empty;
            return empty;
        }
        return m_positions[index];
    }
    
    bool GetPositionsByMagic(ulong magic, SPositionData &positions[]) {
        ArrayResize(positions, 0);
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].magic == magic && m_positions[i].status == POSITION_STATUS_OPEN) {
                int size = ArraySize(positions);
                ArrayResize(positions, size + 1);
                positions[size] = m_positions[i];
            }
        }
        
        return ArraySize(positions) > 0;
    }
    
    bool GetPositionsBySymbol(string symbol, SPositionData &positions[]) {
        ArrayResize(positions, 0);
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].symbol == symbol && m_positions[i].status == POSITION_STATUS_OPEN) {
                int size = ArraySize(positions);
                ArrayResize(positions, size + 1);
                positions[size] = m_positions[i];
            }
        }
        
        return ArraySize(positions) > 0;
    }
    
    bool GetPositionsByStrategy(string strategyName, SPositionData &positions[]) {
        ArrayResize(positions, 0);
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].strategyName == strategyName && m_positions[i].status == POSITION_STATUS_OPEN) {
                int size = ArraySize(positions);
                ArrayResize(positions, size + 1);
                positions[size] = m_positions[i];
            }
        }
        
        return ArraySize(positions) > 0;
    }
    
    int GetOpenPositionCount() const {
        return m_stats.openPositions;
    }
    
    int GetOpenPositionCountByMagic(ulong magic) {
        int count = 0;
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].magic == magic && m_positions[i].status == POSITION_STATUS_OPEN) {
                count++;
            }
        }
        return count;
    }
    
    int GetOpenPositionCountBySymbol(string symbol) {
        int count = 0;
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].symbol == symbol && m_positions[i].status == POSITION_STATUS_OPEN) {
                count++;
            }
        }
        return count;
    }
    
    double GetTotalProfitByMagic(ulong magic) {
        double total = 0;
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].magic == magic && m_positions[i].status == POSITION_STATUS_OPEN) {
                total += m_positions[i].profit;
            }
        }
        return total;
    }
    
    double GetTotalProfitBySymbol(string symbol) {
        double total = 0;
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].symbol == symbol && m_positions[i].status == POSITION_STATUS_OPEN) {
                total += m_positions[i].profit;
            }
        }
        return total;
    }
    
    //+------------------------------------------------------------------+
    //| Position analytics methods                                       |
    //+------------------------------------------------------------------+
    double GetTotalExposure(string symbol = "") {
        double exposure = 0;
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                if(symbol == "" || m_positions[i].symbol == symbol) {
                    // Calculate exposure as volume * price
                    double pointValue = SymbolInfoDouble(m_positions[i].symbol, SYMBOL_TRADE_TICK_VALUE);
                    double point = SymbolInfoDouble(m_positions[i].symbol, SYMBOL_POINT);
                    
                    if(point > 0 && pointValue > 0) {
                        exposure += m_positions[i].volume * pointValue / point;
                    }
                }
            }
        }
        
        return exposure;
    }
    
    double GetNetExposure(string symbol) {
        double longExposure = 0;
        double shortExposure = 0;
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN && m_positions[i].symbol == symbol) {
                if(m_positions[i].IsBuy()) {
                    longExposure += m_positions[i].volume;
                } else {
                    shortExposure += m_positions[i].volume;
                }
            }
        }
        
        return longExposure - shortExposure;
    }
    
    double GetMarginUsed(string symbol = "") {
        double margin = 0;
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                if(symbol == "" || m_positions[i].symbol == symbol) {
                    margin += CalculatePositionMargin(m_positions[i]);
                }
            }
        }
        
        return margin;
    }
    
    double GetRiskExposure() {
        double totalRisk = 0;
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                totalRisk += m_positions[i].riskAmount;
            }
        }
        
        return totalRisk;
    }
    
    //+------------------------------------------------------------------+
    //| Group management methods                                         |
    //+------------------------------------------------------------------+
    bool CreatePositionGroup(string groupId, string symbol) {
        if(!m_enableGroups) return false;
        
        // Check if group already exists
        int groupIndex = FindGroupIndex(groupId);
        if(groupIndex >= 0) {
            LogWarn("Group already exists: " + groupId);
            return false;
        }
        
        // Create new group
        int index = ArraySize(m_positionGroups);
        ArrayResize(m_positionGroups, index + 1);
        
        SPositionGroup group;
        group.groupId = groupId;
        group.symbol = symbol;
        group.createdTime = TimeCurrent();
        
        m_positionGroups[index] = group;
        
        LogInfo("Position group created: " + groupId);
        return true;
    }
    
    bool AddPositionToGroup(ulong ticket, string groupId) {
        if(!m_enableGroups) return false;
        
        int groupIndex = FindGroupIndex(groupId);
        if(groupIndex < 0) {
            LogError("Group not found: " + groupId);
            return false;
        }
        
        int posIndex = FindPositionIndex(ticket);
        if(posIndex < 0) {
            LogError(StringFormat("Position not found: %I64u", ticket));
            return false;
        }
        
        SPositionGroup group = m_positionGroups[groupIndex];
        
        // Check if position already in group
        for(int i = 0; i < group.positionCount; i++) {
            if(group.tickets[i] == ticket) {
                LogWarn("Position already in group");
                return false;
            }
        }
        
        // Add to group
        int newSize = group.positionCount + 1;
        ArrayResize(group.tickets, newSize);
        group.tickets[group.positionCount] = ticket;
        group.positionCount++;
        
        m_positionGroups[groupIndex] = group;
        
        // Update group metrics
        UpdateGroupMetrics(groupIndex);
        
        LogInfo(StringFormat("Position %I64u added to group: %s", ticket, groupId));
        return true;
    }
    
    bool CloseGroup(string groupId, string comment = "") {
        if(!m_enableGroups) return false;
        
        int groupIndex = FindGroupIndex(groupId);
        if(groupIndex < 0) {
            LogError("Group not found: " + groupId);
            return false;
        }
        
        SPositionGroup group = m_positionGroups[groupIndex];
        
        // Close all positions in group
        for(int i = 0; i < group.positionCount; i++) {
            ClosePosition(group.tickets[i], 0, comment);
        }
        
        LogInfo("Closing position group: " + groupId);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Update and maintenance methods                                   |
    //+------------------------------------------------------------------+
    void UpdateAllPositions() {
        if(!m_initialized || !m_autoUpdate) return;
        
        // Update each open position
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                UpdatePosition(i);
            }
        }
        
        // Update statistics
        UpdateStatistics();
        
        // Update groups if enabled
        if(m_enableGroups) {
            UpdateAllGroups();
        }
        
        m_lastSyncTime = TimeCurrent();
    }
    
    void SyncWithTerminal() {
        if(!m_initialized) return;
        
        // Check for new positions
        int totalPositions = PositionsTotal();
        for(int i = 0; i < totalPositions; i++) {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0) {
                int index = FindPositionIndex(ticket);
                if(index < 0) {
                    // New position found, add it
                    AddPosition(ticket);
                }
            }
        }
        
        // Check for closed positions
        for(int i = ArraySize(m_positions) - 1; i >= 0; i--) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                if(!PositionSelectByTicket(m_positions[i].ticket)) {
                    // Position no longer exists, mark as closed
                    MarkPositionAsClosed(i);
                }
            }
        }
        
        LogDebug("Synchronized with terminal, open positions: " + IntegerToString(m_stats.openPositions));
    }
    
    //+------------------------------------------------------------------+
    //| Configuration methods                                            |
    //+------------------------------------------------------------------+
    void SetMaxPositions(int maxPositions) {
        if(maxPositions > 0 && maxPositions != m_maxPositions) {
            m_maxPositions = maxPositions;
            LogInfo("Max positions set to: " + IntegerToString(maxPositions));
        }
    }
    
    void SetMaxHistory(int maxHistory) {
        if(maxHistory > 0 && maxHistory != m_maxHistory) {
            m_maxHistory = maxHistory;
            LogInfo("Max history set to: " + IntegerToString(maxHistory));
        }
    }
    
    void SetTrackClosed(bool trackClosed) {
        if(m_trackClosed != trackClosed) {
            m_trackClosed = trackClosed;
            LogInfo("Closed position tracking " + (trackClosed ? "enabled" : "disabled"));
        }
    }
    
    void SetEnableGroups(bool enableGroups) {
        if(m_enableGroups != enableGroups) {
            m_enableGroups = enableGroups;
            LogInfo("Position grouping " + (enableGroups ? "enabled" : "disabled"));
        }
    }
    
    void SetAutoUpdate(bool autoUpdate) {
        if(m_autoUpdate != autoUpdate) {
            m_autoUpdate = autoUpdate;
            LogInfo("Auto-update " + (autoUpdate ? "enabled" : "disabled"));
        }
    }
    
    //+------------------------------------------------------------------+
    //| Information and reporting methods                                |
    //+------------------------------------------------------------------+
    SPositionStats GetStatistics() const {
        return m_stats;
    }
    
    void PrintStatistics() const {
        if(m_logger == NULL) return;
        
        string stats = StringFormat(
            "Position Statistics:\n" +
            "Total Positions: %d | Open: %d | Closed: %d\n" +
            "Winning: %d | Losing: %d | Win Rate: %.2f%%\n" +
            "Net Profit: %.2f | Total Profit: %.2f | Total Loss: %.2f\n" +
            "Avg Win: %.2f | Avg Loss: %.2f | Largest Win: %.2f | Largest Loss: %.2f\n" +
            "Modifications: %d | Partial Closes: %d | Avg Time: %.2f hours",
            m_stats.totalPositions,
            m_stats.openPositions,
            m_stats.closedPositions,
            m_stats.winningPositions,
            m_stats.losingPositions,
            m_stats.winRate,
            m_stats.netProfit,
            m_stats.totalProfit,
            m_stats.totalLoss,
            m_stats.avgWin,
            m_stats.avgLoss,
            m_stats.largestWin,
            m_stats.largestLoss,
            m_stats.modifications,
            m_stats.partialCloses,
            m_stats.avgPositionTime
        );
        
        m_logger.Info(stats, "PositionManager");
    }
    
    void PrintOpenPositions() const {
        if(m_logger == NULL) return;
        
        m_logger.Info("=== OPEN POSITIONS ===", "PositionManager");
        
        int count = 0;
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_OPEN) {
                string posInfo = StringFormat(
                    "#%d: %I64u %s %.2f %s @ %.5f P/L: %.2f (SL: %.5f TP: %.5f) %s",
                    ++count,
                    m_positions[i].ticket,
                    m_positions[i].symbol,
                    m_positions[i].volume,
                    m_positions[i].IsBuy() ? "BUY" : "SELL",
                    m_positions[i].openPrice,
                    m_positions[i].profit,
                    m_positions[i].stopLoss,
                    m_positions[i].takeProfit,
                    m_positions[i].strategyName
                );
                m_logger.Info(posInfo, "PositionManager");
            }
        }
        
        if(count == 0) {
            m_logger.Info("No open positions", "PositionManager");
        }
    }
    
private:
    //+------------------------------------------------------------------+
    //| Internal helper methods                                          |
    //+------------------------------------------------------------------+
    int FindPositionIndex(ulong ticket) {
        // Check index first
        for(int i = 0; i < ArraySize(m_ticketIndex); i += 2) {
            if(m_ticketIndex[i] == ticket) {
                return (int)m_ticketIndex[i + 1];
            }
        }
        
        // Linear search if not in index
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].ticket == ticket) {
                // Add to index for future lookups
                UpdateTicketIndex(ticket, i);
                return i;
            }
        }
        
        return -1;
    }
    
    void UpdateTicketIndex(ulong ticket, int index) {
        // Check if already in index
        for(int i = 0; i < ArraySize(m_ticketIndex); i += 2) {
            if(m_ticketIndex[i] == ticket) {
                m_ticketIndex[i + 1] = (ulong)index;
                return;
            }
        }
        
        // Add to index
        int newSize = ArraySize(m_ticketIndex) + 2;
        ArrayResize(m_ticketIndex, newSize);
        m_ticketIndex[newSize - 2] = ticket;
        m_ticketIndex[newSize - 1] = (ulong)index;
    }
    
    int FindGroupIndex(string groupId) {
        for(int i = 0; i < ArraySize(m_positionGroups); i++) {
            if(m_positionGroups[i].groupId == groupId) {
                return i;
            }
        }
        return -1;
    }
    
    bool UpdatePosition(int index) {
        if(index < 0 || index >= ArraySize(m_positions)) {
            return false;
        }
        
        SPositionData pos = m_positions[index];
        
        // Get current position data from terminal
        if(!PositionSelectByTicket(pos.ticket)) {
            // Position might be closed
            if(pos.status == POSITION_STATUS_OPEN) {
                MarkPositionAsClosed(index);
            }
            return false;
        }
        
        // Update current state
        pos.currentPrice = (pos.IsBuy() ? SymbolInfoDouble(pos.symbol, SYMBOL_BID) : 
                                         SymbolInfoDouble(pos.symbol, SYMBOL_ASK));
        pos.profit = PositionGetDouble(POSITION_PROFIT);
        pos.swap = PositionGetDouble(POSITION_SWAP);
        
        // Update stop loss and take profit (might have been modified)
        pos.stopLoss = PositionGetDouble(POSITION_SL);
        pos.takeProfit = PositionGetDouble(POSITION_TP);
        
        // Update risk metrics
        UpdatePositionRiskMetrics(pos);
        
        // Update profit excursion
        if(pos.profit > pos.peakProfit) {
            pos.peakProfit = pos.profit;
        }
        if(pos.profit < pos.valleyProfit) {
            pos.valleyProfit = pos.profit;
        }
        
        pos.currentDrawdown = pos.peakProfit - pos.profit;
        pos.maxFavorable = MathMax(pos.maxFavorable, pos.profit);
        pos.maxAdverse = MathMin(pos.maxAdverse, pos.profit);
        
        pos.lastUpdate = TimeCurrent();
        pos.status = POSITION_STATUS_OPEN;
        
        m_positions[index] = pos;
        
        return true;
    }
    
    void UpdatePositionRiskMetrics(SPositionData &pos) {
        if(pos.HasStopLoss()) {
            // Calculate risk amount
            double pointValue = SymbolInfoDouble(pos.symbol, SYMBOL_TRADE_TICK_VALUE);
            double point = SymbolInfoDouble(pos.symbol, SYMBOL_POINT);
            double stopDistance = (pos.IsBuy()) ? 
                (pos.openPrice - pos.stopLoss) / point : 
                (pos.stopLoss - pos.openPrice) / point;
            
            if(point > 0 && pointValue > 0) {
                pos.riskAmount = pos.volume * stopDistance * pointValue;
                
                // Calculate risk percentage
                double balance = AccountInfoDouble(ACCOUNT_BALANCE);
                if(balance > 0) {
                    pos.riskPercent = (pos.riskAmount / balance) * 100;
                }
            }
        }
    }
    
    void MarkPositionAsClosed(int index) {
        SPositionData pos = m_positions[index];
        
        // Update final profit if not already set
        if(pos.profit == 0) {
            // Try to get profit from position history or last update
            pos.profit = pos.peakProfit; // Use last known profit
        }
        
        pos.status = POSITION_STATUS_CLOSED;
        pos.lastUpdate = TimeCurrent();
        
        m_positions[index] = pos;
        
        // Update statistics
        m_stats.openPositions--;
        m_stats.closedPositions++;
        
        if(pos.profit > 0) {
            m_stats.winningPositions++;
            m_stats.totalProfit += pos.profit;
            m_stats.largestWin = MathMax(m_stats.largestWin, pos.profit);
        } else {
            m_stats.losingPositions++;
            m_stats.totalLoss += MathAbs(pos.profit);
            m_stats.largestLoss = MathMin(m_stats.largestLoss, pos.profit);
        }
        
        m_stats.netProfit += pos.profit;
        
        // Calculate position age
        double positionHours = (TimeCurrent() - pos.openTime) / 3600.0;
        m_stats.avgPositionTime = (m_stats.avgPositionTime * (m_stats.closedPositions - 1) + positionHours) / m_stats.closedPositions;
        
        // Update derived statistics
        UpdateDerivedStatistics();
        
        // Remove from groups
        RemovePositionFromGroups(pos.ticket);
        
        LogInfo(StringFormat("Position closed: %I64u (%s) P/L: %.2f", 
                            pos.ticket, pos.symbol, pos.profit));
    }
    
    void UpdateDerivedStatistics() {
        if(m_stats.winningPositions > 0) {
            m_stats.avgWin = m_stats.totalProfit / m_stats.winningPositions;
        }
        
        if(m_stats.losingPositions > 0) {
            m_stats.avgLoss = m_stats.totalLoss / m_stats.losingPositions;
        }
        
        if(m_stats.closedPositions > 0) {
            m_stats.winRate = (double)m_stats.winningPositions / m_stats.closedPositions * 100;
        }
    }
    
    bool LoadExistingPositions() {
        int totalPositions = PositionsTotal();
        
        LogInfo("Loading existing positions from terminal: " + IntegerToString(totalPositions));
        
        for(int i = 0; i < totalPositions; i++) {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0) {
                if(!AddPosition(ticket)) {
                    LogWarn(StringFormat("Failed to load position: %I64u", ticket));
                }
            }
        }
        
        return true;
    }
    
    bool RemoveOldestClosedPosition() {
        if(!m_trackClosed) return true;
        
        // Find oldest closed position
        int oldestIndex = -1;
        datetime oldestTime = INT_MAX;
        
        for(int i = 0; i < ArraySize(m_positions); i++) {
            if(m_positions[i].status == POSITION_STATUS_CLOSED) {
                if(m_positions[i].lastUpdate < oldestTime) {
                    oldestTime = m_positions[i].lastUpdate;
                    oldestIndex = i;
                }
            }
        }
        
        if(oldestIndex < 0) {
            // No closed positions to remove
            return false;
        }
        
        // Remove from array
        ulong ticket = m_positions[oldestIndex].ticket;
        
        for(int i = oldestIndex; i < ArraySize(m_positions) - 1; i++) {
            m_positions[i] = m_positions[i + 1];
            // Update index for moved position
            UpdateTicketIndex(m_positions[i].ticket, i);
        }
        ArrayResize(m_positions, ArraySize(m_positions) - 1);
        
        // Remove from ticket index
        RemoveTicketFromIndex(ticket);
        
        // Remove from groups
        RemovePositionFromGroups(ticket);
        
        LogDebug("Removed oldest closed position: " + IntegerToString(ticket));
        return true;
    }
    
    void RemoveTicketFromIndex(ulong ticket) {
        for(int i = 0; i < ArraySize(m_ticketIndex); i += 2) {
            if(m_ticketIndex[i] == ticket) {
                // Shift remaining entries
                for(int j = i; j < ArraySize(m_ticketIndex) - 2; j += 2) {
                    m_ticketIndex[j] = m_ticketIndex[j + 2];
                    m_ticketIndex[j + 1] = m_ticketIndex[j + 3];
                }
                ArrayResize(m_ticketIndex, ArraySize(m_ticketIndex) - 2);
                break;
            }
        }
    }
    
    void RemovePositionFromGroups(ulong ticket) {
        if(!m_enableGroups) return;
        
        for(int g = 0; g < ArraySize(m_positionGroups); g++) {
            SPositionGroup group = m_positionGroups[g];
            
            for(int i = 0; i < group.positionCount; i++) {
                if(group.tickets[i] == ticket) {
                    // Remove from group
                    for(int j = i; j < group.positionCount - 1; j++) {
                        group.tickets[j] = group.tickets[j + 1];
                    }
                    group.positionCount--;
                    ArrayResize(group.tickets, group.positionCount);
                    
                    m_positionGroups[g] = group;
                    
                    // Update group metrics
                    UpdateGroupMetrics(g);
                    
                    LogDebug(StringFormat("Removed position %I64u from group %s", ticket, group.groupId));
                    break;
                }
            }
        }
    }
    
    void UpdatePositionGroups(SPositionData &pos) {
        // This would be called when adding or updating positions
        // Groups would be updated based on strategy logic
        // For now, it's a placeholder for future implementation
    }
    
    void UpdateGroupMetrics(int groupIndex) {
        if(groupIndex < 0 || groupIndex >= ArraySize(m_positionGroups)) {
            return;
        }
        
        SPositionGroup group = m_positionGroups[groupIndex];
        
        // Reset metrics
        group.netVolume = 0;
        group.avgOpenPrice = 0;
        group.totalProfit = 0;
        
        double totalVolume = 0;
        double priceVolumeSum = 0;
        
        for(int i = 0; i < group.positionCount; i++) {
            int posIndex = FindPositionIndex(group.tickets[i]);
            if(posIndex >= 0) {
                SPositionData pos = m_positions[posIndex];
                
                if(pos.IsBuy()) {
                    group.netVolume += pos.volume;
                } else {
                    group.netVolume -= pos.volume;
                }
                
                totalVolume += pos.volume;
                priceVolumeSum += pos.openPrice * pos.volume;
                group.totalProfit += pos.profit;
            }
        }
        
        if(totalVolume > 0) {
            group.avgOpenPrice = priceVolumeSum / totalVolume;
        }
        
        m_positionGroups[groupIndex] = group;
    }
    
    void UpdateAllGroups() {
        for(int i = 0; i < ArraySize(m_positionGroups); i++) {
            UpdateGroupMetrics(i);
        }
    }
    
    void UpdateStatistics() {
        m_stats.lastUpdate = TimeCurrent();
        // Additional statistical updates could be added here
    }
    
   double CalculatePositionMargin(SPositionData &pos) {
       // Use OrderCalcMargin for accurate margin calculation
       double margin = 0;
       ENUM_ORDER_TYPE order_type = (pos.IsBuy()) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
       
       // Try to calculate margin using OrderCalcMargin first
       if(OrderCalcMargin(order_type, pos.symbol, pos.volume, pos.openPrice, margin)) {
           return margin;
       }
       
       // Fallback to simplified calculation if OrderCalcMargin fails
       int leverage = (int)AccountInfoInteger(ACCOUNT_LEVERAGE);
       double contractSize = SymbolInfoDouble(pos.symbol, SYMBOL_TRADE_CONTRACT_SIZE);
       
       if(leverage > 0 && contractSize > 0) {
           margin = (pos.volume * contractSize * pos.openPrice) / leverage;
       }
       
       return margin;
   }
       
    //+------------------------------------------------------------------+
    //| Logging methods                                                  |
    //+------------------------------------------------------------------+
    void LogError(string message) {
        if(m_logger != NULL) {
            m_logger.Error(message, "PositionManager");
        } else {
            Print("ERROR [PositionManager]: " + message);
        }
    }
    
    void LogWarn(string message) {
        if(m_logger != NULL) {
            m_logger.Warn(message, "PositionManager");
        }
    }
    
    void LogInfo(string message) {
        if(m_logger != NULL) {
            m_logger.Info(message, "PositionManager");
        } else {
            Print("INFO [PositionManager]: " + message);
        }
    }
    
    void LogDebug(string message) {
        if(m_logger != NULL) {
            m_logger.Debug(message, "PositionManager");
        }
    }
};

#endif