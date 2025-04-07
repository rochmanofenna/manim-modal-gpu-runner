How to Run

1. Clone the Repository

git clone <your-repo-url>
cd <repo-name>

2. Set Up the Environment

If you don’t have requirements.txt:

pip freeze > requirements.txt

Then install dependencies:

pip install -r requirements.txt

3. (Optional) Test EGL Context Locally

python src/render/egl_window.py

4. Run on Modal

First, install the Modal CLI and log in:

pip install modal
modal token new

Then run the pipeline:

modal run modal_deploy.py

5. Output

Rendered video files will appear in the downloaded_outputs/ folder as .mp4 files.

Example:
	•	SimpleAnimation.mp4 — rendered in ~9.02 seconds on NVIDIA A100


