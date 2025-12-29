// Indicators/IndicatorCache.mqh
//+------------------------------------------------------------------+
//| Description: LRU Memory Cache for Indicator System              |
//+------------------------------------------------------------------+
#ifndef INDICATORCACHE_MQH
#define INDICATORCACHE_MQH

#include "IndicatorTypes.mqh"
#include "IndicatorKey.mqh"
#include "IndicatorUtils.mqh"

//+------------------------------------------------------------------+
//| LRU Cache Node Structure                                         |
//+------------------------------------------------------------------+
struct CacheNode
{
    string      key;            // Cache key
    double      value;          // Indicator value
    datetime    timestamp;      // When value was stored
    int         accessCount;    // How many times accessed
    CacheNode*  prev;           // Previous node in LRU list
    CacheNode*  next;           // Next node in LRU list
    
    CacheNode()
    {
        key = "";
        value = 0.0;
        timestamp = 0;
        accessCount = 0;
        prev = NULL;
        next = NULL;
    }
};

//+------------------------------------------------------------------+
//| LRU Memory Cache Class                                           |
//+------------------------------------------------------------------+
class CIndicatorCache
{
private:
    // Cache storage
    CacheNode*          m_head;                 // Most recently used
    CacheNode*          m_tail;                 // Least recently used
    int                 m_size;                 // Current cache size
    int                 m_maxSize;              // Maximum cache size
    int                 m_ttlSeconds;           // Time-to-live in seconds
    ulong               m_hits;                 // Cache hits counter
    ulong               m_misses;               // Cache misses counter
    
    // Hash map for O(1) lookups (simulated with array for MQL5)
    struct HashEntry
    {
        string key;
        CacheNode* node;
    };
    HashEntry           m_hashMap[1000];        // Simple hash table
    int                 m_hashSize;
    
    // Statistics
    PerformanceStats    m_stats;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor                                                      |
    //+------------------------------------------------------------------+
    CIndicatorCache(int maxSize = MAX_MEMORY_CACHE_ENTRIES, int ttlSeconds = MEMORY_CACHE_TTL_SECONDS)
    {
        m_head = NULL;
        m_tail = NULL;
        m_size = 0;
        m_maxSize = maxSize;
        m_ttlSeconds = ttlSeconds;
        m_hits = 0;
        m_misses = 0;
        m_hashSize = 0;
        
        // Initialize hash map
        ArrayInitialize(m_hashMap, NULL);
        
        Print("IndicatorCache initialized. Max size: ", m_maxSize, 
              ", TTL: ", m_ttlSeconds, " seconds");
    }
    
    //+------------------------------------------------------------------+
    //| Destructor                                                       |
    //+------------------------------------------------------------------+
    ~CIndicatorCache()
    {
        Clear();
        Print("IndicatorCache destroyed. Final stats - Hits: ", m_hits, 
              ", Misses: ", m_misses, ", Hit rate: ", GetHitRate(), "%");
    }
    
