import numpy as np
from PIL import Image
import moderngl
from moderngl_window.timers.clock import Timer

class RenderBackend:
    def __init__(self, backend='egl'):
        self.backend = backend.lower()
        self.ctx = self.create_context()
        self.used_fallback = False

    def create_context(self):
        if self.backend == 'egl':
            try:
                print("Trying EGL backend")
                return moderngl.create_standalone_context(require=330, backend="egl")
            except Exception as e:
                print(f"EGL context failed, falling back: {e}")
                return self.create_fallback()
        else:
            return self.create_fallback()

    def create_fallback(self):
        print("Falling back to CPU/software OpenGL context")
        self.used_fallback = True
        return moderngl.create_standalone_context(require=330)

class EGLWindow:
    def __init__(self, backend='egl', size=(640, 480), samples=0, scene=None):
        self.backend = backend.lower()
        self.size = size
        self.scene = scene
        self.renderer = RenderBackend(backend=self.backend)
        self.ctx = self.renderer.ctx
        self.used_fallback = self.renderer.used_fallback

        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture(self.size, components=3)]
        )
        self.timer = Timer()
        self.timer.start()

        if self.scene:
            self._inject_context()

    def _inject_context(self):
        self.scene.ctx = self.ctx
        self.scene.fbo = self.fbo
        self.scene.window = self
        self.scene.timer = self.timer

    def render_scene(self):
        self.fbo.use()
        self.fbo.clear(0.0, 1.0, 0.0)
        if self.scene:
            self.scene.render_frame()

    def render(self):
        self.fbo.use()
        self.fbo.clear(0.0, 0.0, 0.0)
        if self.scene:
            self.scene.render_frame()

    def save_image(self, filename="framebuffer_output.png"):
        data = self.fbo.read(components=3)
        image = Image.frombytes('RGB', self.size, data)
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image.save(filename)

    def swap_buffers(self):
        pass