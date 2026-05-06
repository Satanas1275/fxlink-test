import tkinter as tk
from tkinter import filedialog
import json
from PIL import Image

WIDTH = 30
HEIGHT = 19
PIXEL_SIZE = 20

class Editor:
    def __init__(self, root):
        self.root = root
        self.root.title("Éditeur PNG 30x19 Monochrome")

        self.grid = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
        self.drawing = False
        self.draw_value = 1

        self.canvas = tk.Canvas(root, width=WIDTH*PIXEL_SIZE, height=HEIGHT*PIXEL_SIZE)
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw_move)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)

        self.draw()

        frame = tk.Frame(root)
        frame.pack()

        tk.Button(frame, text="Clear", command=self.clear).pack(side=tk.LEFT)
        tk.Button(frame, text="Save JSON", command=self.save_json).pack(side=tk.LEFT)
        tk.Button(frame, text="Load (PNG/JSON)", command=self.load).pack(side=tk.LEFT)
        tk.Button(frame, text="Export PNG", command=self.export_png).pack(side=tk.LEFT)

    def draw(self):
        self.canvas.delete("all")
        for y in range(HEIGHT):
            for x in range(WIDTH):
                color = "black" if self.grid[y][x] else "white"
                self.canvas.create_rectangle(
                    x*PIXEL_SIZE,
                    y*PIXEL_SIZE,
                    (x+1)*PIXEL_SIZE,
                    (y+1)*PIXEL_SIZE,
                    fill=color,
                    outline="gray"
                )

    def set_pixel(self, x, y, value):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.grid[y][x] = value

    def start_draw(self, event):
        x = event.x // PIXEL_SIZE
        y = event.y // PIXEL_SIZE

        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.draw_value = 0 if self.grid[y][x] else 1
            self.set_pixel(x, y, self.draw_value)
            self.drawing = True
            self.draw()

    def draw_move(self, event):
        if not self.drawing:
            return

        x = event.x // PIXEL_SIZE
        y = event.y // PIXEL_SIZE
        self.set_pixel(x, y, self.draw_value)
        self.draw()

    def stop_draw(self, event):
        self.drawing = False

    def clear(self):
        self.grid = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
        self.draw()

    def save_json(self):
        file = filedialog.asksaveasfilename(defaultextension=".json")
        if file:
            with open(file, "w") as f:
                json.dump(self.grid, f)

    def export_png(self):
        file = filedialog.asksaveasfilename(defaultextension=".png")
        if not file:
            return

        img = Image.new("1", (WIDTH, HEIGHT))

        for y in range(HEIGHT):
            for x in range(WIDTH):
                img.putpixel((x, y), 0 if self.grid[y][x] else 1)

        img.save(file)

    def load(self):
        file = filedialog.askopenfilename()
        if not file:
            return

        # JSON
        if file.endswith(".json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if len(data) == HEIGHT and len(data[0]) == WIDTH:
                    self.grid = data
                    self.draw()
                else:
                    print("Taille invalide")

            except Exception as e:
                print("Erreur JSON :", e)

        # IMAGE
        else:
            try:
                img = Image.open(file).convert("L")
                img = img.resize((WIDTH, HEIGHT))

                self.grid = [
                    [
                        1 if img.getpixel((x, y)) < 128 else 0
                        for x in range(WIDTH)
                    ]
                    for y in range(HEIGHT)
                ]

                self.draw()

            except Exception as e:
                print("Erreur image :", e)


root = tk.Tk()
Editor(root)
root.mainloop()