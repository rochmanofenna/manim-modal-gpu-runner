import modal
import os
import time
import shutil
import subprocess

# Create a Modal app
app = modal.App("binary-search-animation")

# Define the GPU-optimized image with all required dependencies
image = (
    modal.Image.debian_slim()
    # First install system dependencies
    .apt_install(
        # Base requirements
        "ffmpeg",
        "build-essential",
        "pkg-config",
        "python3-dev",
        # OpenGL and graphics dependencies
        "libgl1-mesa-dev",
        "libegl1-mesa-dev",
        "libgles2-mesa-dev",
        "libglvnd-dev",
        "libglfw3-dev",
        "freeglut3-dev",
        # X11 dependencies
        "xvfb",
        "x11-utils",
        # Cairo and text rendering
        "libcairo2-dev",
        "libpango1.0-dev",
        # Audio processing
        "sox",
        "libsox-fmt-all",
        # LaTeX packages
        "texlive",
        "texlive-latex-extra",
        "texlive-fonts-extra",
        "texlive-latex-recommended",
        "texlive-science",
        "texlive-fonts-recommended",
    )
    # Then install Python packages
    .pip_install(
        # Core dependencies
        "manimgl==1.7.2",
        "numpy",
        "requests",
        "moviepy",
        "torch",
        # Additional dependencies
        "pycairo",
        "pyglet",
        "pydub",
        "moderngl",
        "moderngl-window",
        "screeninfo",
        "mapbox-earcut",
        "validators",
        "tqdm",
    )
)

# Create a persistent volume for output storage
volume = modal.Volume.from_name("manim-outputs", create_if_missing=True)

# GPU-accelerated function
@app.function(
    image=image,
    gpu="A100",
    volumes={"/root/output": volume},
    timeout=1800,
)
def render_manim_gpu(file_content):
    import torch
    import os
    import subprocess
    import time
    import shutil
    
    # Make sure the output directory exists
    output_path = "/root/output/gpu"
    os.makedirs(output_path, exist_ok=True)
    
    # Check GPU status
    gpu_available = torch.cuda.is_available()
    device_type = "GPU" if gpu_available else "CPU"
    gpu_info = torch.cuda.get_device_name(0) if gpu_available else "N/A"
    
    # Write animation file to disk
    with open("/root/binary_search.py", "w", encoding="utf-8") as f:
        f.write(file_content)
    
    # Print file contents for debugging
    print(f"Animation file written, size: {os.path.getsize('/root/binary_search.py')} bytes")
    with open('/root/binary_search.py', 'r') as f:
        print(f"First 100 chars: {f.read(100)}")
    
    # Set up virtual display
    os.environ["DISPLAY"] = ":1"
    display_process = subprocess.Popen(["Xvfb", ":1", "-screen", "0", "1920x1080x24"])
    time.sleep(2)  # Give more time for Xvfb to initialize
    
    # Check if Xvfb is running
    try:
        subprocess.check_call(["xdpyinfo", "-display", ":1"], stdout=subprocess.DEVNULL)
        print("Virtual display is running properly")
    except subprocess.CalledProcessError:
        print("Warning: Virtual display may not be running correctly")
    
    # Set library paths for OpenGL
    os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:/usr/lib/i386-linux-gnu"
    
    # Measure execution time
    start_time = time.time()
    
    # Run the animation with more detailed output
    cmd = "cd /root && PYTHONPATH=/root manimgl binary_search.py SimpleAnimation -o"
    print(f"Running command: {cmd}")
    
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"Exit code: {process.returncode}")
    print(f"STDOUT: {process.stdout}")
    print(f"STDERR: {process.stderr}")
    
    elapsed_time = time.time() - start_time
    
    # Clean up display
    display_process.terminate()
    
    # Check ManimGL output directories
    expected_manim_output_dir = "/root/videos/BinarySearchExplanation/1080p30"
    print("Checking output directories...")
    print(f"Manim output dir exists: {os.path.exists(expected_manim_output_dir)}")
    
    # Search for output files more thoroughly
    found_mp4_files = []
    for root, dirs, files in os.walk("/root"):
        for file in files:
            if file.endswith(".mp4"):
                found_mp4_files.append(os.path.join(root, file))
                print(f"Found MP4: {os.path.join(root, file)}")
    
    # If we found any MP4 files, use the first one's directory as our manim_output_dir
    if found_mp4_files:
        manim_output_dir = os.path.dirname(found_mp4_files[0])
    else:
        manim_output_dir = expected_manim_output_dir
    
    # Copy output files to the volume
    output_file_paths = []
    
    if os.path.exists(manim_output_dir):
        print(f"Files in manim output dir: {os.listdir(manim_output_dir)}")
        for file in os.listdir(manim_output_dir):
            if file.endswith(".mp4") or file.endswith(".wav"):
                src_path = os.path.join(manim_output_dir, file)
                dst_path = os.path.join(output_path, file)
                print(f"Copying {src_path} to {dst_path}")
                shutil.copy2(src_path, dst_path)
                output_file_paths.append(dst_path)
                print(f"Copied output file to {dst_path}")
    else:
        print(f"Warning: Expected output directory {manim_output_dir} doesn't exist")
        # Try to find alternative output locations
        for mp4_file in found_mp4_files:
            dst_path = os.path.join(output_path, os.path.basename(mp4_file))
            print(f"Copying from alternate location: {mp4_file} to {dst_path}")
            shutil.copy2(mp4_file, dst_path)
            output_file_paths.append(dst_path)
    
    # List all files in the output volume directory
    print(f"Files in output volume directory: {os.listdir(output_path)}")
    
    # Collect output files
    output_files = []
    for root, dirs, files in os.walk(output_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, output_path)
            size_bytes = os.path.getsize(file_path)
            output_files.append({
                "path": rel_path, 
                "size": size_bytes,
                "full_path": file_path
            })
    
    return {
        "device": device_type,
        "gpu_info": gpu_info,
        "elapsed_time": elapsed_time,
        "output_files": output_files,
        "exit_code": process.returncode
    }

