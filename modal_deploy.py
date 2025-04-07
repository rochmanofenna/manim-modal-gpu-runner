import modal
import os
import time
import shutil
import subprocess

app = modal.App("binary-search-animation")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ffmpeg", "build-essential", "pkg-config", "python3-dev",
        "libgl1-mesa-dev", "libegl1-mesa-dev", "libgles2-mesa-dev",
        "libglvnd-dev", "libglfw3-dev", "freeglut3-dev",
        "xvfb", "x11-utils",
        "libcairo2-dev", "libpango1.0-dev",
        "sox", "libsox-fmt-all",
        "texlive", "texlive-latex-extra", "texlive-fonts-extra",
        "texlive-latex-recommended", "texlive-science", "texlive-fonts-recommended"
    )
    .pip_install(
        "manimce", "numpy", "requests", "moviepy", "torch",
        "pycairo", "pyglet", "pydub", "moderngl", "moderngl-window",
        "screeninfo", "mapbox-earcut", "validators", "tqdm"
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
    cold_start_time = time.time()

    output_path = "/root/output/gpu"
    os.makedirs(output_path, exist_ok=True)

    gpu_available = torch.cuda.is_available()
    device_type = "GPU" if gpu_available else "CPU"
    gpu_info = torch.cuda.get_device_name(0) if gpu_available else "N/A"

    with open("/root/binary_search.py", "w", encoding="utf-8") as f:
        f.write(file_content)

    print(f"Animation file written, size: {os.path.getsize('/root/binary_search.py')} bytes")
    with open('/root/binary_search.py', 'r') as f:
        print(f"First 100 chars: {f.read(100)}")

    os.environ["DISPLAY"] = ":1"
    display_process = subprocess.Popen(["Xvfb", ":1", "-screen", "0", "1920x1080x24"])
    time.sleep(2)

    try:
        subprocess.check_call(["xdpyinfo", "-display", ":1"], stdout=subprocess.DEVNULL)
        print("Virtual display is running properly")
    except subprocess.CalledProcessError:
        print("Warning: Virtual display may not be running correctly")

    os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:/usr/lib/i386-linux-gnu"

    render_start_time = time.time()
    print(f"\nCold start duration: {render_start_time - cold_start_time:.2f} seconds")

    cmd = "cd /root && manim binary_search.py SimpleAnimation -pql"
    print(f"Running command: {cmd}")
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    print(f"Exit code: {process.returncode}")
    print(f"STDOUT: {process.stdout}")
    print(f"STDERR: {process.stderr}")

    render_duration = time.time() - render_start_time
    print(f"Render execution time: {render_duration:.2f} seconds")

    display_process.terminate()

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
        "exit_code": process.returncode
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

    for file in result["output_files"]:
        if file['path'].endswith(('.mp4', '.wav')):
            content = download_file.remote(file['full_path'])
            if content:
                output_path = os.path.join(local_output_dir, file['path'])
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(content)
                print(f"File is downloaded to {output_path}")
            else:
                print(f"File is downloaded to {file['path']}")

    print(f"\nAll files downloaded to {local_output_dir}")
