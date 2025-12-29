// Indicators/IndicatorStorage.mqh
//+------------------------------------------------------------------+
//| Description: Binary file storage for Indicator System           |
//+------------------------------------------------------------------+
#ifndef INDICATORSTORAGE_MQH
#define INDICATORSTORAGE_MQH

#include "IndicatorTypes.mqh"
#include "IndicatorKey.mqh"
#include "IndicatorUtils.mqh"

//+------------------------------------------------------------------+
//| Binary File Header Structure (64 bytes)                          |
//+------------------------------------------------------------------+
struct FileHeader
{
    uint        magicNumber;        // 0x534F4C41 ("SOLA")
    ushort      version;            // File format version
    ushort      entryCount;         // Number of entries
    uint        createdTimestamp;   // When file was created
    uint        updatedTimestamp;   // When file was last updated
    uint        reserved1;          // Reserved for future use
    uint        reserved2;          // Reserved for future use
    uint        reserved3;          // Reserved for future use
    uint        reserved4;          // Reserved for future use
    uint        reserved5;          // Reserved for future use
    uint        reserved6;          // Reserved for future use
    uint        reserved7;          // Reserved for future use
    uint        reserved8;          // Reserved for future use
    
    FileHeader()
    {
        magicNumber = INDICATOR_MAGIC_NUMBER;
        version = INDICATOR_FILE_VERSION;
        entryCount = 0;
        createdTimestamp = CIndicatorUtils::GetUnixTimestamp();
        updatedTimestamp = createdTimestamp;
        reserved1 = 0;
        reserved2 = 0;
        reserved3 = 0;
        reserved4 = 0;
        reserved5 = 0;
        reserved6 = 0;
        reserved7 = 0;
        reserved8 = 0;
    }
};

//+------------------------------------------------------------------+
//| File Cache Entry Structure (64 bytes)                            |
//+------------------------------------------------------------------+
struct FileCacheEntry
{
    char        key[40];            // Null-terminated string (39 chars + null)
    double      value;              // 8 bytes
    uint        timestamp;          // 4 bytes
    ushort      accessCount;        // 2 bytes
    uchar       flags;              // 1 byte
    uchar       reserved[9];        // Padding to 64 bytes
    
    FileCacheEntry()
    {
        StringToCharArray("", key, 0, 40);
        value = 0.0;
        timestamp = 0;
        accessCount = 0;
        flags = 0;
        ArrayInitialize(reserved, 0);
    }
};

//+------------------------------------------------------------------+
//| Binary File Storage Class                                        |
//+------------------------------------------------------------------+
class CIndicatorStorage
{
private:
    string              m_filename;         // Current cache file
    string              m_archivePath;      // Archive directory
    int                 m_maxEntries;       // Maximum entries in file
    int                 m_ttlSeconds;       // Time-to-live in seconds
    bool                m_enabled;          // Is file cache enabled?
    
    // In-memory index for fast lookups
    struct FileIndexEntry
    {
        string key;
        int filePosition;    // Position in file (entry index)
        bool isValid;
    };
    FileIndexEntry      m_index[1000];      // Index for fast lookups
    int                 m_indexSize;
    
    // Statistics
    ulong               m_fileHits;
    ulong               m_fileMisses;
    PerformanceStats    m_stats;
    
public:
    //+------------------------------------------------------------------+
    //| Constructor                                                      |
    //+------------------------------------------------------------------+
    CIndicatorStorage(string filename = "cache_current.bin", 
                     int maxEntries = 500, 
                     int ttlSeconds = FILE_CACHE_TTL_SECONDS)
    {
        m_filename = "Data/Indicators/" + filename;
        m_archivePath = "Data/Indicators/cache_archive/";
        m_maxEntries = maxEntries;
        m_ttlSeconds = ttlSeconds;
        m_enabled = true;
        m_indexSize = 0;
        m_fileHits = 0;
        m_fileMisses = 0;
        
        // Create directories if they don't exist
        CreateDirectories();
        
        // Build index from existing file
        BuildIndex();
        
        Print("IndicatorStorage initialized. File: ", m_filename, 
              ", Max entries: ", m_maxEntries, ", TTL: ", m_ttlSeconds, " seconds");
    }
    