    //+------------------------------------------------------------------+
    //| Get value from cache                                             |
    //+------------------------------------------------------------------+
    bool Get(string key, double &value)
    {
        // Start timing for performance stats
        ulong startTime = GetMicrosecondCount();
        
        // Find node in hash map
        CacheNode* node = FindInHashMap(key);
        
        if(node == NULL)
        {
            // Cache miss
            m_misses++;
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        // Check if entry is expired
        if(IsEntryExpired(node))
        {
            // Remove expired entry
            RemoveNode(node);
            m_misses++;
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        // Cache hit - update access info
        node->accessCount++;
        node->timestamp = TimeCurrent();
        
        // Move to front (most recently used)
        MoveToFront(node);
        
        value = node->value;
        m_hits++;
        
        UpdateStats(true, GetMicrosecondCount() - startTime);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Set value in cache                                               |
    //+------------------------------------------------------------------+
    void Set(string key, double value)
    {
        // Start timing
        ulong startTime = GetMicrosecondCount();
        
        // Check if key already exists
        CacheNode* node = FindInHashMap(key);
        
        if(node != NULL)
        {
            // Update existing entry
            node->value = value;
            node->timestamp = TimeCurrent();
            node->accessCount++;
            MoveToFront(node);
            
            UpdateStats(false, GetMicrosecondCount() - startTime); // Not a hit
            return;
        }
        
        // Create new node
        node = new CacheNode();
        node->key = key;
        node->value = value;
        node->timestamp = TimeCurrent();
        node->accessCount = 1;
        
        // Add to hash map
        AddToHashMap(key, node);
        
        // Add to front of LRU list
        AddToFront(node);
        
        // Check if cache is full
        if(m_size > m_maxSize)
        {
            // Remove least recently used entry
            RemoveLRU();
        }
        
        UpdateStats(false, GetMicrosecondCount() - startTime);
    }
    
    //+------------------------------------------------------------------+
    //| Check if key exists in cache (without updating access)          |
    //+------------------------------------------------------------------+
    bool Has(string key)
    {
        CacheNode* node = FindInHashMap(key);
        
        if(node == NULL)
            return false;
            
        // Check if expired
        return !IsEntryExpired(node);
    }
    
    //+------------------------------------------------------------------+
    //| Remove entry from cache                                          |
    //+------------------------------------------------------------------+
    bool Remove(string key)
    {
        CacheNode* node = FindInHashMap(key);
        
        if(node == NULL)
            return false;
            
        RemoveNode(node);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Clear entire cache                                               |
    //+------------------------------------------------------------------+
    void Clear()
    {
        // Clear hash map
        for(int i = 0; i < m_hashSize; i++)
        {
            if(m_hashMap[i].node != NULL)
            {
                delete m_hashMap[i].node;
                m_hashMap[i].node = NULL;
            }
        }
        m_hashSize = 0;
        
        // Clear linked list
        CacheNode* current = m_head;
        while(current != NULL)
        {
            CacheNode* next = current->next;
            delete current;
            current = next;
        }
        
        m_head = NULL;
        m_tail = NULL;
        m_size = 0;
        
        Print("Cache cleared");
    }
    
    //+------------------------------------------------------------------+
    //| Cleanup expired entries                                          |
    //+------------------------------------------------------------------+
    int CleanupExpired()
    {
        int removed = 0;
        CacheNode* current = m_head;
        
        while(current != NULL)
        {
            CacheNode* next = current->next;
            
            if(IsEntryExpired(current))
            {
                RemoveNode(current);
                removed++;
            }
            
            current = next;
        }
        
        if(removed > 0)
            Print("Cleaned up ", removed, " expired cache entries");
            
        return removed;
    }
    
    //+------------------------------------------------------------------+
    //| Get cache statistics                                             |
    //+------------------------------------------------------------------+
    void GetStats(int &hits, int &misses, double &hitRate, int &size, int &maxSize)
    {
        hits = (int)m_hits;
        misses = (int)m_misses;
        hitRate = GetHitRate();
        size = m_size;
        maxSize = m_maxSize;
    }
    
    //+------------------------------------------------------------------+
    //| Get performance statistics                                       |
    //+------------------------------------------------------------------+
    PerformanceStats GetPerformanceStats()
    {
        return m_stats;
    }
    
    //+------------------------------------------------------------------+
    //| Print cache contents (for debugging)                             |
    //+------------------------------------------------------------------+
    void PrintCacheContents(bool detailed = false)
    {
        Print("=== Cache Contents (", m_size, "/", m_maxSize, " entries) ===");
        Print("Hits: ", m_hits, ", Misses: ", m_misses, ", Hit rate: ", GetHitRate(), "%");
        
        if(!detailed)
        {
            Print("Keys: ", GetKeysAsString());
            return;
        }
        
        // Detailed print
        CacheNode* current = m_head;
        int count = 0;
        
        while(current != NULL && count < 20) // Limit output
        {
            string age = CIndicatorUtils::FormatPercent(
                (double)(TimeCurrent() - current->timestamp) / m_ttlSeconds);
            
            Print(count + 1, ". ", current->key, 
                  " = ", DoubleToString(current->value, 5),
                  " (Age: ", age, ", Accesses: ", current->accessCount, ")");
            
            current = current->next;
            count++;
        }
        
        if(m_size > 20)
            Print("... and ", m_size - 20, " more entries");
            
        Print("=== End Cache Contents ===");
    }
    
    //+------------------------------------------------------------------+
    //| Get all cache keys as comma-separated string                     |
    //+------------------------------------------------------------------+
    string GetKeysAsString()
    {
        string keys = "";
        CacheNode* current = m_head;
        int count = 0;
        
        while(current != NULL && count < 10)
        {
            if(keys != "") keys += ", ";
            keys += current->key;
            
            current = current->next;
            count++;
        }
        
        if(m_size > 10)
            keys += ", ...";
            
        return keys;
    }
    
    //+------------------------------------------------------------------+
    //| Get cache size                                                   |
    //+------------------------------------------------------------------+
    int GetSize()
    {
        return m_size;
    }
    
    //+------------------------------------------------------------------+
    //| Get maximum cache size                                           |
    //+------------------------------------------------------------------+
    int GetMaxSize()
    {
        return m_maxSize;
    }
    
    //+------------------------------------------------------------------+
    //| Set maximum cache size                                           |
    //+------------------------------------------------------------------+
    void SetMaxSize(int maxSize)
    {
        if(maxSize < 10) maxSize = 10;
        if(maxSize > 1000) maxSize = 1000;
        
        m_maxSize = maxSize;
        
        // Trim cache if necessary
        while(m_size > m_maxSize)
        {
            RemoveLRU();
        }
    }
    
    //+------------------------------------------------------------------+
    //| Set cache TTL (Time-To-Live)                                     |
    //+------------------------------------------------------------------+
    void SetTTL(int ttlSeconds)
    {
        if(ttlSeconds < 1) ttlSeconds = 1;
        if(ttlSeconds > 3600) ttlSeconds = 3600;
        
        m_ttlSeconds = ttlSeconds;
    }
    
    //+------------------------------------------------------------------+
    //| Test cache functionality                                         |
    //+------------------------------------------------------------------+
    static void TestCache()
    {
        Print("=== Testing Memory Cache ===");
        
        CIndicatorCache cache(5, 10); // Small cache for testing
        
        // Test Set and Get
        cache.Set("TEST_KEY_1", 1.23456);
        cache.Set("TEST_KEY_2", 2.34567);
        cache.Set("TEST_KEY_3", 3.45678);
        
        double value;
        if(cache.Get("TEST_KEY_1", value))
            Print("Get TEST_KEY_1: ", DoubleToString(value, 5), " - PASS");
        else
            Print("Get TEST_KEY_1: FAIL");
            
        // Test cache hit
        cache.Get("TEST_KEY_2", value);
        cache.Get("TEST_KEY_2", value); // Second access
        
        // Test cache miss
        if(!cache.Get("NON_EXISTENT_KEY", value))
            Print("Non-existent key returns false - PASS");
            
        // Test LRU eviction
        cache.Set("TEST_KEY_4", 4.56789);
        cache.Set("TEST_KEY_5", 5.67890);
        cache.Set("TEST_KEY_6", 6.78901); // Should evict TEST_KEY_1
        
        if(!cache.Get("TEST_KEY_1", value))
            Print("TEST_KEY_1 was evicted (LRU) - PASS");
            
        // Test statistics
        int hits, misses, size, maxSize;
        double hitRate;
        cache.GetStats(hits, misses, hitRate, size, maxSize);
        
        Print("Stats - Hits: ", hits, ", Misses: ", misses, 
              ", Hit rate: ", hitRate, "%, Size: ", size, "/", maxSize);
        
        // Print cache contents
        cache.PrintCacheContents(true);
        
        Print("=== Cache Test Complete ===");
    }
    
private:
    //+------------------------------------------------------------------+
    //| Find node in hash map (simple implementation)                    |
    //+------------------------------------------------------------------+
    CacheNode* FindInHashMap(string key)
    {
        for(int i = 0; i < m_hashSize; i++)
        {
            if(m_hashMap[i].key == key)
                return m_hashMap[i].node;
        }
        return NULL;
    }
    
    //+------------------------------------------------------------------+
    //| Add node to hash map                                             |
    //+------------------------------------------------------------------+
    void AddToHashMap(string key, CacheNode* node)
    {
        if(m_hashSize >= 1000)
        {
            Print("ERROR: Hash map full!");
            return;
        }
        
        m_hashMap[m_hashSize].key = key;
        m_hashMap[m_hashSize].node = node;
        m_hashSize++;
    }
    
    //+------------------------------------------------------------------+
    //| Remove node from hash map                                        |
    //+------------------------------------------------------------------+
    void RemoveFromHashMap(string key)
    {
        for(int i = 0; i < m_hashSize; i++)
        {
            if(m_hashMap[i].key == key)
            {
                // Shift remaining entries
                for(int j = i; j < m_hashSize - 1; j++)
                {
                    m_hashMap[j] = m_hashMap[j + 1];
                }
                m_hashSize--;
                return;
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Add node to front of LRU list                                    |
    //+------------------------------------------------------------------+
    void AddToFront(CacheNode* node)
    {
        node->prev = NULL;
        node->next = m_head;
        
        if(m_head != NULL)
            m_head->prev = node;
            
        m_head = node;
        
        if(m_tail == NULL)
            m_tail = node;
            
        m_size++;
    }
    
    //+------------------------------------------------------------------+
    //| Remove node from LRU list                                        |
    //+------------------------------------------------------------------+
    void RemoveNode(CacheNode* node)
    {
        if(node == NULL) return;
        
        // Update neighbors
        if(node->prev != NULL)
            node->prev->next = node->next;
        else
            m_head = node->next;
            
        if(node->next != NULL)
            node->next->prev = node->prev;
        else
            m_tail = node->prev;
        
        // Remove from hash map
        RemoveFromHashMap(node->key);
        
        // Delete node
        delete node;
        m_size--;
    }
    
    //+------------------------------------------------------------------+
    //| Move node to front (most recently used)                          |
    //+------------------------------------------------------------------+
    void MoveToFront(CacheNode* node)
    {
        if(node == m_head) return;
        
        // Remove from current position
        if(node->prev != NULL)
            node->prev->next = node->next;
            
        if(node->next != NULL)
            node->next->prev = node->prev;
        else
            m_tail = node->prev;
        
        // Add to front
        node->prev = NULL;
        node->next = m_head;
        
        if(m_head != NULL)
            m_head->prev = node;
            
        m_head = node;
        
        if(m_tail == NULL)
            m_tail = node;
    }
    
    //+------------------------------------------------------------------+
    //| Remove least recently used node                                  |
    //+------------------------------------------------------------------+
    void RemoveLRU()
    {
        if(m_tail == NULL) return;
        
        RemoveNode(m_tail);
    }
    
    //+------------------------------------------------------------------+
    //| Check if cache entry is expired                                  |
    //+------------------------------------------------------------------+
    bool IsEntryExpired(CacheNode* node)
    {
        if(m_ttlSeconds <= 0) return false;
        
        datetime now = TimeCurrent();
        datetime expiryTime = node->timestamp + m_ttlSeconds;
        
        return (now > expiryTime);
    }
    
    //+------------------------------------------------------------------+
    //| Calculate cache hit rate                                         |
    //+------------------------------------------------------------------+
    double GetHitRate()
    {
        ulong total = m_hits + m_misses;
        if(total == 0) return 0.0;
        
        return (double)m_hits / total * 100.0;
    }
    
    //+------------------------------------------------------------------+
    //| Update performance statistics                                    |
    //+------------------------------------------------------------------+
    void UpdateStats(bool isHit, ulong responseTimeMicros)
    {
        if(isHit)
        {
            m_stats.memoryHits++;
            
            // Update average response time for hits
            double responseTimeMs = responseTimeMicros / 1000.0;
            if(m_stats.memoryHits == 1)
                m_stats.avgMemoryTime = responseTimeMs;
            else
                m_stats.avgMemoryTime = (m_stats.avgMemoryTime * (m_stats.memoryHits - 1) + 
                                        responseTimeMs) / m_stats.memoryHits;
        }
        else
        {
            m_stats.memoryMisses++;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Get current time in microseconds (for timing)                    |
    //+------------------------------------------------------------------+
    ulong GetMicrosecondCount()
    {
        return GetTickCount() * 1000; // Convert milliseconds to microseconds
    }
};

#endif // INDICATORCACHE_MQH