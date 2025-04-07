from manim import Scene, Text, Circle, Square, VGroup, Create, FadeOut, Write
from manim.constants import LEFT, RIGHT
from manim.utils.color import BLUE, GREEN

class LongAnimation(Scene):
    def construct(self):
        title = Text("ManimGL GPU Render Test").scale(0.7)
        self.play(Write(title), run_time=2)
        self.wait(1)

        for i in range(30):  # Each iteration ~4 seconds
            circ = Circle(radius=1).shift(LEFT).set_color(BLUE)
            sq = Square().shift(RIGHT).set_color(GREEN)
            self.play(Create(circ), Create(sq), run_time=1.5)
            self.play(circ.animate.shift(RIGHT), sq.animate.shift(LEFT), run_time=1.5)
            self.play(FadeOut(circ), FadeOut(sq), run_time=1)

        self.wait(1)