# Function to download file from the volume to local machine
@app.function(
    volumes={"/root/output": volume},
)
def download_file(file_path):
    import os
    print(f"Attempting to download {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    if os.path.exists(file_path):
        print(f"File size: {os.path.getsize(file_path)} bytes")
        with open(file_path, "rb") as f:
            content = f.read()
            print(f"Read {len(content)} bytes")
            return content
    else:
        print(f"ERROR: File {file_path} does not exist")
        # List parent directory contents
        parent_dir = os.path.dirname(file_path)
        if os.path.exists(parent_dir):
            print(f"Contents of {parent_dir}:")
            for item in os.listdir(parent_dir):
                full_path = os.path.join(parent_dir, item)
                size = os.path.getsize(full_path) if os.path.isfile(full_path) else "DIR"
                print(f"  - {item} ({size})")
        else:
            print(f"Parent directory {parent_dir} does not exist")
        return None

# Local Entry Point
@app.local_entrypoint()
def main():
    print("Starting Binary Search Animation on Modal GPU...")
    
    # Read the animation script from the current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    animation_file_path = os.path.join(script_dir, "binary_search.py")
    
    # Create local directory for downloads
    local_output_dir = os.path.join(script_dir, "downloaded_outputs")
    os.makedirs(local_output_dir, exist_ok=True)
    
    # If the file doesn't exist yet, create it
    if not os.path.exists(animation_file_path):
        print(f"Animation file not found at {animation_file_path}. Creating default animation file.")
        # Here you would include your default binary search animation code
        # For this example, I'll assume it's already defined
        return
    
    with open(animation_file_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    
    print("\n=== Running ManimGL on GPU ===")
    try:
        gpu_result = render_manim_gpu.remote(file_content)
        print(f"GPU Execution Time: {gpu_result['elapsed_time']:.2f} seconds")
        print(f"GPU: {gpu_result['gpu_info']}")
        print(f"Exit Code: {gpu_result['exit_code']}")
        print(f"Generated {len(gpu_result['output_files'])} output files")
        
        # Print all output files
        for file_info in gpu_result['output_files']:
            print(f"- {file_info['path']} ({file_info['size'] / 1024 / 1024:.2f} MB)")
        
        # Download the files to local machine
        print("\n=== Downloading files to local machine ===")
        for file_info in gpu_result['output_files']:
            if file_info['path'].endswith('.mp4') or file_info['path'].endswith('.wav'):
                print(f"Downloading {file_info['path']}...")
                file_content = download_file.remote(file_info['full_path'])
                if file_content is not None:
                    local_file_path = os.path.join(local_output_dir, file_info['path'])
                    
                    # Create directories if needed
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    
                    # Save the file locally
                    with open(local_file_path, "wb") as f:
                        f.write(file_content)
                    
                    print(f"✅ Downloaded to {local_file_path}")
                else:
                    print(f"❌ Failed to download {file_info['path']}")
        
        print(f"\nAll files downloaded to {local_output_dir}")
        
        if gpu_result["elapsed_time"] <= 60:
            print("✅ Animation rendering completed in under a minute!")
        else:
            print(f"⚠️ Rendering took {gpu_result['elapsed_time']:.2f} seconds")
    
    except Exception as e:
        print(f"GPU Execution Failed: {str(e)}")
        import traceback
        traceback.print_exc()