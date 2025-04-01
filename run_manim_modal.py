import modal
import time
import os
import sys
import shutil

# Create the Modal app
app = modal.App("manim-render")

# Define a Modal image with Manim dependencies
image = modal.Image.debian_slim().apt_install(
    "ffmpeg",
    "build-essential",
    "libcairo2-dev",
    "libpango1.0-dev",
    "sox",
    "pkg-config",
    "python3-dev",
    # Add LaTeX packages needed by Manim
    "texlive-latex-base",
    "texlive-latex-extra",
    "texlive-fonts-recommended",
    "texlive-fonts-extra",
    "texlive-xetex",
    "texlive-science",
    "texlive-plain-generic",
).pip_install(
    "manim",
    "numpy",
    "requests",
    "moviepy",
    "torch",
)

# Create volume to store output files
volume = modal.Volume.from_name("manim-outputs", create_if_missing=True)

# CPU version
@app.function(
    image=image,
    volumes={"/root/output": volume},
    timeout=1800,
)
def render_manim_cpu(file_content):
    import torch
    import time
    import os
    
    # Setup output directory
    output_path = "/root/output/cpu"
    os.makedirs(output_path, exist_ok=True)
    
    # Write file content to disk with UTF-8 encoding
    with open("/root/vid.py", "w", encoding="utf-8") as f:
        f.write(file_content)
    
    # Set Manim output path
    os.environ["MANIM_OUTPUT_PATH"] = output_path
    
    # Measure time and run Manim
    start_time = time.time()
    result = os.system("cd /root && python vid.py")
    elapsed_time = time.time() - start_time
    
    # Collect output files
    output_files = []
    for root, dirs, files in os.walk(output_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, output_path)
            file_size = os.path.getsize(file_path)
            output_files.append({
                "path": rel_path,
                "size": file_size
            })
    
    return {
        "device": "CPU",
        "elapsed_time": elapsed_time,
        "output_files": output_files,
        "exit_code": result
    }

# GPU version
@app.function(
    image=image,
    gpu="T4",
    volumes={"/root/output": volume},
    timeout=1800,
)
def render_manim_gpu(file_content):
    import torch
    import time
    import os
    
    # Setup output directory
    output_path = "/root/output/gpu"
    os.makedirs(output_path, exist_ok=True)
    
    # Check GPU availability
    gpu_available = torch.cuda.is_available()
    device_type = "GPU" if gpu_available else "CPU"
    gpu_info = "N/A"
    if gpu_available:
        gpu_info = f"{torch.cuda.get_device_name(0)} (CUDA {torch.version.cuda})"
    
    # Write file content to disk with UTF-8 encoding
    with open("/root/vid.py", "w", encoding="utf-8") as f:
        f.write(file_content)
    
    # Set Manim output path
    os.environ["MANIM_OUTPUT_PATH"] = output_path
    
    # Measure time and run Manim
    start_time = time.time()
    result = os.system("cd /root && python vid.py")
    elapsed_time = time.time() - start_time
    
    # Collect output files
    output_files = []
    for root, dirs, files in os.walk(output_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, output_path)
            file_size = os.path.getsize(file_path)
            output_files.append({
                "path": rel_path,
                "size": file_size
            })
    
    return {
        "device": device_type,
        "gpu_info": gpu_info,
        "elapsed_time": elapsed_time,
        "output_files": output_files,
        "exit_code": result
    }

