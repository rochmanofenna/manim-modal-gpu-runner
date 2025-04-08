import modal
import os
import time
import shutil
import subprocess
import json

app = modal.App("binary-search-animation-v2")

image = (
    modal.Image.from_registry("python:3.11-slim-bullseye")
    .apt_install(
        "ffmpeg", "build-essential", "pkg-config", "python3-dev",
        "libgl1-mesa-dev", "libegl1-mesa-dev", "libgles2-mesa-dev",
        "libglvnd-dev", "libglfw3-dev", "freeglut3-dev",
        "xvfb", "x11-utils", "libcairo2-dev", "libpango1.0-dev",
        "sox", "libsox-fmt-all",
        "texlive", "texlive-latex-extra", "texlive-fonts-extra",
        "texlive-latex-recommended", "texlive-science", "texlive-fonts-recommended",
    )
    .run_commands(
        "apt-get update && apt-get install -y git",
        "pip install --upgrade pip",
        "pip install torch manim==0.14.0",
        "pip install moviepy",
        "pip install nvidia-ml-py3 psutil"  # Added for GPU monitoring
    )
)

volume = modal.Volume.from_name("manim-outputs", create_if_missing=True)

@app.function(
    image=image,
    gpu="A100",
    volumes={"/root/output": volume},
    timeout=1800,
)
def render_manim_gpu(file_content):
    import torch
    import threading
    import time
    import json
    from datetime import datetime
    
    try:
        import pynvml
        pynvml.nvmlInit()
    except ImportError:
        print("NVML library not available, trying nvidia-smi directly")
        pynvml = None
    
    cold_start_time = time.time()
    output_path = "/root/output/gpu"
    os.makedirs(output_path, exist_ok=True)
    
    # GPU info at startup
    gpu_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count() if gpu_available else 0
    device_type = "GPU" if gpu_available else "CPU"
    gpu_info = torch.cuda.get_device_name(0) if gpu_available else "N/A"
    
    print(f"CUDA Available: {gpu_available}")
    print(f"Device Count: {device_count}")
    print(f"Device Type: {device_type}")
    print(f"GPU Info: {gpu_info}")
    
    # Function to collect GPU metrics
    def collect_gpu_metrics(stop_event, metrics_file):
        metrics = []
        
        while not stop_event.is_set():
            timestamp = datetime.now().isoformat()
            metric_point = {"timestamp": timestamp}
            
            # Try to collect GPU metrics using NVML
            if pynvml and gpu_available:
                try:
                    for i in range(device_count):
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        
                        # Temperature
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        metric_point[f"gpu{i}_temp"] = temp
                        
                        # Utilization
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        metric_point[f"gpu{i}_util"] = util.gpu
                        metric_point[f"gpu{i}_mem_util"] = util.memory
                        
                        # Power usage
                        power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert from mW to W
                        metric_point[f"gpu{i}_power"] = power
                        
                        # Memory info
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        metric_point[f"gpu{i}_mem_used"] = mem_info.used / 1024**2  # MB
                        metric_point[f"gpu{i}_mem_total"] = mem_info.total / 1024**2  # MB
                        
                        # Clock speeds
                        sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                        mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                        metric_point[f"gpu{i}_sm_clock"] = sm_clock
                        metric_point[f"gpu{i}_mem_clock"] = mem_clock
                        
                except Exception as e:
                    print(f"Failed to collect GPU metrics via NVML: {e}")
                    metric_point["error"] = str(e)
            
            # If NVML fails or is not available, try nvidia-smi as a fallback
            elif gpu_available:
                try:
                    # Get GPU stats via nvidia-smi
                    nvidia_smi = subprocess.check_output(
                        ['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,power.draw,memory.used,memory.total',
                         '--format=csv,noheader,nounits'], 
                        universal_newlines=True
                    )
                    
                    values = nvidia_smi.strip().split(',')
                    if len(values) >= 6:
                        metric_point["gpu0_temp"] = float(values[0].strip())
                        metric_point["gpu0_util"] = float(values[1].strip())
                        metric_point["gpu0_mem_util"] = float(values[2].strip())
                        metric_point["gpu0_power"] = float(values[3].strip())
                        metric_point["gpu0_mem_used"] = float(values[4].strip())
                        metric_point["gpu0_mem_total"] = float(values[5].strip())
                    
                except Exception as e:
                    print(f"Failed to collect GPU metrics via nvidia-smi: {e}")
                    metric_point["error"] = str(e)
            
            metrics.append(metric_point)
            
            # Write current metrics to file
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            # Sleep for a bit before collecting next metrics
            time.sleep(0.5)
    
    # File to store metrics
    metrics_file = "/root/output/gpu/gpu_metrics.json"
    
    # Create and start the monitoring thread
    stop_monitoring = threading.Event()
    monitoring_thread = threading.Thread(
        target=collect_gpu_metrics, 
        args=(stop_monitoring, metrics_file)
    )
    monitoring_thread.daemon = True
    monitoring_thread.start()
    
    # Write animation file
    with open("/root/binary_search.py", "w", encoding="utf-8") as f:
        f.write(file_content)
    
    print(f"Animation file written, size: {os.path.getsize('/root/binary_search.py')} bytes")
    with open('/root/binary_search.py', 'r') as f:
        print(f"First 100 chars: {f.read(100)}")
    
    # Set up virtual display
    os.environ["DISPLAY"] = ":1"
    display_process = subprocess.Popen(["Xvfb", ":1", "-screen", "0", "1920x1080x24"])
    time.sleep(2)
    
    try:
        subprocess.check_call(["xdpyinfo", "-display", ":1"], stdout=subprocess.DEVNULL)
        print("Virtual display is running properly")
    except subprocess.CalledProcessError:
        print("Warning: Virtual display may not be running correctly")
    
    os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:/usr/lib/i386-linux-gnu"
    
    subprocess.run("pip show manim", shell=True)
    subprocess.run("python -c 'import manim; print(manim.__file__)'", shell=True)
    
    render_start_time = time.time()
    print(f"\nCold start duration: {render_start_time - cold_start_time:.2f} seconds")
    
    cmd = "cd /root && manim binary_search.py CombinedScene -pql"
    print(f"Running command: {cmd}")
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    print(f"Exit code: {process.returncode}")
    print(f"STDOUT: {process.stdout}")
    print(f"STDERR: {process.stderr}")
    
    # Stop GPU monitoring
    stop_monitoring.set()
    monitoring_thread.join(timeout=10)
    
    render_duration = time.time() - render_start_time
    print(f"Render execution time: {render_duration:.2f} seconds")
    
    # Generate GPU performance summary
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, 'r') as f:
                metrics_data = json.load(f)
                
            if metrics_data:
                # Calculate statistics
                temp_values = [m.get("gpu0_temp", 0) for m in metrics_data if "gpu0_temp" in m]
                util_values = [m.get("gpu0_util", 0) for m in metrics_data if "gpu0_util" in m]
                power_values = [m.get("gpu0_power", 0) for m in metrics_data if "gpu0_power" in m]
                mem_util_values = [m.get("gpu0_mem_util", 0) for m in metrics_data if "gpu0_mem_util" in m]
                
                summary = {
                    "gpu_metrics_summary": {
                        "samples_collected": len(metrics_data),
                        "temperature": {
                            "min": min(temp_values) if temp_values else "N/A",
                            "max": max(temp_values) if temp_values else "N/A",
                            "avg": sum(temp_values)/len(temp_values) if temp_values else "N/A"
                        },
                        "utilization": {
                            "min": min(util_values) if util_values else "N/A",
                            "max": max(util_values) if util_values else "N/A",
                            "avg": sum(util_values)/len(util_values) if util_values else "N/A"
                        },
                        "power": {
                            "min": min(power_values) if power_values else "N/A",
                            "max": max(power_values) if power_values else "N/A",
                            "avg": sum(power_values)/len(power_values) if power_values else "N/A"
                        },
                        "memory_utilization": {
                            "min": min(mem_util_values) if mem_util_values else "N/A",
                            "max": max(mem_util_values) if mem_util_values else "N/A",
                            "avg": sum(mem_util_values)/len(mem_util_values) if mem_util_values else "N/A"
                        }
                    }
                }
                
                # Write summary
                summary_file = "/root/output/gpu/gpu_summary.json"
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                print("\n=== GPU PERFORMANCE SUMMARY ===")
                print(f"Samples collected: {summary['gpu_metrics_summary']['samples_collected']}")
                print(f"Temperature: {summary['gpu_metrics_summary']['temperature']['min']}°C - {summary['gpu_metrics_summary']['temperature']['max']}°C (avg: {summary['gpu_metrics_summary']['temperature']['avg']:.1f}°C)")
                print(f"GPU Utilization: {summary['gpu_metrics_summary']['utilization']['min']}% - {summary['gpu_metrics_summary']['utilization']['max']}% (avg: {summary['gpu_metrics_summary']['utilization']['avg']:.1f}%)")
                print(f"Power Usage: {summary['gpu_metrics_summary']['power']['min']}W - {summary['gpu_metrics_summary']['power']['max']}W (avg: {summary['gpu_metrics_summary']['power']['avg']:.1f}W)")
                print(f"Memory Utilization: {summary['gpu_metrics_summary']['memory_utilization']['min']}% - {summary['gpu_metrics_summary']['memory_utilization']['max']}% (avg: {summary['gpu_metrics_summary']['memory_utilization']['avg']:.1f}%)")
                print("===============================")
        except Exception as e:
            print(f"Error processing GPU metrics: {e}")
    
    # Cleanup pynvml
    if pynvml:
        try:
            pynvml.nvmlShutdown()
        except:
            pass
    
    display_process.terminate()
    
    # Copy output files
    expected_output_dir = "/root/videos/BinarySearchExplanation/1080p30"
    found_mp4_files = []
    
    for root, _, files in os.walk("/root"):
        for file in files:
            if file.endswith(".mp4"):
                found_mp4_files.append(os.path.join(root, file))
    
    manim_output_dir = os.path.dirname(found_mp4_files[0]) if found_mp4_files else expected_output_dir
    
    output_file_paths = []
    if os.path.exists(manim_output_dir):
        for file in os.listdir(manim_output_dir):
            if file.endswith((".mp4", ".wav")):
                src, dst = os.path.join(manim_output_dir, file), os.path.join(output_path, file)
                shutil.copy2(src, dst)
                output_file_paths.append(dst)
    else:
        for mp4 in found_mp4_files:
            dst = os.path.join(output_path, os.path.basename(mp4))
            shutil.copy2(mp4, dst)
            output_file_paths.append(dst)
    
    output_files = []
    for root, _, files in os.walk(output_path):
        for file in files:
            file_path = os.path.join(root, file)
            output_files.append({
                "path": os.path.relpath(file_path, output_path),
                "size": os.path.getsize(file_path),
                "full_path": file_path
            })
    
    return {
        "device": device_type,
        "gpu_info": gpu_info,
        "elapsed_time": render_duration,
        "output_files": output_files,
        "exit_code": process.returncode,
        "gpu_metrics_file": "gpu_metrics.json" if os.path.exists(metrics_file) else None,
        "gpu_summary_file": "gpu_summary.json" if os.path.exists("/root/output/gpu/gpu_summary.json") else None
    }