    //+------------------------------------------------------------------+
    //| Destructor                                                       |
    //+------------------------------------------------------------------+
    ~CIndicatorStorage()
    {
        // Save any pending changes
        if(m_enabled)
        {
            CleanupExpired();
            Print("IndicatorStorage destroyed. File hits: ", m_fileHits, 
                  ", Misses: ", m_fileMisses, ", Hit rate: ", GetHitRate(), "%");
        }
    }
    
    //+------------------------------------------------------------------+
    //| Get value from file cache                                        |
    //+------------------------------------------------------------------+
    bool Get(string key, double &value)
    {
        if(!m_enabled) 
            return false;
            
        ulong startTime = GetMicrosecondCount();
        
        // Check index first
        int entryIndex = FindInIndex(key);
        
        if(entryIndex == -1)
        {
            // Not in index
            m_fileMisses++;
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        // Read entry from file
        FileCacheEntry entry;
        if(!ReadEntry(entryIndex, entry))
        {
            // Read failed
            m_fileMisses++;
            RemoveFromIndex(key);
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        // Check if entry is expired
        if(IsEntryExpired(entry))
        {
            // Expired - remove from file
            RemoveEntry(entryIndex);
            m_fileMisses++;
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        // Valid entry found
        value = entry.value;
        
        // Update access count
        entry.accessCount++;
        entry.timestamp = CIndicatorUtils::GetUnixTimestamp();
        WriteEntry(entryIndex, entry);
        
        m_fileHits++;
        UpdateStats(true, GetMicrosecondCount() - startTime);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Set value in file cache                                          |
    //+------------------------------------------------------------------+
    bool Set(string key, double value)
    {
        if(!m_enabled) 
            return false;
            
        ulong startTime = GetMicrosecondCount();
        
        // Check if key already exists
        int entryIndex = FindInIndex(key);
        
        if(entryIndex != -1)
        {
            // Update existing entry
            FileCacheEntry entry;
            if(ReadEntry(entryIndex, entry))
            {
                entry.value = value;
                entry.timestamp = CIndicatorUtils::GetUnixTimestamp();
                entry.accessCount++;
                entry.flags |= FLAG_IS_DIRTY;
                
                WriteEntry(entryIndex, entry);
                
                UpdateStats(false, GetMicrosecondCount() - startTime);
                return true;
            }
            else
            {
                // Read failed - remove from index
                RemoveFromIndex(key);
            }
        }
        
        // Create new entry
        FileCacheEntry newEntry;
        StringToCharArray(key, newEntry.key, 0, 40);
        newEntry.value = value;
        newEntry.timestamp = CIndicatorUtils::GetUnixTimestamp();
        newEntry.accessCount = 1;
        newEntry.flags = FLAG_IS_DIRTY;
        
        // Check if we need to make space
        if(GetEntryCount() >= m_maxEntries)
        {
            if(!RemoveOldestEntry())
            {
                // Failed to make space
                UpdateStats(false, GetMicrosecondCount() - startTime);
                return false;
            }
        }
        
        // Add new entry
        if(!AddEntry(newEntry))
        {
            UpdateStats(false, GetMicrosecondCount() - startTime);
            return false;
        }
        
        UpdateStats(false, GetMicrosecondCount() - startTime);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Check if key exists in file cache                                |
    //+------------------------------------------------------------------+
    bool Has(string key)
    {
        if(!m_enabled) 
            return false;
            
        int entryIndex = FindInIndex(key);
        
        if(entryIndex == -1)
            return false;
            
        // Check if expired
        FileCacheEntry entry;
        if(!ReadEntry(entryIndex, entry))
            return false;
            
        return !IsEntryExpired(entry);
    }
    
    //+------------------------------------------------------------------+
    //| Remove entry from file cache                                     |
    //+------------------------------------------------------------------+
    bool Remove(string key)
    {
        if(!m_enabled) 
            return false;
            
        int entryIndex = FindInIndex(key);
        
        if(entryIndex == -1)
            return false;
            
        return RemoveEntry(entryIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Cleanup expired entries                                          |
    //+------------------------------------------------------------------+
    int CleanupExpired()
    {
        if(!m_enabled) 
            return 0;
            
        int removed = 0;
        
        // Read file header
        FileHeader header;
        if(!ReadHeader(header))
            return 0;
            
        // Check each entry
        for(int i = 0; i < header.entryCount; i++)
        {
            FileCacheEntry entry;
            if(!ReadEntry(i, entry))
                continue;
                
            if(IsEntryExpired(entry))
            {
                if(RemoveEntry(i))
                {
                    removed++;
                    i--; // Adjust index since entries shift
                    header.entryCount = GetEntryCount();
                }
            }
        }
        
        if(removed > 0)
            Print("Cleaned up ", removed, " expired file cache entries");
            
        return removed;
    }
    
    //+------------------------------------------------------------------+
    //| Archive current cache file                                       |
    //+------------------------------------------------------------------+
    bool ArchiveCurrentFile()
    {
        if(!m_enabled || !FileIsExist(m_filename))
            return false;
            
        // Create archive filename with date
        MqlDateTime dt;
        TimeCurrent(dt);
        string archiveName = StringFormat("cache_%04d-%02d-%02d.bin", 
                                         dt.year, dt.mon, dt.day);
        string archivePath = m_archivePath + archiveName;
        
        // Copy current file to archive
        if(FileCopy(m_filename, 0, archivePath, FILE_REWRITE))
        {
            Print("Archived cache file to: ", archivePath);
            
            // Clean up old archives (keep last 7 days)
            CleanupOldArchives(7);
            
            return true;
        }
        
        Print("ERROR: Failed to archive cache file");
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| Load cache from file                                             |
    //+------------------------------------------------------------------+
    bool LoadFromFile(string filename = "")
    {
        if(filename == "")
            filename = m_filename;
            
        if(!FileIsExist(filename))
        {
            Print("Cache file not found: ", filename);
            return false;
        }
        
        // Read and validate file
        FileHeader header;
        if(!ReadHeader(filename, header))
        {
            Print("ERROR: Invalid cache file: ", filename);
            return false;
        }
        
        // Rebuild index
        BuildIndex();
        
        Print("Loaded cache from ", filename, " (", header.entryCount, " entries)");
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Save cache to file                                               |
    //+------------------------------------------------------------------+
    bool SaveToFile(string filename = "")
    {
        if(filename == "")
            filename = m_filename;
            
        // Update file header
        FileHeader header;
        if(!ReadHeader(header))
            header = FileHeader();
            
        header.entryCount = GetEntryCount();
        header.updatedTimestamp = CIndicatorUtils::GetUnixTimestamp();
        
        if(!WriteHeader(filename, header))
        {
            Print("ERROR: Failed to save cache file: ", filename);
            return false;
        }
        
        Print("Saved cache to ", filename, " (", header.entryCount, " entries)");
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Get file cache statistics                                        |
    //+------------------------------------------------------------------+
    void GetStats(int &hits, int &misses, double &hitRate, int &entryCount)
    {
        hits = (int)m_fileHits;
        misses = (int)m_fileMisses;
        hitRate = GetHitRate();
        entryCount = GetEntryCount();
    }
    
    //+------------------------------------------------------------------+
    //| Get performance statistics                                       |
    //+------------------------------------------------------------------+
    PerformanceStats GetPerformanceStats()
    {
        return m_stats;
    }
    
    //+------------------------------------------------------------------+
    //| Enable/disable file cache                                        |
    //+------------------------------------------------------------------+
    void SetEnabled(bool enabled)
    {
        m_enabled = enabled;
        Print("File cache ", enabled ? "enabled" : "disabled");
    }
    
    //+------------------------------------------------------------------+
    //| Check if file cache is enabled                                   |
    //+------------------------------------------------------------------+
    bool IsEnabled()
    {
        return m_enabled;
    }
    
    //+------------------------------------------------------------------+
    //| Get current filename                                             |
    //+------------------------------------------------------------------+
    string GetFilename()
    {
        return m_filename;
    }
    
    //+------------------------------------------------------------------+
    //| Get entry count                                                  |
    //+------------------------------------------------------------------+
    int GetEntryCount()
    {
        FileHeader header;
        if(!ReadHeader(header))
            return 0;
            
        return header.entryCount;
    }
    
    //+------------------------------------------------------------------+
    //| Print file cache contents (for debugging)                        |
    //+------------------------------------------------------------------+
    void PrintFileCacheContents(bool detailed = false)
    {
        if(!m_enabled)
        {
            Print("File cache is disabled");
            return;
        }
        
        FileHeader header;
        if(!ReadHeader(header))
        {
            Print("ERROR: Cannot read cache file");
            return;
        }
        
        Print("=== File Cache Contents (", header.entryCount, "/", m_maxEntries, " entries) ===");
        Print("File: ", m_filename);
        Print("Created: ", TimeToString(header.createdTimestamp), 
              ", Updated: ", TimeToString(header.updatedTimestamp));
        Print("Hits: ", m_fileHits, ", Misses: ", m_fileMisses, 
              ", Hit rate: ", GetHitRate(), "%");
        
        if(!detailed || header.entryCount == 0)
            return;
        
        // Print first few entries
        int entriesToShow = MathMin(header.entryCount, 10);
        
        for(int i = 0; i < entriesToShow; i++)
        {
            FileCacheEntry entry;
            if(ReadEntry(i, entry))
            {
                string key = CharArrayToString(entry.key);
                string age = CIndicatorUtils::FormatPercent(
                    (double)(CIndicatorUtils::GetUnixTimestamp() - entry.timestamp) / m_ttlSeconds);
                    
                Print(i + 1, ". ", key, " = ", DoubleToString(entry.value, 5),
                      " (Age: ", age, ", Accesses: ", entry.accessCount, ")");
            }
        }
        
        if(header.entryCount > 10)
            Print("... and ", header.entryCount - 10, " more entries");
            
        Print("=== End File Cache Contents ===");
    }
    
    //+------------------------------------------------------------------+
    //| Test file storage functionality                                  |
    //+------------------------------------------------------------------+
    static void TestStorage()
    {
        Print("=== Testing File Storage ===");
        
        // Create test cache file
        string testFile = "Data/Indicators/test_cache.bin";
        
        // Delete existing test file
        if(FileIsExist(testFile))
            FileDelete(testFile);
        
        CIndicatorStorage storage(testFile, 10, 60); // Small cache for testing
        
        // Test Set and Get
        storage.Set("TEST_KEY_1", 1.23456);
        storage.Set("TEST_KEY_2", 2.34567);
        storage.Set("TEST_KEY_3", 3.45678);
        
        double value;
        if(storage.Get("TEST_KEY_1", value))
            Print("Get TEST_KEY_1: ", DoubleToString(value, 5), " - PASS");
        else
            Print("Get TEST_KEY_1: FAIL");
            
        // Test cache hit
        storage.Get("TEST_KEY_2", value);
        storage.Get("TEST_KEY_2", value); // Second access
        
        // Test cache miss
        if(!storage.Get("NON_EXISTENT_KEY", value))
            Print("Non-existent key returns false - PASS");
            
        // Fill cache to test eviction
        for(int i = 4; i <= 15; i++)
        {
            string key = "TEST_KEY_" + IntegerToString(i);
            storage.Set(key, i * 1.11111);
        }
        
        // Oldest entry should be evicted
        if(!storage.Get("TEST_KEY_1", value))
            Print("TEST_KEY_1 was evicted (oldest) - PASS");
            
        // Test statistics
        int hits, misses, entryCount;
        double hitRate;
        storage.GetStats(hits, misses, hitRate, entryCount);
        
        Print("Stats - Hits: ", hits, ", Misses: ", misses, 
              ", Hit rate: ", hitRate, "%, Entries: ", entryCount);
        
        // Print cache contents
        storage.PrintFileCacheContents(true);
        
        // Clean up test file
        FileDelete(testFile);
        
        Print("=== File Storage Test Complete ===");
    }
    
private:
    //+------------------------------------------------------------------+
    //| Create necessary directories                                     |
    //+------------------------------------------------------------------+
    void CreateDirectories()
    {
        // Create Data/Indicators directory
        string dataDir = "Data/Indicators";
        if(!FolderCreate(dataDir, FILE_COMMON))
        {
            // Directory might already exist
        }
        
        // Create archive directory
        if(!FolderCreate(m_archivePath, FILE_COMMON))
        {
            // Directory might already exist
        }
    }
    
    //+------------------------------------------------------------------+
    //| Build index from file                                            |
    //+------------------------------------------------------------------+
    void BuildIndex()
    {
        // Clear existing index
        ArrayInitialize(m_index, NULL);
        m_indexSize = 0;
        
        if(!FileIsExist(m_filename))
            return;
            
        FileHeader header;
        if(!ReadHeader(header))
            return;
            
        // Read all entries and build index
        for(int i = 0; i < header.entryCount && m_indexSize < 1000; i++)
        {
            FileCacheEntry entry;
            if(ReadEntry(i, entry))
            {
                string key = CharArrayToString(entry.key);
                if(key != "")
                {
                    m_index[m_indexSize].key = key;
                    m_index[m_indexSize].filePosition = i;
                    m_index[m_indexSize].isValid = true;
                    m_indexSize++;
                }
            }
        }
        
        Print("Built index with ", m_indexSize, " entries");
    }
    
    //+------------------------------------------------------------------+
    //| Find key in index                                                |
    //+------------------------------------------------------------------+
    int FindInIndex(string key)
    {
        for(int i = 0; i < m_indexSize; i++)
        {
            if(m_index[i].key == key && m_index[i].isValid)
                return m_index[i].filePosition;
        }
        return -1;
    }
    
    //+------------------------------------------------------------------+
    //| Add key to index                                                 |
    //+------------------------------------------------------------------+
    void AddToIndex(string key, int position)
    {
        if(m_indexSize >= 1000)
            return;
            
        m_index[m_indexSize].key = key;
        m_index[m_indexSize].filePosition = position;
        m_index[m_indexSize].isValid = true;
        m_indexSize++;
    }
    
    //+------------------------------------------------------------------+
    //| Remove key from index                                            |
    //+------------------------------------------------------------------+
    void RemoveFromIndex(string key)
    {
        for(int i = 0; i < m_indexSize; i++)
        {
            if(m_index[i].key == key)
            {
                m_index[i].isValid = false;
                return;
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Update index position (when entries shift)                       |
    //+------------------------------------------------------------------+
    void UpdateIndexPositions(int fromPosition)
    {
        for(int i = 0; i < m_indexSize; i++)
        {
            if(m_index[i].isValid && m_index[i].filePosition > fromPosition)
                m_index[i].filePosition--;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Read file header                                                 |
    //+------------------------------------------------------------------+
    bool ReadHeader(FileHeader &header, string filename = "")
    {
        if(filename == "")
            filename = m_filename;
            
        if(!FileIsExist(filename))
            return false;
            
        int handle = FileOpen(filename, FILE_READ|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        // Read header (64 bytes)
        uint bytesRead = FileReadStruct(handle, header);
        FileClose(handle);
        
        if(bytesRead != sizeof(header))
            return false;
            
        // Validate magic number
        if(header.magicNumber != INDICATOR_MAGIC_NUMBER)
            return false;
            
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Write file header                                                |
    //+------------------------------------------------------------------+
    bool WriteHeader(string filename, FileHeader &header)
    {
        int handle = FileOpen(filename, FILE_WRITE|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        header.updatedTimestamp = CIndicatorUtils::GetUnixTimestamp();
        
        uint bytesWritten = FileWriteStruct(handle, header);
        FileClose(handle);
        
        return (bytesWritten == sizeof(header));
    }
    
    //+------------------------------------------------------------------+
    //| Read cache entry                                                 |
    //+------------------------------------------------------------------+
    bool ReadEntry(int index, FileCacheEntry &entry)
    {
        int handle = FileOpen(m_filename, FILE_READ|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        // Seek to entry position
        int position = FILE_HEADER_SIZE + (index * CACHE_ENTRY_SIZE);
        FileSeek(handle, position, SEEK_SET);
        
        uint bytesRead = FileReadStruct(handle, entry);
        FileClose(handle);
        
        return (bytesRead == sizeof(entry));
    }
    
    //+------------------------------------------------------------------+
    //| Write cache entry                                                |
    //+------------------------------------------------------------------+
    bool WriteEntry(int index, FileCacheEntry &entry)
    {
        int handle = FileOpen(m_filename, FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        // Seek to entry position
        int position = FILE_HEADER_SIZE + (index * CACHE_ENTRY_SIZE);
        FileSeek(handle, position, SEEK_SET);
        
        uint bytesWritten = FileWriteStruct(handle, entry);
        FileClose(handle);
        
        return (bytesWritten == sizeof(entry));
    }
    
    //+------------------------------------------------------------------+
    //| Add new entry to file                                            |
    //+------------------------------------------------------------------+
    bool AddEntry(FileCacheEntry &entry)
    {
        FileHeader header;
        if(!ReadHeader(header))
        {
            // Create new file
            header = FileHeader();
            header.entryCount = 0;
        }
        
        if(header.entryCount >= m_maxEntries)
            return false;
            
        // Open file for appending
        int handle = FileOpen(m_filename, FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        // Seek to end of entries
        int position = FILE_HEADER_SIZE + (header.entryCount * CACHE_ENTRY_SIZE);
        FileSeek(handle, position, SEEK_SET);
        
        // Write new entry
        uint bytesWritten = FileWriteStruct(handle, entry);
        
        // Update header
        header.entryCount++;
        header.updatedTimestamp = CIndicatorUtils::GetUnixTimestamp();
        
        FileSeek(handle, 0, SEEK_SET);
        FileWriteStruct(handle, header);
        
        FileClose(handle);
        
        // Add to index
        AddToIndex(CharArrayToString(entry.key), header.entryCount - 1);
        
        return (bytesWritten == sizeof(entry));
    }
    
    //+------------------------------------------------------------------+
    //| Remove entry from file                                           |
    //+------------------------------------------------------------------+
    bool RemoveEntry(int index)
    {
        FileHeader header;
        if(!ReadHeader(header))
            return false;
            
        if(index >= header.entryCount)
            return false;
            
        // If it's the last entry, just truncate
        if(index == header.entryCount - 1)
        {
            header.entryCount--;
            WriteHeader(m_filename, header);
            RemoveFromIndexByPosition(index);
            return true;
        }
        
        // Need to shift entries
        int handle = FileOpen(m_filename, FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
        if(handle == INVALID_HANDLE)
            return false;
            
        // Read all entries after the one being removed
        int entriesAfter = header.entryCount - index - 1;
        FileCacheEntry entries[];
        ArrayResize(entries, entriesAfter);
        
        int startPos = FILE_HEADER_SIZE + ((index + 1) * CACHE_ENTRY_SIZE);
        FileSeek(handle, startPos, SEEK_SET);
        
        for(int i = 0; i < entriesAfter; i++)
        {
            FileReadStruct(handle, entries[i]);
        }
        
        // Write shifted entries back one position earlier
        startPos = FILE_HEADER_SIZE + (index * CACHE_ENTRY_SIZE);
        FileSeek(handle, startPos, SEEK_SET);
        
        for(int i = 0; i < entriesAfter; i++)
        {
            FileWriteStruct(handle, entries[i]);
        }
        
        // Update header
        header.entryCount--;
        header.updatedTimestamp = CIndicatorUtils::GetUnixTimestamp();
        
        FileSeek(handle, 0, SEEK_SET);
        FileWriteStruct(handle, header);
        
        FileClose(handle);
        
        // Update index
        RemoveFromIndexByPosition(index);
        UpdateIndexPositions(index);
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Remove oldest entry (by timestamp)                               |
    //+------------------------------------------------------------------+
    bool RemoveOldestEntry()
    {
        FileHeader header;
        if(!ReadHeader(header) || header.entryCount == 0)
            return false;
            
        // Find oldest entry
        int oldestIndex = -1;
        uint oldestTimestamp = 0xFFFFFFFF;
        
        for(int i = 0; i < header.entryCount; i++)
        {
            FileCacheEntry entry;
            if(ReadEntry(i, entry))
            {
                if(entry.timestamp < oldestTimestamp)
                {
                    oldestTimestamp = entry.timestamp;
                    oldestIndex = i;
                }
            }
        }
        
        if(oldestIndex == -1)
            return false;
            
        return RemoveEntry(oldestIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Remove from index by position                                    |
    //+------------------------------------------------------------------+
    void RemoveFromIndexByPosition(int position)
    {
        for(int i = 0; i < m_indexSize; i++)
        {
            if(m_index[i].filePosition == position)
            {
                m_index[i].isValid = false;
                return;
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Check if entry is expired                                        |
    //+------------------------------------------------------------------+
    bool IsEntryExpired(FileCacheEntry &entry)
    {
        if(m_ttlSeconds <= 0) return false;
        
        uint now = CIndicatorUtils::GetUnixTimestamp();
        uint expiryTime = entry.timestamp + m_ttlSeconds;
        
        return (now > expiryTime);
    }
    
    //+------------------------------------------------------------------+
    //| Clean up old archive files                                       |
    //+------------------------------------------------------------------+
    void CleanupOldArchives(int keepDays)
    {
        string filenames[];
        string searchPath = m_archivePath + "cache_*.bin";
        
        // Get list of archive files
        long handle = FileFindFirst(searchPath, filenames[0], 0);
        if(handle == INVALID_HANDLE)
            return;
            
        int count = 1;
        while(FileFindNext(handle, filenames[count]))
            count++;
            
        FileFindClose(handle);
        
        // Sort by filename (which contains date)
        ArraySort(filenames);
        
        // Keep only the most recent files
        int filesToDelete = ArraySize(filenames) - keepDays;
        if(filesToDelete <= 0)
            return;
            
        for(int i = 0; i < filesToDelete; i++)
        {
            string filepath = m_archivePath + filenames[i];
            if(FileDelete(filepath, FILE_COMMON))
                Print("Deleted old archive: ", filepath);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Calculate hit rate                                               |
    //+------------------------------------------------------------------+
    double GetHitRate()
    {
        ulong total = m_fileHits + m_fileMisses;
        if(total == 0) return 0.0;
        
        return (double)m_fileHits / total * 100.0;
    }
    
    //+------------------------------------------------------------------+
    //| Update performance statistics                                    |
    //+------------------------------------------------------------------+
    void UpdateStats(bool isHit, ulong responseTimeMicros)
    {
        if(isHit)
        {
            m_stats.fileHits++;
            
            // Update average response time for hits
            double responseTimeMs = responseTimeMicros / 1000.0;
            if(m_stats.fileHits == 1)
                m_stats.avgFileTime = responseTimeMs;
            else
                m_stats.avgFileTime = (m_stats.avgFileTime * (m_stats.fileHits - 1) + 
                                      responseTimeMs) / m_stats.fileHits;
        }
        else
        {
            m_stats.fileMisses++;
        }
    }
    
    //+------------------------------------------------------------------+
    //| Get current time in microseconds                                 |
    //+------------------------------------------------------------------+
    ulong GetMicrosecondCount()
    {
        return GetTickCount() * 1000;
    }
};

#endif // INDICATORSTORAGE_MQH