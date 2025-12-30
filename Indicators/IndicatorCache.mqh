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
//| Cache Node Structure (extends CacheEntry with LRU pointers)     |
//+------------------------------------------------------------------+
struct CacheNode
{
    CacheEntry  entry;          // Base cache entry from IndicatorTypes.mqh
    int         prevIndex;      // Previous node index (-1 if none)
    int         nextIndex;      // Next node index (-1 if none)
    
    CacheNode()
    {
        prevIndex = -1;
        nextIndex = -1;
    }
};

//+------------------------------------------------------------------+
//| LRU Memory Cache Class                                           |
//+------------------------------------------------------------------+
class CIndicatorCache
{
private:
    // Cache storage
    CacheNode   m_nodes[];              // Dynamic array of nodes
    int         m_headIndex;           // Index of most recently used node
    int         m_tailIndex;           // Index of least recently used node
    int         m_freeIndices[];       // Stack of free indices
    int         m_freeCount;           // Number of free indices
    
    int         m_maxSize;             // Maximum cache size
    int         m_ttlSeconds;          // Time-to-live in seconds
    ulong       m_hits;                // Cache hits counter
    ulong       m_misses;              // Cache misses counter
    
    // Hash map for O(1) lookups
    struct HashEntry
    {
        string key;
        int nodeIndex;  // Index in m_nodes array
    };
    HashEntry   m_hashMap[1000];       // Simple hash table
    int         m_hashSize;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor                                                      |
    //+------------------------------------------------------------------+
    CIndicatorCache(int maxSize = MAX_MEMORY_CACHE_ENTRIES, int ttlSeconds = MEMORY_CACHE_TTL_SECONDS)
    {
        m_headIndex = -1;
        m_tailIndex = -1;
        m_maxSize = maxSize;
        m_ttlSeconds = ttlSeconds;
        m_hits = 0;
        m_misses = 0;
        m_hashSize = 0;
        m_freeCount = 0;
        
        // Initialize hash map
        for(int i = 0; i < 1000; i++)
        {
            m_hashMap[i].key = "";
            m_hashMap[i].nodeIndex = -1;
        }
        
        // Initialize free indices array
        ArrayResize(m_freeIndices, maxSize);
        for(int i = 0; i < maxSize; i++)
        {
            m_freeIndices[i] = i;
        }
        m_freeCount = maxSize;
        
        // Initialize nodes array
        ArrayResize(m_nodes, maxSize);
        
        Print("IndicatorCache initialized. Max size: ", m_maxSize, 
              ", TTL: ", m_ttlSeconds, " seconds");
    }
    
    //+------------------------------------------------------------------+
    //| Destructor                                                       |
    //+------------------------------------------------------------------+
    ~CIndicatorCache()
    {
        Print("IndicatorCache destroyed. Final stats - Hits: ", m_hits, 
              ", Misses: ", m_misses, ", Hit rate: ", GetHitRate(), "%");
    }
    
