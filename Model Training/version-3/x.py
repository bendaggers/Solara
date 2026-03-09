import psutil
import subprocess
import time
from threading import Thread
import ctypes
import struct

# --- Configuration ---
MONITOR_DURATION = 60  # seconds
INTERVAL = 1           # seconds between readings

# Lists to store usage data
cpu_usage_list = []
cpu_temp_list = []
gpu_usage_list = []
gpu_temp_list = []

# Flag to control monitoring loop
monitoring = True

# --- HWInfo Shared Memory Setup ---
HWINFO_SIZE = 2048
SHARED_MEMORY_NAME = "Global\\HWiNFO_SENSORS"  # default shared memory

def read_hwinfo_cpu_temp():
    """Read CPU temperature from HWInfo shared memory (first core as example)."""
    try:
        hmap = ctypes.windll.kernel32.OpenFileMappingW(0x0004, False, SHARED_MEMORY_NAME)
        if not hmap:
            return None
        ptr = ctypes.windll.kernel32.MapViewOfFile(hmap, 0x0004, 0, 0, HWINFO_SIZE)
        if not ptr:
            ctypes.windll.kernel32.CloseHandle(hmap)
            return None
        # Example: read first 2 bytes as CPU temp (HWInfo scale: x10)
        raw_data = ctypes.string_at(ptr, 2)
        cpu_temp = struct.unpack("H", raw_data)[0] / 10.0
        ctypes.windll.kernel32.UnmapViewOfFile(ptr)
        ctypes.windll.kernel32.CloseHandle(hmap)
        return cpu_temp
    except Exception:
        return None

# --- CPU Monitoring Function ---
def monitor_cpu():
    while monitoring:
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_usage_list.append(cpu_percent)

        cpu_temp = read_hwinfo_cpu_temp()
        if cpu_temp is not None:
            cpu_temp_list.append(cpu_temp)
        else:
            cpu_temp_list.append(0)
        time.sleep(INTERVAL)

# --- GPU Monitoring Function ---
def monitor_gpu():
    while monitoring:
        try:
            # GPU usage
            usage_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            gpu_usage_list.append(int(usage_result.stdout.strip()))

            # GPU temperature
            temp_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            gpu_temp_list.append(int(temp_result.stdout.strip()))
        except Exception:
            gpu_usage_list.append(0)
            gpu_temp_list.append(0)
        time.sleep(INTERVAL)

# --- Start monitoring threads ---
cpu_thread = Thread(target=monitor_cpu)
gpu_thread = Thread(target=monitor_gpu)
cpu_thread.start()
gpu_thread.start()

print(f"Monitoring CPU & GPU usage and temperatures for {MONITOR_DURATION} seconds...")
time.sleep(MONITOR_DURATION)

# --- Stop monitoring ---
monitoring = False
cpu_thread.join()
gpu_thread.join()

# --- Compute and display averages ---
if cpu_usage_list:
    print(f"\nAverage CPU Usage: {sum(cpu_usage_list)/len(cpu_usage_list):.2f}%")
else:
    print("\nNo CPU usage recorded.")

if cpu_temp_list and any(cpu_temp_list):
    print(f"Average CPU Temperature: {sum(cpu_temp_list)/len(cpu_temp_list):.2f} °C")
else:
    print("CPU Temperature not available. Make sure HWInfo is running in Sensors-only mode with Shared Memory enabled.")

if gpu_usage_list:
    print(f"Average GPU Usage: {sum(gpu_usage_list)/len(gpu_usage_list):.2f}%")
else:
    print("No GPU usage recorded.")

if gpu_temp_list:
    print(f"Average GPU Temperature: {sum(gpu_temp_list)/len(gpu_temp_list):.2f} °C")
else:
    print("No GPU temperature recorded.")