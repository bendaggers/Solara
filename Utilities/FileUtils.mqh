//+------------------------------------------------------------------+
//| FileUtils.mqh - File operation utilities for Solara              |
//+------------------------------------------------------------------+
#ifndef FILEUTILS_MQH
#define FILEUTILS_MQH

#include "Logger.mqh"
#include <Files\FileTxt.mqh>
#include <Files\FileBin.mqh>

//+------------------------------------------------------------------+
//| CFileUtils - File utility class                                  |
//+------------------------------------------------------------------+
class CFileUtils {
private:
    CLogger* m_logger;
    
    // Helper function to trim strings (MQL5 doesn't have StringTrim)
    string StringTrim(string str) {
        // Trim leading spaces
        int start = 0;
        while(start < StringLen(str) && StringGetCharacter(str, start) == ' ') {
            start++;
        }
        
        // Trim trailing spaces
        int end = StringLen(str) - 1;
        while(end >= 0 && StringGetCharacter(str, end) == ' ') {
            end--;
        }
        
        if(start > end) return "";
        return StringSubstr(str, start, end - start + 1);
    }
    
public:
    CFileUtils(void) {
        m_logger = GlobalLogger;
    }
    
    //+------------------------------------------------------------------+
    //| File existence and information                                  |
    //+------------------------------------------------------------------+
    bool FileExists(string filename) {
        return FileIsExist(filename);
    }
    
    long GetFileSize(string filename) {
        if(!FileExists(filename)) return -1;
        
        int handle = FileOpen(filename, FILE_READ|FILE_BIN);
        if(handle == INVALID_HANDLE) return -1;
        
        long size = (long)FileSize(handle);
        FileClose(handle);
        return size;
    }
    
    datetime GetFileModifiedTime(string filename) {
        if(!FileExists(filename)) return 0;
        
        int handle = FileOpen(filename, FILE_READ|FILE_BIN);
        if(handle == INVALID_HANDLE) return 0;
        
        datetime modified = (datetime)FileGetInteger(handle, FILE_MODIFY_DATE);
        FileClose(handle);
        return modified;
    }
    
