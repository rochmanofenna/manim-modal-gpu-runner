from manim import *

class SimpleAudioScene(Scene):
    def construct(self):
        self.add_sound("assets/audio/intro.mp3")  # add your actual path
        text = Text("Audio Test Scene")
        self.play(Write(text))
        self.wait(1)