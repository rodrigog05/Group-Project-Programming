from functools import lru_cache
import pygame

PAPER = "#f4eee0"


@lru_cache(maxsize=16)
def font(size):
    return pygame.font.Font(None, size)


def label(screen, text, pos, size=21, color=PAPER, width=0):
    x, y = pos
    face = font(size)
    for paragraph in str(text).splitlines():
        line = ""
        for word in paragraph.split():
            potential = (line + " " + word).strip()
            if width and line and face.size(potential)[0] > width:
                screen.blit(face.render(line, True, color), (x, y))
                y += face.get_linesize()
                line = word
            else:
                line = potential
        screen.blit(face.render(line, True, color), (x, y))
        y += face.get_linesize()
    return y