    //+------------------------------------------------------------------+
    //| Text file operations                                            |
    //+------------------------------------------------------------------+
    bool WriteTextFile(string filename, string content, bool append = false) {
        int flags = FILE_WRITE|FILE_TXT|FILE_ANSI;
        if(append) flags |= FILE_READ;
        
        int handle = FileOpen(filename, flags);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open file for writing: " + filename, "FileUtils");
            }
            return false;
        }
        
        if(append) {
            FileSeek(handle, 0, SEEK_END);
        }
        
        FileWrite(handle, content);
        FileClose(handle);
        return true;
    }
    
    bool ReadTextFile(string filename, string &content) {
        if(!FileExists(filename)) {
            if(m_logger != NULL) {
                m_logger.Error("File does not exist: " + filename, "FileUtils");
            }
            return false;
        }
        
        int handle = FileOpen(filename, FILE_READ|FILE_TXT|FILE_ANSI);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open file for reading: " + filename, "FileUtils");
            }
            return false;
        }
        
        content = "";
        while(!FileIsEnding(handle)) {
            content += FileReadString(handle) + "\n";
        }
        
        FileClose(handle);
        return true;
    }
    
    bool ReadTextFileLines(string filename, string &lines[]) {
        if(!FileExists(filename)) {
            if(m_logger != NULL) {
                m_logger.Error("File does not exist: " + filename, "FileUtils");
            }
            return false;
        }
        
        int handle = FileOpen(filename, FILE_READ|FILE_TXT|FILE_ANSI);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open file for reading: " + filename, "FileUtils");
            }
            return false;
        }
        
        ArrayResize(lines, 0);
        while(!FileIsEnding(handle)) {
            string line = FileReadString(handle);
            if(line != "") {
                int size = ArraySize(lines);
                ArrayResize(lines, size + 1);
                lines[size] = line;
            }
        }
        
        FileClose(handle);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| CSV file operations                                             |
    //+------------------------------------------------------------------+
    bool WriteCSVFile(string filename, string &headers[], string &data[][], string delimiter = ",") {
        int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, delimiter);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open CSV file for writing: " + filename, "FileUtils");
            }
            return false;
        }
        
        // Write headers
        string headerLine = "";
        for(int i = 0; i < ArraySize(headers); i++) {
            if(i > 0) headerLine += delimiter;
            headerLine += headers[i];
        }
        FileWrite(handle, headerLine);
        
        // Write data
        int rows = ArrayRange(data, 0);
        int cols = ArrayRange(data, 1);
        
        for(int row = 0; row < rows; row++) {
            string dataLine = "";
            for(int col = 0; col < cols; col++) {
                if(col > 0) dataLine += delimiter;
                dataLine += data[row][col];
            }
            FileWrite(handle, dataLine);
        }
        
        FileClose(handle);
        return true;
    }
    
    bool ReadCSVFile(string filename, string &data[][], string delimiter = ",", bool hasHeaders = true) {
        if(!FileExists(filename)) {
            if(m_logger != NULL) {
                m_logger.Error("CSV file does not exist: " + filename, "FileUtils");
            }
            return false;
        }
        
        string lines[];
        if(!ReadTextFileLines(filename, lines)) {
            return false;
        }
        
        int startLine = hasHeaders ? 1 : 0;
        int rowCount = ArraySize(lines) - startLine;
        if(rowCount <= 0) {
            ArrayResize(data, 0);
            return true;
        }
        
        // Determine column count from first data line
        string firstLine = lines[startLine];
        string testCols[];
        ushort delimiterChar = StringGetCharacter(delimiter, 0);
        int colCount = StringSplit(firstLine, delimiterChar, testCols);
        
        ArrayResize(data, rowCount, colCount);
        
        for(int row = 0; row < rowCount; row++) {
            string currentLine = lines[startLine + row];
            string columns[];
            int splitCount = StringSplit(currentLine, delimiterChar, columns);
            
            for(int col = 0; col < MathMin(colCount, splitCount); col++) {
                data[row][col] = columns[col];
            }
        }
        
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| Binary file operations                                          |
    //+------------------------------------------------------------------+
    bool WriteBinaryFile(string filename, const uchar &data[]) {
        int handle = FileOpen(filename, FILE_WRITE|FILE_BIN);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open binary file for writing: " + filename, "FileUtils");
            }
            return false;
        }
        
        FileWriteArray(handle, data);
        FileClose(handle);
        return true;
    }
    
    bool ReadBinaryFile(string filename, uchar &data[]) {
        if(!FileExists(filename)) {
            if(m_logger != NULL) {
                m_logger.Error("Binary file does not exist: " + filename, "FileUtils");
            }
            return false;
        }
        
        int handle = FileOpen(filename, FILE_READ|FILE_BIN);
        if(handle == INVALID_HANDLE) {
            if(m_logger != NULL) {
                m_logger.Error("Cannot open binary file for reading: " + filename, "FileUtils");
            }
            return false;
        }
        
        int size = (int)FileSize(handle);
        ArrayResize(data, size);
        FileReadArray(handle, data, 0, size);
        FileClose(handle);
        return true;
    }
    
    //+------------------------------------------------------------------+
    //| File management                                                 |
    //+------------------------------------------------------------------+
    bool DeleteFile(string filename) {
        if(!FileExists(filename)) return true;
        
        if(FileDelete(filename)) {
            return true;
        } else {
            if(m_logger != NULL) {
                m_logger.Error("Cannot delete file: " + filename, "FileUtils");
            }
            return false;
        }
    }
    
    bool MoveFile(string oldFilename, string newFilename) {
        if(!FileExists(oldFilename)) {
            if(m_logger != NULL) {
                m_logger.Error("Source file does not exist: " + oldFilename, "FileUtils");
            }
            return false;
        }
        
        if(FileMove(oldFilename, 0, newFilename, 0)) {
            return true;
        } else {
            if(m_logger != NULL) {
                m_logger.Error("Cannot move file from " + oldFilename + " to " + newFilename, "FileUtils");
            }
            return false;
        }
    }
    
    bool CopyFile(string sourceFilename, string destFilename) {
        if(!FileExists(sourceFilename)) {
            if(m_logger != NULL) {
                m_logger.Error("Source file does not exist: " + sourceFilename, "FileUtils");
            }
            return false;
        }
        
        // Read source file
        uchar data[];
        if(!ReadBinaryFile(sourceFilename, data)) {
            return false;
        }
        
        // Write to destination
        return WriteBinaryFile(destFilename, data);
    }
    
    //+------------------------------------------------------------------+
    //| Directory operations                                            |
    //+------------------------------------------------------------------+
    bool CreateDirectory(string dirPath) {
        ResetLastError();
        
        // In MQL5, directories are created automatically when you create a file in them
        // Just check if it exists or can be accessed
        string testFile = dirPath + "\\_temp_check.tmp";
        int handle = FileOpen(testFile, FILE_WRITE|FILE_BIN);
        if(handle != INVALID_HANDLE) {
            FileClose(handle);
            FileDelete(testFile);
            return true;
        }
        
        int error = GetLastError();
        if(m_logger != NULL) {
            m_logger.Error("Cannot create/access directory: " + dirPath + ", Error: " + (string)error, "FileUtils");
        }
        return false;
    }
    
    bool DirectoryExists(string dirPath) {
        // Try to open a file in the directory
        string testFile = dirPath + "\\_temp_check.tmp";
        int handle = FileOpen(testFile, FILE_READ|FILE_BIN);
        if(handle != INVALID_HANDLE) {
            FileClose(handle);
            return true;
        }
        
        // Also try to find files in the directory
        string filename;
        long findHandle = FileFindFirst(dirPath + "\\*", filename);
        if(findHandle != INVALID_HANDLE) {
            FileFindClose(findHandle);
            return true;
        }
        
        return false;
    }
    
    //+------------------------------------------------------------------+
    //| File search and listing                                         |
    //+------------------------------------------------------------------+
    int FindFiles(string pattern, string &results[]) {
        string filename;
        long handle;
        int count = 0;
        
        ArrayResize(results, 0);
        
        handle = FileFindFirst(pattern, filename);
        if(handle != INVALID_HANDLE) {
            do {
                int size = ArraySize(results);
                ArrayResize(results, size + 1);
                results[size] = filename;
                count++;
            } while(FileFindNext(handle, filename));
            
            FileFindClose(handle);
        }
        
        return count;
    }
    
    //+------------------------------------------------------------------+
    //| Configuration file operations                                   |
    //+------------------------------------------------------------------+
    bool WriteConfigValue(string filename, string section, string key, string value) {
        // Simple INI-style configuration
        string content;
        if(!ReadTextFile(filename, content)) {
            content = "";
        }
        
        // Implementation would parse and update INI-style content
        // This is a simplified version
        string newContent = content + StringFormat("\n[%s]\n%s=%s\n", section, key, value);
        return WriteTextFile(filename, newContent);
    }
    
    string ReadConfigValue(string filename, string section, string key, string defaultValue = "") {
        string content;
        if(!ReadTextFile(filename, content)) {
            return defaultValue;
        }
        
        // Simplified INI parsing
        string lines[];
        int count = StringSplit(content, '\n', lines);
        
        bool inSection = false;
        for(int i = 0; i < count; i++) {
            string line = lines[i];
            line = StringTrim(line); // Use custom trim function
            
            if(StringLen(line) > 0 && StringGetCharacter(line, 0) == '[' && StringGetCharacter(line, StringLen(line)-1) == ']') {
                string currentSection = StringSubstr(line, 1, StringLen(line)-2);
                inSection = (currentSection == section);
            } else if(inSection && StringFind(line, key + "=") == 0) {
                string parts[];
                if(StringSplit(line, '=', parts) >= 2) {
                    return parts[1];
                }
            }
        }
        
        return defaultValue;
    }
};

//+------------------------------------------------------------------+
//| Global file utils instance                                       |
//+------------------------------------------------------------------+
CFileUtils* GlobalFileUtils = NULL;

//+------------------------------------------------------------------+
//| File utils initialization                                        |
//+------------------------------------------------------------------+
void InitializeGlobalFileUtils() {
    if(GlobalFileUtils == NULL) {
        GlobalFileUtils = new CFileUtils();
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global file utils initialized", "FileUtils");
        }
    }
}

//+------------------------------------------------------------------+
//| File utils cleanup                                               |
//+------------------------------------------------------------------+
void CleanupGlobalFileUtils() {
    if(GlobalFileUtils != NULL) {
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global file utils cleanup", "FileUtils");
        }
        delete GlobalFileUtils;
        GlobalFileUtils = NULL;
    }
}

#endif