@app.local_entrypoint()
def main():
    print("Starting Manim Modal renderer...")
    
    # Hardcoded path to vid.py in the same directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_file_path = os.path.join(script_dir, "vid.py")
    
    print(f"Using hardcoded path: {local_file_path}")
    
    if not os.path.exists(local_file_path):
        print(f"Error: File '{local_file_path}' not found.")
        return
    
    # Read file content with UTF-8 encoding
    with open(local_file_path, 'r', encoding="utf-8") as f:
        file_content = f.read()
    
    # Create local output directory
    local_output_dir = os.path.join(os.getcwd(), "manim_output")
    os.makedirs(local_output_dir, exist_ok=True)
    
    # Run on CPU
    print("\n=== Running Manim on CPU ===")
    try:
        cpu_result = render_manim_cpu.remote(file_content)
        print(f"CPU execution time: {cpu_result['elapsed_time']:.2f} seconds")
        print(f"Exit code: {cpu_result['exit_code']}")
        print(f"Found {len(cpu_result['output_files'])} output files")
        
        # Download CPU output files
        cpu_output_dir = os.path.join(local_output_dir, "cpu_output")
        os.makedirs(cpu_output_dir, exist_ok=True)
        
        # Fix for volume.partial_access() issue
        try:
            # Try the new method first
            for file_info in cpu_result['output_files']:
                source_path = os.path.join("/root/output/cpu", file_info['path'])
                dest_path = os.path.join(cpu_output_dir, file_info['path'])
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                # Use volume.fetch method instead of partial_access
                volume.fetch(source_path, dest_path)
                print(f"Downloaded: {file_info['path']}")
        except AttributeError:
            print("Note: Using alternative method to access volume files")
            # If the new method fails, try the old method
            for file_info in cpu_result['output_files']:
                source_path = os.path.join("/root/output/cpu", file_info['path'])
                dest_path = os.path.join(cpu_output_dir, file_info['path'])
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                # Copy the file using the app function
                copy_from_volume = app.function(volumes={"/root/output": volume})(lambda src, dst: shutil.copy(src, dst))
                copy_from_volume.remote(source_path, dest_path)
                print(f"Downloaded: {file_info['path']}")
    except Exception as e:
        print(f"CPU execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Run on GPU
    print("\n=== Running Manim on GPU ===")
    try:
        gpu_result = render_manim_gpu.remote(file_content)
        print(f"GPU execution time: {gpu_result['elapsed_time']:.2f} seconds")
        print(f"GPU info: {gpu_result['gpu_info']}")
        print(f"Exit code: {gpu_result['exit_code']}")
        print(f"Found {len(gpu_result['output_files'])} output files")
        
        # Download GPU output files
        gpu_output_dir = os.path.join(local_output_dir, "gpu_output")
        os.makedirs(gpu_output_dir, exist_ok=True)
        
        # Fix for volume.partial_access() issue
        try:
            # Try the new method first
            for file_info in gpu_result['output_files']:
                source_path = os.path.join("/root/output/gpu", file_info['path'])
                dest_path = os.path.join(gpu_output_dir, file_info['path'])
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                # Use volume.fetch method instead of partial_access
                volume.fetch(source_path, dest_path)
                print(f"Downloaded: {file_info['path']}")
        except AttributeError:
            print("Note: Using alternative method to access volume files")
            # If the new method fails, try the old method
            for file_info in gpu_result['output_files']:
                source_path = os.path.join("/root/output/gpu", file_info['path'])
                dest_path = os.path.join(gpu_output_dir, file_info['path'])
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                # Copy the file using the app function
                copy_from_volume = app.function(volumes={"/root/output": volume})(lambda src, dst: shutil.copy(src, dst))
                copy_from_volume.remote(source_path, dest_path)
                print(f"Downloaded: {file_info['path']}")
        
        # Calculate speedup
        if 'cpu_result' in locals() and cpu_result['elapsed_time'] > 0:
            speedup = cpu_result['elapsed_time'] / gpu_result['elapsed_time']
            print(f"\nGPU speedup: {speedup:.2f}x faster than CPU")
        
        # Check 10-second requirement
        if gpu_result['elapsed_time'] <= 10:
            print("\n✅ GPU acceleration meets the 10-second requirement!")
        else:
            print(f"\n❌ GPU execution took {gpu_result['elapsed_time']:.2f} seconds, exceeding the 10-second requirement.")
    except Exception as e:
        print(f"GPU execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print(f"\nOutput files are available in:\n- CPU: {cpu_output_dir}\n- GPU: {gpu_output_dir}")
    print("Script completed.")