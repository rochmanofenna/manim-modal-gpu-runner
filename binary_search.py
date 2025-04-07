from manim import Scene, Text, Circle, Square, Triangle, VGroup, Axes, Dot, Create, FadeIn, FadeOut, Write, linear
from manim.utils.unit import UP, DOWN
from manim.utils.color import BLUE, GREEN, RED, YELLOW, WHITE
from math import pi as PI
import numpy as np
class SimpleAnimation(Scene):
    def construct(self):
        # Title
        title = Text("ManimGL Demo", font_size=70)
        self.play(Write(title), run_time=1.5)
        self.wait(0.5)
        self.play(title.animate.to_edge(UP), run_time=1)
        
        # Create basic shapes
        circle = Circle(radius=1, color=BLUE)
        square = Square(side_length=2, color=GREEN)
        triangle = Triangle().scale(1.5).set_color(RED)
        
        shapes = VGroup(circle, square, triangle).arrange(RIGHT, buff=1.5)
        shapes.next_to(title, DOWN, buff=1)
        
        # Display shapes one by one
        for shape in shapes:
            self.play(Create(shape), run_time=1)
        self.wait(0.5)
        
        # Move shapes around
        self.play(
            circle.animate.shift(DOWN * 1.5),
            square.animate.rotate(PI/4),
            triangle.animate.shift(UP * 1.5),
            run_time=1.5
        )
        self.wait(1)
        
        # Create some simple functions
        axes = Axes(
            x_range=(-3, 3, 1),
            y_range=(-2, 2, 1),
            height=4,
            width=8
        )
        axes.next_to(shapes, DOWN, buff=1)
        
        sin_graph = axes.get_graph(lambda x: np.sin(x), color=YELLOW)
        
        # Show the axes and the sine function
        self.play(Create(axes), run_time=1)
        self.play(Create(sin_graph), run_time=1.5)
        
        # Create a moving dot on the sine curve
        dot = Dot(color=WHITE)
        dot.move_to(axes.c2p(-3, np.sin(-3)))
        self.play(FadeIn(dot))
        
        # Animate the dot along the curve
        self.play(
            dot.animate.move_to(axes.c2p(3, np.sin(3))),
            run_time=3,
            rate_func=linear
        )
        self.wait(0.5)
        
        # Transition to the end
        end_text = Text("Thank You!", font_size=70, color=YELLOW)
        
        self.play(
            FadeOut(title),
            FadeOut(shapes),
            FadeOut(axes),
            FadeOut(sin_graph),
            FadeOut(dot),
            run_time=1
        )
        
        self.play(Write(end_text))
        self.wait(1)
        self.play(FadeOut(end_text), run_time=1)