@app.function(volumes={"/root/output": volume})
def download_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()
    return None

@app.local_entrypoint()
def main():
    print("Starting Binary Search Animation on Modal GPU...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    animation_path = os.path.join(script_dir, "binary_search.py")
    local_output_dir = os.path.join(script_dir, "downloaded_outputs")
    os.makedirs(local_output_dir, exist_ok=True)

    if not os.path.exists(animation_path):
        print("Animation file missing. Aborting.")
        return

    with open(animation_path, "r", encoding="utf-8") as f:
        file_content = f.read()

    result = render_manim_gpu.remote(file_content)
    print(f"GPU Execution Time: {result['elapsed_time']:.2f} seconds")
    print(f"GPU: {result['gpu_info']}")

    for file in result["output_files"]:
        print(f"- {file['path']} ({file['size'] / 1024 / 1024:.2f} MB)")

    # Download GPU metrics files first
    if result.get("gpu_metrics_file"):
        metrics_path = os.path.join("/root/output/gpu", result["gpu_metrics_file"])
        content = download_file.remote(metrics_path)
        if content:
            local_metrics_path = os.path.join(local_output_dir, result["gpu_metrics_file"])
            with open(local_metrics_path, "wb") as f:
                f.write(content)
            print(f"\nGPU metrics downloaded to {local_metrics_path}")
            
            # Print some metrics info
            try:
                with open(local_metrics_path, "r") as f:
                    metrics_data = json.load(f)
                print(f"Collected {len(metrics_data)} GPU metric samples")
            except:
                pass

    if result.get("gpu_summary_file"):
        summary_path = os.path.join("/root/output/gpu", result["gpu_summary_file"])
        content = download_file.remote(summary_path)
        if content:
            local_summary_path = os.path.join(local_output_dir, result["gpu_summary_file"])
            with open(local_summary_path, "wb") as f:
                f.write(content)
            print(f"GPU summary downloaded to {local_summary_path}")
            
            # Print summary
            try:
                with open(local_summary_path, "r") as f:
                    summary_data = json.load(f)
                
                print("\n=== GPU PERFORMANCE SUMMARY ===")
                summary = summary_data.get("gpu_metrics_summary", {})
                print(f"Samples: {summary.get('samples_collected', 'N/A')}")
                temp = summary.get('temperature', {})
                util = summary.get('utilization', {})
                power = summary.get('power', {})
                mem = summary.get('memory_utilization', {})
                
                print(f"Temperature: {temp.get('min')}°C - {temp.get('max')}°C (avg: {temp.get('avg', 0):.1f}°C)")
                print(f"GPU Utilization: {util.get('min')}% - {util.get('max')}% (avg: {util.get('avg', 0):.1f}%)")
                print(f"Power Usage: {power.get('min')}W - {power.get('max')}W (avg: {power.get('avg', 0):.1f}W)")
                print(f"Memory Utilization: {mem.get('min')}% - {mem.get('max')}% (avg: {mem.get('avg', 0):.1f}%)")
                print("===============================")
            except Exception as e:
                print(f"Error displaying summary: {e}")

    # Download other output files
    for file in result["output_files"]:
        if file['path'].endswith(('.mp4', '.wav')):
            content = download_file.remote(file['full_path'])
            if content:
                output_path = os.path.join(local_output_dir, file['path'])
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(content)
                print(f"File downloaded to {output_path}")
            else:
                print(f"Failed to download {file['path']}")

    print(f"\nAll files downloaded to {local_output_dir}")
    print("\nTo view the detailed GPU metrics, examine the gpu_metrics.json file")
    print("To see a quick summary, check the gpu_summary.json file")