    //+------------------------------------------------------------------+
    //| Get value from cache                                             |
    //+------------------------------------------------------------------+
    bool Get(string key, double &value)
    {
        // Find node in hash map
        int nodeIndex = FindInHashMap(key);
        
        if(nodeIndex == -1)
        {
            // Cache miss
            m_misses++;
            return false;
        }
        
        // Get node
        CacheNode node = m_nodes[nodeIndex];
        
        // Check if entry is expired
        if(IsEntryExpired(node.entry))
        {
            // Remove expired entry
            RemoveNode(nodeIndex);
            m_misses++;
            return false;
        }
        
        // Cache hit - update access info
        node.entry.accessCount++;
        node.entry.timestamp = TimeCurrent();
        
        // Update the node in array
        m_nodes[nodeIndex] = node;
        
        // Move to front (most recently used)
        MoveToFront(nodeIndex);
        
        value = node.entry.value;
        m_hits++;
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Set value in cache                                               |
    //+------------------------------------------------------------------+
    void Set(string key, double value)
    {
        // Check if key already exists
        int nodeIndex = FindInHashMap(key);
        
        if(nodeIndex != -1)
        {
            // Update existing node
            CacheNode node = m_nodes[nodeIndex];
            node.entry.value = value;
            node.entry.timestamp = TimeCurrent();
            node.entry.accessCount++;
            m_nodes[nodeIndex] = node;
            
            MoveToFront(nodeIndex);
            return;
        }
        
        // Check if cache is full
        if(IsFull())
        {
            // Remove least recently used node
            RemoveLRU();
        }
        
        // Get a free index
        nodeIndex = GetFreeIndex();
        if(nodeIndex == -1)
        {
            Print("ERROR: No free indices available");
            return;
        }
        
        // Create new node
        CacheNode node;
        node.entry.key = key;
        node.entry.value = value;
        node.entry.timestamp = TimeCurrent();
        node.entry.accessCount = 1;
        node.prevIndex = -1;
        node.nextIndex = -1;
        
        m_nodes[nodeIndex] = node;
        
        // Add to hash map
        AddToHashMap(key, nodeIndex);
        
        // Add to front of LRU list
        AddToFront(nodeIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Check if key exists in cache (without updating access)          |
    //+------------------------------------------------------------------+
    bool Has(string key)
    {
        int nodeIndex = FindInHashMap(key);
        
        if(nodeIndex == -1)
            return false;
            
        // Check if expired
        CacheNode node = m_nodes[nodeIndex];
        return !IsEntryExpired(node.entry);
    }
    
    //+------------------------------------------------------------------+
    //| Remove entry from cache                                          |
    //+------------------------------------------------------------------+
    bool Remove(string key)
    {
        int nodeIndex = FindInHashMap(key);
        
        if(nodeIndex == -1)
            return false;
            
        RemoveNode(nodeIndex);
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
            m_hashMap[i].key = "";
            m_hashMap[i].nodeIndex = -1;
        }
        m_hashSize = 0;
        
        // Reset LRU list
        m_headIndex = -1;
        m_tailIndex = -1;
        
        // Reset free indices
        m_freeCount = m_maxSize;
        for(int i = 0; i < m_maxSize; i++)
        {
            m_freeIndices[i] = i;
            m_nodes[i] = CacheNode();
        }
        
        Print("Cache cleared");
    }
    
    //+------------------------------------------------------------------+
    //| Cleanup expired entries                                          |
    //+------------------------------------------------------------------+
    int CleanupExpired()
    {
        int removed = 0;
        int currentIndex = m_headIndex;
        
        while(currentIndex != -1)
        {
            CacheNode node = m_nodes[currentIndex];
            int nextIndex = node.nextIndex;
            
            if(IsEntryExpired(node.entry))
            {
                RemoveNode(currentIndex);
                removed++;
            }
            
            currentIndex = nextIndex;
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
        size = m_maxSize - m_freeCount;
        maxSize = m_maxSize;
    }
    
    //+------------------------------------------------------------------+
    //| Print cache contents (for debugging)                             |
    //+------------------------------------------------------------------+
    void PrintCacheContents(bool detailed = false)
    {
        int currentSize = m_maxSize - m_freeCount;
        Print("=== Cache Contents (", currentSize, "/", m_maxSize, " entries) ===");
        Print("Hits: ", m_hits, ", Misses: ", m_misses, ", Hit rate: ", GetHitRate(), "%");
        
        if(!detailed)
        {
            Print("Keys: ", GetKeysAsString());
            return;
        }
        
        // Detailed print
        int currentIndex = m_headIndex;
        int count = 0;
        
        while(currentIndex != -1 && count < 20)
        {
            CacheNode node = m_nodes[currentIndex];
            double agePercent = 0.0;
            if(m_ttlSeconds > 0)
            {
                agePercent = (double)(TimeCurrent() - node.entry.timestamp) / m_ttlSeconds;
            }
            
            string ageStr = CIndicatorUtils::FormatPercent(agePercent);
            
            Print(count + 1, ". ", node.entry.key, 
                  " = ", DoubleToString(node.entry.value, 5),
                  " (Age: ", ageStr, ", Accesses: ", node.entry.accessCount, 
                  ", Index: ", currentIndex, ")");
            
            currentIndex = node.nextIndex;
            count++;
        }
        
        if(currentSize > 20)
            Print("... and ", currentSize - 20, " more entries");
            
        Print("=== End Cache Contents ===");
    }
    
    //+------------------------------------------------------------------+
    //| Get all cache keys as comma-separated string                     |
    //+------------------------------------------------------------------+
    string GetKeysAsString()
    {
        string keys = "";
        int currentIndex = m_headIndex;
        int count = 0;
        
        while(currentIndex != -1 && count < 10)
        {
            CacheNode node = m_nodes[currentIndex];
            if(keys != "") keys += ", ";
            keys += node.entry.key;
            
            currentIndex = node.nextIndex;
            count++;
        }
        
        int currentSize = m_maxSize - m_freeCount;
        if(currentSize > 10)
            keys += ", ...";
            
        return keys;
    }
    
    //+------------------------------------------------------------------+
    //| Get cache size                                                   |
    //+------------------------------------------------------------------+
    int GetSize()
    {
        return m_maxSize - m_freeCount;
    }
    
    //+------------------------------------------------------------------+
    //| Get maximum cache size                                           |
    //+------------------------------------------------------------------+
    int GetMaxSize()
    {
        return m_maxSize;
    }
    
    //+------------------------------------------------------------------+
    //| Test cache functionality                                         |
    //+------------------------------------------------------------------+
    static void TestCache()
    {
        Print("=== Testing Memory Cache ===");
        
        CIndicatorCache cache(5, 10);
        
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
        cache.Get("TEST_KEY_2", value);
        
        // Test cache miss
        if(!cache.Get("NON_EXISTENT_KEY", value))
            Print("Non-existent key returns false - PASS");
            
        // Test LRU eviction
        cache.Set("TEST_KEY_4", 4.56789);
        cache.Set("TEST_KEY_5", 5.67890);
        cache.Set("TEST_KEY_6", 6.78901);
        
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
    //| Find node in hash map                                           |
    //+------------------------------------------------------------------+
    int FindInHashMap(string key)
    {
        for(int i = 0; i < m_hashSize; i++)
        {
            if(m_hashMap[i].key == key)
                return m_hashMap[i].nodeIndex;
        }
        return -1;
    }
    
    //+------------------------------------------------------------------+
    //| Add node to hash map                                            |
    //+------------------------------------------------------------------+
    void AddToHashMap(string key, int nodeIndex)
    {
        if(m_hashSize >= 1000)
        {
            Print("ERROR: Hash map full!");
            return;
        }
        
        m_hashMap[m_hashSize].key = key;
        m_hashMap[m_hashSize].nodeIndex = nodeIndex;
        m_hashSize++;
    }
    
    //+------------------------------------------------------------------+
    //| Remove node from hash map                                       |
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
    //| Add node to front of LRU list                                   |
    //+------------------------------------------------------------------+
    void AddToFront(int nodeIndex)
    {
        CacheNode node = m_nodes[nodeIndex];
        
        node.prevIndex = -1;
        node.nextIndex = m_headIndex;
        
        if(m_headIndex != -1)
        {
            CacheNode headNode = m_nodes[m_headIndex];
            headNode.prevIndex = nodeIndex;
            m_nodes[m_headIndex] = headNode;
        }
        
        m_headIndex = nodeIndex;
        
        if(m_tailIndex == -1)
        {
            m_tailIndex = nodeIndex;
        }
        
        m_nodes[nodeIndex] = node;
    }
    
    //+------------------------------------------------------------------+
    //| Remove node from LRU list                                       |
    //+------------------------------------------------------------------+
    void RemoveNode(int nodeIndex)
    {
        if(nodeIndex < 0 || nodeIndex >= m_maxSize)
            return;
            
        CacheNode node = m_nodes[nodeIndex];
        
        // Update neighbors
        if(node.prevIndex != -1)
        {
            CacheNode prevNode = m_nodes[node.prevIndex];
            prevNode.nextIndex = node.nextIndex;
            m_nodes[node.prevIndex] = prevNode;
        }
        else
        {
            m_headIndex = node.nextIndex;
        }
            
        if(node.nextIndex != -1)
        {
            CacheNode nextNode = m_nodes[node.nextIndex];
            nextNode.prevIndex = node.prevIndex;
            m_nodes[node.nextIndex] = nextNode;
        }
        else
        {
            m_tailIndex = node.prevIndex;
        }
        
        // Remove from hash map
        RemoveFromHashMap(node.entry.key);
        
        // Clear node
        m_nodes[nodeIndex] = CacheNode();
        
        // Add to free indices
        m_freeIndices[m_freeCount] = nodeIndex;
        m_freeCount++;
    }
    
    //+------------------------------------------------------------------+
    //| Move node to front (most recently used)                         |
    //+------------------------------------------------------------------+
    void MoveToFront(int nodeIndex)
    {
        if(nodeIndex == m_headIndex) return;
        
        // First remove the node from its current position
        CacheNode node = m_nodes[nodeIndex];
        
        if(node.prevIndex != -1)
        {
            CacheNode prevNode = m_nodes[node.prevIndex];
            prevNode.nextIndex = node.nextIndex;
            m_nodes[node.prevIndex] = prevNode;
        }
            
        if(node.nextIndex != -1)
        {
            CacheNode nextNode = m_nodes[node.nextIndex];
            nextNode.prevIndex = node.prevIndex;
            m_nodes[node.nextIndex] = nextNode;
        }
        else
        {
            m_tailIndex = node.prevIndex;
        }
        
        // Now add to front
        node.prevIndex = -1;
        node.nextIndex = m_headIndex;
        
        if(m_headIndex != -1)
        {
            CacheNode headNode = m_nodes[m_headIndex];
            headNode.prevIndex = nodeIndex;
            m_nodes[m_headIndex] = headNode;
        }
            
        m_headIndex = nodeIndex;
        
        if(m_tailIndex == -1)
        {
            m_tailIndex = nodeIndex;
        }
        
        m_nodes[nodeIndex] = node;
    }
    
    //+------------------------------------------------------------------+
    //| Remove least recently used node                                 |
    //+------------------------------------------------------------------+
    void RemoveLRU()
    {
        if(m_tailIndex == -1) return;
        
        RemoveNode(m_tailIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Check if cache entry is expired                                  |
    //+------------------------------------------------------------------+
    bool IsEntryExpired(CacheEntry &entry)
    {
        if(m_ttlSeconds <= 0) return false;
        
        datetime now = TimeCurrent();
        datetime expiryTime = entry.timestamp + m_ttlSeconds;
        
        return (now > expiryTime);
    }
    
    //+------------------------------------------------------------------+
    //| Check if cache is full                                           |
    //+------------------------------------------------------------------+
    bool IsFull()
    {
        return (m_freeCount == 0);
    }
    
    //+------------------------------------------------------------------+
    //| Get a free index from the pool                                   |
    //+------------------------------------------------------------------+
    int GetFreeIndex()
    {
        if(m_freeCount == 0) return -1;
        
        m_freeCount--;
        return m_freeIndices[m_freeCount];
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
};

#endif // INDICATORCACHE_MQH