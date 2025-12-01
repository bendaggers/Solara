//+------------------------------------------------------------------+
//| ArrayUtils.mqh - Array utility functions for Solara              |
//+------------------------------------------------------------------+
#ifndef ARRAYUTILS_MQH
#define ARRAYUTILS_MQH

#include "Logger.mqh"
#include <Arrays\ArrayDouble.mqh>
#include <Arrays\ArrayInt.mqh>
#include <Arrays\ArrayString.mqh>

//+------------------------------------------------------------------+
//| CArrayUtils - Array utility class                                |
//+------------------------------------------------------------------+
class CArrayUtils {
private:
    CLogger* m_logger;
    
public:
    CArrayUtils(void) {
        m_logger = GlobalLogger;
    }
    
    //+------------------------------------------------------------------+
    //| Array copying and manipulation                                   |
    //+------------------------------------------------------------------+
    template<typename T>
    void ArrayCopy(const T &source[], T &destination[]) {
        int size = ArraySize(source);
        ArrayResize(destination, size);
        for(int i = 0; i < size; i++) {
            destination[i] = source[i];
        }
    }
    
    template<typename T>
    void ArrayAppend(T &array[], const T &values[]) {
        int oldSize = ArraySize(array);
        int addSize = ArraySize(values);
        ArrayResize(array, oldSize + addSize);
        
        for(int i = 0; i < addSize; i++) {
            array[oldSize + i] = values[i];
        }
    }
    
    template<typename T>
    void ArrayPrepend(T &array[], const T &values[]) {
        int oldSize = ArraySize(array);
        int addSize = ArraySize(values);
        ArrayResize(array, oldSize + addSize);
        
        // Shift existing elements
        for(int i = oldSize - 1; i >= 0; i--) {
            array[i + addSize] = array[i];
        }
        
        // Add new elements at beginning
        for(int i = 0; i < addSize; i++) {
            array[i] = values[i];
        }
    }
    
    //+------------------------------------------------------------------+
    //| Array searching                                                  |
    //+------------------------------------------------------------------+
    template<typename T>
    int ArrayFind(const T &array[], T value) {
        for(int i = 0; i < ArraySize(array); i++) {
            if(array[i] == value) {
                return i;
            }
        }
        return -1;
    }
    
    template<typename T>
    int ArrayFindLast(const T &array[], T value) {
        for(int i = ArraySize(array) - 1; i >= 0; i--) {
            if(array[i] == value) {
                return i;
            }
        }
        return -1;
    }
    
    template<typename T>
    bool ArrayContains(const T &array[], T value) {
        return ArrayFind(array, value) != -1;
    }
    
    //+------------------------------------------------------------------+
    //| Array statistics                                                 |
    //+------------------------------------------------------------------+
    double ArrayMin(const double &array[]) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        
        double minVal = array[0];
        for(int i = 1; i < size; i++) {
            if(array[i] < minVal) minVal = array[i];
        }
        return minVal;
    }
    
    double ArrayMax(const double &array[]) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        
        double maxVal = array[0];
        for(int i = 1; i < size; i++) {
            if(array[i] > maxVal) maxVal = array[i];
        }
        return maxVal;
    }
    
    double ArraySum(const double &array[]) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        
        double sum = 0;
        for(int i = 0; i < size; i++) {
            sum += array[i];
        }
        return sum;
    }
    
    double ArrayAverage(const double &array[]) {
        int size = ArraySize(array);
        if(size == 0) return 0;
        return ArraySum(array) / size;
    }
    
    //+------------------------------------------------------------------+
    //| Array sorting                                                    |
    //+------------------------------------------------------------------+
    template<typename T>
    void ArraySort(T &array[], bool ascending = true) {
        int size = ArraySize(array);
        for(int i = 0; i < size - 1; i++) {
            for(int j = i + 1; j < size; j++) {
                bool shouldSwap = ascending ? (array[i] > array[j]) : (array[i] < array[j]);
                if(shouldSwap) {
                    T temp = array[i];
                    array[i] = array[j];
                    array[j] = temp;
                }
            }
        }
    }
    
    //+------------------------------------------------------------------+
    //| Array filtering                                                  |
    //+------------------------------------------------------------------+
    template<typename T>
    void ArrayFilter(T &array[], T minValue, T maxValue) {
        int size = ArraySize(array);
        int writeIndex = 0;
        
        for(int readIndex = 0; readIndex < size; readIndex++) {
            if(array[readIndex] >= minValue && array[readIndex] <= maxValue) {
                if(writeIndex != readIndex) {
                    array[writeIndex] = array[readIndex];
                }
                writeIndex++;
            }
        }
        
        ArrayResize(array, writeIndex);
    }
    
    //+------------------------------------------------------------------+
    //| Array conversion                                                 |
    //+------------------------------------------------------------------+
    void DoubleArrayToString(const double &array[], string &result[], int digits = 2) {
        int size = ArraySize(array);
        ArrayResize(result, size);
        
        for(int i = 0; i < size; i++) {
            result[i] = DoubleToString(array[i], digits);
        }
    }
    
    void StringArrayToDouble(const string &array[], double &result[]) {
        int size = ArraySize(array);
        ArrayResize(result, size);
        
        for(int i = 0; i < size; i++) {
            result[i] = StringToDouble(array[i]);
        }
    }
    
    //+------------------------------------------------------------------+
    //| Array validation                                                 |
    //+------------------------------------------------------------------+
    template<typename T>
    bool ArrayIsValid(const T &array[]) {
        return ArraySize(array) > 0;
    }
    
    template<typename T>
    bool ArrayHasDuplicates(const T &array[]) {
        int size = ArraySize(array);
        for(int i = 0; i < size - 1; i++) {
            for(int j = i + 1; j < size; j++) {
                if(array[i] == array[j]) {
                    return true;
                }
            }
        }
        return false;
    }
    
    template<typename T>
    bool ArrayIsSorted(const T &array[], bool ascending = true) {
        int size = ArraySize(array);
        for(int i = 0; i < size - 1; i++) {
            if(ascending && array[i] > array[i + 1]) return false;
            if(!ascending && array[i] < array[i + 1]) return false;
        }
        return true;
    }
};

//+------------------------------------------------------------------+
//| Global array utils instance                                      |
//+------------------------------------------------------------------+
CArrayUtils* GlobalArrayUtils = NULL;

//+------------------------------------------------------------------+
//| Array utils initialization                                       |
//+------------------------------------------------------------------+
void InitializeGlobalArrayUtils() {
    if(GlobalArrayUtils == NULL) {
        GlobalArrayUtils = new CArrayUtils();
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global array utils initialized", "ArrayUtils");
        }
    }
}

//+------------------------------------------------------------------+
//| Array utils cleanup                                              |
//+------------------------------------------------------------------+
void CleanupGlobalArrayUtils() {
    if(GlobalArrayUtils != NULL) {
        if(GlobalLogger != NULL) {
            GlobalLogger.Info("Global array utils cleanup", "ArrayUtils");
        }
        delete GlobalArrayUtils;
        GlobalArrayUtils = NULL;
    }
}

#endif