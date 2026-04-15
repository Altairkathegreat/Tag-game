

"""
╔══════════════════════════════════════════════════════════════════╗
║              N E O N   T A G  —  2-Player Local                 ║
║  Beautiful 2D tag game with 5 game modes & uncommon mechanics    ║
╚══════════════════════════════════════════════════════════════════╝
 
INSTALL:  pip install pygame numpy
RUN:      python tag_game.py
 
PLAYER 1 (Crimson):  WASD to move  |  Q = Dodge  |  E = Special
PLAYER 2 (Cyan):     Arrow Keys     |  RSHIFT = Dodge  |  RCTRL = Special
"""
 
import pygame
import sys
import math
import random
 
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
 
W, H = 1280, 720
FPS  = 60
 
# ── Palette ────────────────────────────────────────────────────────
C = {
    "bg":       (4,   6,  20),
    "bg2":      (8,  12,  35),
    "grid":     (15, 22,  55),
    "p1":       (255, 60,  90),
    "p1_dark":  (120, 20,  40),
    "p1_glow":  (255,100, 130),
    "p2":       (0,  220, 255),
    "p2_dark":  (0,   80, 120),
    "p2_glow":  (100, 240, 255),
    "tag":      (255, 200,   0),
    "white":    (255, 255, 255),
    "gray":     (80,  90, 120),
    "dk_gray":  (20,  25,  50),
    "green":    (0,  255, 140),
    "purple":   (160, 80, 255),
    "orange":   (255, 140,   0),
}
 
# ── Sound synthesis ────────────────────────────────────────────────
try:
    import numpy as np
 
    def _make_sound(freq=440, dur=0.12, wave="sine", vol=0.28, decay=True):
        sr = 44100
        n  = int(sr * dur)
        t  = [i / sr for i in range(n)]
        if wave == "sine":
            data = [math.sin(2 * math.pi * freq * x) for x in t]
        elif wave == "square":
            data = [1.0 if math.sin(2 * math.pi * freq * x) > 0 else -1.0 for x in t]
        else:
            data = [random.uniform(-1, 1) for _ in t]
        if decay:
            data = [data[i] * ((n - i) / n) ** 2 for i in range(n)]
        arr  = np.array(data, dtype=np.float32)
        arr  = (arr * vol * 32767).astype(np.int16)
        stereo = np.column_stack([arr, arr])
        return pygame.sndarray.make_sound(stereo)
 
    SFX = {
        "tag":   _make_sound(880, 0.18, "square", 0.22),
        "dodge": _make_sound(440, 0.12, "sine",   0.18),
        "click": _make_sound(660, 0.07, "sine",   0.14),
        "win":   _make_sound(523, 0.38, "sine",   0.28),
        "boost": _make_sound(220, 0.10, "noise",  0.13),
        "spawn": _make_sound(330, 0.14, "sine",   0.18),
    }
    SOUND_OK = True
except Exception:
    SOUND_OK = False
    class _DummySound:
        def play(self): pass
    _d = _DummySound()
    SFX = {k: _d for k in ("tag","dodge","click","win","boost","spawn")}
 
 
# ══════════════════════════════════════════════════════════════════
#  PARTICLES
# ══════════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ("x","y","vx","vy","color","size","life","max_life")
    def __init__(self, x, y, color, vx, vy, size, life):
        self.x, self.y  = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.color = color
        self.size  = size
        self.life  = life
        self.max_life = life
 
    def update(self, dt):
        self.x    += self.vx
        self.y    += self.vy
        self.vy   += 0.12
        self.life -= dt
        self.size *= 0.975
 
    @property
    def alive(self):
        return self.life > 0 and self.size > 0.4
 
    def draw(self, surf):
        a = max(0.0, self.life / self.max_life)
        r = max(0, min(255, int(self.color[0] * a)))
        g = max(0, min(255, int(self.color[1] * a)))
        b = max(0, min(255, int(self.color[2] * a)))
        pygame.draw.circle(surf, (r, g, b),
                           (int(self.x), int(self.y)), max(1, int(self.size)))
 
 
class PS:          # ParticleSystem
    def __init__(self):
        self.particles = []
 
    def burst(self, x, y, color, n=28):
        for _ in range(n):
            a  = random.uniform(0, math.tau)
            sp = random.uniform(1.5, 7.5)
            self.particles.append(Particle(
                x, y, color,
                math.cos(a)*sp, math.sin(a)*sp,
                random.uniform(3, 8), random.uniform(0.5, 1.2)
            ))
 
    def trail(self, x, y, color):
        self.particles.append(Particle(
            x, y, color,
            random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4),
            random.uniform(2, 4), 0.22
        ))
 
    def emit(self, x, y, color, n=6, **kw):
        for _ in range(n):
            self.particles.append(Particle(
                x, y, color,
                kw.get("vx", random.uniform(-2, 2)),
                kw.get("vy", random.uniform(-3, 0.5)),
                kw.get("size", random.uniform(2, 5)),
                kw.get("life", random.uniform(0.4, 0.9))
            ))
 
    def update(self, dt):
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update(dt)
 
    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)
 
 
# ══════════════════════════════════════════════════════════════════
#  DRAW HELPERS
# ══════════════════════════════════════════════════════════════════
def glow_circle(surf, color, pos, r, layers=4, step=35):
    gs = pygame.Surface((r*4+4, r*4+4), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        ri = int(r * (1 + i*0.38))
        a  = min(180, step * (layers - i + 1))
        pygame.draw.circle(gs, (*color, a), (r*2+2, r*2+2), ri)
    surf.blit(gs, (pos[0]-r*2-2, pos[1]-r*2-2))
    pygame.draw.circle(surf, color, pos, r)
 
 
def glow_rect(surf, color, rect, rr=4, gs=7):
    s = pygame.Surface((rect.w+gs*2, rect.h+gs*2), pygame.SRCALPHA)
    for i in range(gs, 0, -1):
        a  = int(110*(gs-i+1)/gs)
        gr = pygame.Rect(gs-i, gs-i, rect.w+i*2, rect.h+i*2)
        pygame.draw.rect(s, (*color, a), gr, border_radius=rr+i)
    surf.blit(s, (rect.x-gs, rect.y-gs))
    pygame.draw.rect(surf, color, rect, border_radius=rr)
 
 
def text_center(surf, txt, font, color, y):
    s  = font.render(txt, True, (0,0,0))
    surf.blit(s, (W//2 - s.get_width()//2+2, y+2))
    t  = font.render(txt, True, color)
    surf.blit(t, (W//2 - t.get_width()//2, y))
 
 
def scanlines(surf):
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, 4):
        pygame.draw.line(s, (0,0,0,18), (0,y), (W,y))
    surf.blit(s, (0,0))
 
 
def vignette(surf):
    v = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(0, 320, 22):
        a  = int(55*i/320)
        ew = W - i*2
        eh = H - i*2
        if ew > 0 and eh > 0:
            pygame.draw.ellipse(v, (0,0,0,a), (i, i, ew, eh), 22)
    surf.blit(v, (0,0))
 
 
# ══════════════════════════════════════════════════════════════════
#  MAPS
# ══════════════════════════════════════════════════════════════════
class Map:
    def __init__(self, name, color, walls, zones=None, bg="grid"):
        self.name  = name
        self.color = color
        self.walls = [pygame.Rect(*w) for w in walls]
        self.zones = zones or []      # [(rect_tuple, "slow"|"boost")]
        self.bg    = bg
 
    def draw_bg(self, surf):
        surf.fill(C["bg"])
        if self.bg == "grid":
            for x in range(0, W, 60):
                pygame.draw.line(surf, C["grid"], (x,0), (x,H))
            for y in range(0, H, 60):
                pygame.draw.line(surf, C["grid"], (0,y), (W,y))
        elif self.bg == "hex":
            sz = 40
            for row in range(H//sz+3):
                for col in range(W//sz+3):
                    cx = col*sz*1.5
                    cy = row*sz*math.sqrt(3) + (col%2)*sz*math.sqrt(3)/2
                    pts = [(cx + sz*0.38*math.cos(math.pi/3*i),
                            cy + sz*0.38*math.sin(math.pi/3*i)) for i in range(6)]
                    pygame.draw.polygon(surf, C["grid"], pts, 1)
        elif self.bg == "dots":
            for x in range(0, W, 40):
                for y in range(0, H, 40):
                    pygame.draw.circle(surf, C["grid"], (x,y), 2)
        elif self.bg == "diag":
            for i in range(-H, W+H, 40):
                pygame.draw.line(surf, C["grid"], (i,0), (i+H,H))
 
    def draw(self, surf):
        self.draw_bg(surf)
        for zr, zt in self.zones:
            r  = pygame.Rect(*zr)
            zc = C["green"] if zt=="slow" else C["purple"]
            s  = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill((*zc, 28))
            surf.blit(s, r.topleft)
            pygame.draw.rect(surf, (*zc, 70), r, 1)
        for w in self.walls:
            glow_rect(surf, self.color, w, rr=3, gs=6)
            inner = w.inflate(-4,-4)
            if inner.w>0 and inner.h>0:
                s = pygame.Surface((inner.w, inner.h), pygame.SRCALPHA)
                s.fill((*C["white"],18))
                surf.blit(s, inner.topleft)
 
    def zone_at(self, pos):
        for zr, zt in self.zones:
            if pygame.Rect(*zr).collidepoint(pos):
                return zt
        return None
 
 
MAPS = [
    Map("NEON ARENA", C["purple"], [
        (100,100,200,18),(980,100,200,18),(100,600,200,18),(980,600,200,18),
        (575,278,130,18),(575,424,130,18),(298,338,18,104),(964,338,18,104)],
        bg="grid"),
    Map("HEX MAZE", C["green"], [
        (198,148,18,205),(398,148,18,155),(598,198,18,155),(798,148,18,205),(998,148,18,205),
        (198,448,18,205),(398,498,18,155),(598,448,18,155),(798,448,18,205),(998,448,18,205),
        (298,338,205,18),(698,338,205,18),(148,338,82,18),(1050,338,82,18)],
        zones=[((298,278,105,105),"slow"),((878,278,105,105),"boost")], bg="hex"),
    Map("VOID CROSS", C["orange"], [
        (158,158,308,18),(158,158,18,308),(820,158,308,18),(1108,158,18,308),
        (158,558,308,18),(158,418,18,158),(820,558,308,18),(1108,418,18,158),
        (538,298,205,18),(538,398,205,18),(538,298,18,118),(728,298,18,118)],
        bg="diag"),
    Map("STAR FIELD", C["p1"], [
        (198,198,125,18),(958,198,125,18),(198,498,125,18),(958,498,125,18),
        (578,148,125,18),(578,548,125,18),(348,338,18,82),(908,338,18,82),(578,338,125,18)],
        zones=[((498,288,285,145),"boost")], bg="dots"),
    Map("CIRCUIT", C["p2"], [
        (78,78,405,18),(798,78,405,18),(78,78,18,565),(1185,78,18,565),
        (78,623,405,18),(798,623,405,18),
        (278,198,205,18),(798,198,205,18),(278,198,18,205),(985,198,18,205),
        (278,498,205,18),(798,498,205,18),(278,378,18,138),(985,378,18,138),(498,318,285,18)],
        bg="grid"),
]
 
 
# ══════════════════════════════════════════════════════════════════
#  PLAYER
# ══════════════════════════════════════════════════════════════════
SPEED         = 224.0
DODGE_SPEED   = 640.0
DODGE_DUR     = 0.17
DODGE_CD      = 1.25
SPECIAL_CD    = 5.0
P_RADIUS      = 18
 
 
class Player:
    def __init__(self, pid, x, y, color, glow, dark, keys, kd, ks):
        self.pid   = pid
        self.x, self.y = float(x), float(y)
        self.color, self.glow, self.dark = color, glow, dark
        self.keys  = keys        # (up,down,left,right)
        self.kd    = kd          # dodge key
        self.ks    = ks          # special key
        self.is_it = False
        self.radius = P_RADIUS
 
        self.dodge_cd    = 0.0
        self.dodge_t     = 0.0
        self.dodge_dir   = (0.0, -1.0)
        self.is_dodging  = False
        self.invincible  = False
 
        self.special_cd  = 0.0
        self.special_t   = 0.0
        self.special_on  = False
 
        self.frozen      = 0.0
        self.size_mod    = 1.0
        self.angle       = 0.0
        self.tag_flash   = 0.0
        self.trail_t     = 0.0
        self.zone_fx     = None
 
    @property
    def pos(self):
        return (int(self.x), int(self.y))
 
    @property
    def r(self):
        return self.radius * self.size_mod
 
    def hits_wall(self, rect):
        nx = max(rect.left, min(self.x, rect.right))
        ny = max(rect.top,  min(self.y, rect.bottom))
        return (self.x-nx)**2 + (self.y-ny)**2 <= self.r**2
 
    def touches(self, other):
        dx, dy = self.x-other.x, self.y-other.y
        return math.sqrt(dx*dx+dy*dy) < self.r + other.r
 
    def input(self, keys):
        if self.frozen > 0:
            return 0, 0
        u,d,l,ri = self.keys
        dx = (1 if keys[ri] else 0) - (1 if keys[l] else 0)
        dy = (1 if keys[d]  else 0) - (1 if keys[u] else 0)
        return dx, dy
 
    def update(self, dt, keys, walls, ps, map_obj):
        if self.frozen > 0:
            self.frozen -= dt
            self.frozen = max(0.0, self.frozen)
            return
 
        dx, dy = self.input(keys)
 
        # Cooldowns
        self.dodge_cd = max(0.0, self.dodge_cd - dt)
        if self.dodge_t > 0:
            self.dodge_t -= dt
            if self.dodge_t <= 0:
                self.is_dodging = False
                self.invincible = False
        self.special_cd = max(0.0, self.special_cd - dt)
        if self.special_t  > 0:
            self.special_t -= dt
            if self.special_t <= 0:
                self.special_on = False
 
        # Trigger dodge
        if keys[self.kd] and self.dodge_cd <= 0 and not self.is_dodging:
            ndx, ndy = float(dx), float(dy)
            if ndx == 0 and ndy == 0:
                ndy = -1.0
            ln = math.sqrt(ndx**2+ndy**2)
            self.dodge_dir = (ndx/ln, ndy/ln)
            self.is_dodging = True
            self.invincible  = True
            self.dodge_t    = DODGE_DUR
            self.dodge_cd   = DODGE_CD
            ps.burst(self.x, self.y, self.glow, 18)
            SFX["dodge"].play()
 
        # Speed
        spd = SPEED
        if self.zone_fx == "slow":  spd *= 0.5
        if self.zone_fx == "boost": spd *= 1.65
 
        if self.is_dodging:
            mvx = self.dodge_dir[0]*DODGE_SPEED
            mvy = self.dodge_dir[1]*DODGE_SPEED
        else:
            ln = math.sqrt(dx**2+dy**2)
            if ln > 0:
                dx /= ln; dy /= ln
            mvx, mvy = dx*spd, dy*spd
            if dx!=0 or dy!=0:
                self.angle = math.atan2(dy, dx)
 
        # Trail
        self.trail_t += dt
        if self.trail_t > 0.025:
            self.trail_t = 0
            tc = self.glow if not self.is_it else C["tag"]
            ps.trail(self.x, self.y, tc)
 
        # Move X
        self.x += mvx*dt
        for w in walls:
            if self.hits_wall(w):
                self.x = (w.left - self.r) if mvx>0 else (w.right + self.r)
                mvx = 0
        # Move Y
        self.y += mvy*dt
        for w in walls:
            if self.hits_wall(w):
                self.y = (w.top - self.r) if mvy>0 else (w.bottom + self.r)
                mvy = 0
 
        # Bounds
        self.x = max(self.r, min(W-self.r, self.x))
        self.y = max(self.r, min(H-self.r, self.y))
 
        self.zone_fx = map_obj.zone_at((self.x, self.y))
        if self.tag_flash > 0:
            self.tag_flash = max(0.0, self.tag_flash - dt*3)
 
    def draw(self, surf):
        r   = int(self.r)
        pos = self.pos
 
        if self.is_it:
            glow_circle(surf, C["tag"], pos, r, layers=5, step=32)
        elif self.special_on:
            glow_circle(surf, self.glow, pos, r+4, layers=6, step=38)
        else:
            glow_circle(surf, self.glow, pos, r, layers=3, step=28)
 
        bc = C["tag"] if self.is_it else self.color
        if self.tag_flash > 0:
            t = self.tag_flash
            bc = (min(255,int(bc[0]*(1-t)+255*t)),
                  min(255,int(bc[1]*(1-t)+255*t)),
                  min(255,int(bc[2]*(1-t)+255*t)))
        pygame.draw.circle(surf, bc, pos, r)
        pygame.draw.circle(surf, self.dark, pos, max(1,r-4), 2)
 
        ax = int(self.x + math.cos(self.angle)*(r-7))
        ay = int(self.y + math.sin(self.angle)*(r-7))
        pygame.draw.line(surf, self.glow, pos, (ax,ay), 3)
        pygame.draw.circle(surf, self.glow, (ax,ay), 3)
 
        if self.is_it:
            f = pygame.font.SysFont("Consolas", 13, bold=True)
            lbl = f.render("IT", True, C["bg"])
            surf.blit(lbl, (pos[0]-lbl.get_width()//2, pos[1]-lbl.get_height()//2))
 
        if self.frozen > 0:
            pygame.draw.circle(surf, (100,180,255), pos, r+4, 3)
 
        if self.dodge_cd > 0:
            frac = self.dodge_cd / DODGE_CD
            pygame.draw.arc(surf, self.glow,
                            (self.x-r-6, self.y-r-6, (r+6)*2, (r+6)*2),
                            math.pi/2, math.pi/2 + math.tau*(1-frac), 2)
 
 
# ══════════════════════════════════════════════════════════════════
#  GAME MODES
# ══════════════════════════════════════════════════════════════════
class Mode:
    name = "Base"; desc = ""; color = C["white"]
 
    def __init__(self, p1, p2, m):
        self.p1, self.p2 = p1, p2
        self.map = m
        self.grace  = 0.0
        self.winner = None
 
    def tag(self, tagger, tagged, ps):
        if self.grace > 0: return
        tagged.is_it   = True
        tagger.is_it   = False
        tagged.tag_flash = 1.0
        self.grace = 0.5
        ps.burst(tagged.x, tagged.y, C["tag"], 40)
        SFX["tag"].play()
 
    def update(self, dt, keys, ps):
        self.grace = max(0.0, self.grace - dt)
        for p in (self.p1, self.p2):
            if keys[p.ks] and p.special_cd <= 0:
                self.special(p, ps)
        if not self.p1.invincible and not self.p2.invincible:
            if self.p1.is_it and self.p1.touches(self.p2):
                self.tag(self.p1, self.p2, ps)
            elif self.p2.is_it and self.p2.touches(self.p1):
                self.tag(self.p2, self.p1, ps)
        self.check_win()
 
    def special(self, p, ps):
        p.special_cd = SPECIAL_CD
        p.special_on = True
        p.special_t  = 2.0
        ps.burst(p.x, p.y, p.glow, 22)
        SFX["boost"].play()
 
    def check_win(self): pass
    def hud(self, surf): pass
 
 
# 1 ── Classic Tag ──────────────────────────────────────────────────
class ClassicTag(Mode):
    name  = "CLASSIC TAG"
    desc  = "Avoid being IT! First to 30s free time wins."
    color = C["p1"]
 
    def __init__(self, p1, p2, m):
        super().__init__(p1, p2, m)
        self.t1 = self.t2 = 0.0
        self.target = 30.0
 
    def update(self, dt, keys, ps):
        super().update(dt, keys, ps)
        if not self.p1.is_it: self.t1 += dt
        if not self.p2.is_it: self.t2 += dt
 
    def check_win(self):
        if self.t1 >= self.target: self.winner = 1
        elif self.t2 >= self.target: self.winner = 2
 
    def special(self, p, ps):
        super().special(p, ps)
        p.zone_fx = "boost"
 
    def hud(self, surf):
        f = pygame.font.SysFont("Consolas", 18, bold=True)
        bw = 300
        for i,(p,t) in enumerate([(self.p1,self.t1),(self.p2,self.t2)]):
            x = 40 if i==0 else W-40-bw
            y = H-55
            frac = min(1.0, t/self.target)
            pygame.draw.rect(surf, C["dk_gray"], (x,y,bw,16), border_radius=8)
            fc = p.color if not p.is_it else C["tag"]
            pygame.draw.rect(surf, fc, (x,y,int(bw*frac),16), border_radius=8)
            pygame.draw.rect(surf, p.glow, (x,y,bw,16), 1, border_radius=8)
            lbl = f.render(f"P{p.pid} FREE: {t:.1f}s", True, p.glow)
            surf.blit(lbl, (x, y-22))
 
 
# 2 ── Survivor ────────────────────────────────────────────────────
class Survivor(Mode):
    name  = "SURVIVOR"
    desc  = "Be NOT-IT when time runs out!"
    color = C["green"]
 
    def __init__(self, p1, p2, m):
        super().__init__(p1, p2, m)
        self.time_left = 60.0
 
    def update(self, dt, keys, ps):
        super().update(dt, keys, ps)
        self.time_left = max(0.0, self.time_left - dt)
 
    def check_win(self):
        if self.time_left <= 0:
            self.winner = 2 if self.p1.is_it else 1
 
    def hud(self, surf):
        f = pygame.font.SysFont("Consolas", 44, bold=True)
        t = self.time_left
        c = C["orange"] if t < 10 else C["white"]
        lbl = f.render(f"{t:.1f}", True, c)
        surf.blit(lbl, (W//2-lbl.get_width()//2, 18))
 
 
# 3 ── Score Rush ──────────────────────────────────────────────────
class ScoreRush(Mode):
    name  = "SCORE RUSH"
    desc  = "Earn pts while NOT being IT! First to 50 wins."
    color = C["purple"]
 
    def __init__(self, p1, p2, m):
        super().__init__(p1, p2, m)
        self.s1 = self.s2 = 0.0
        self.target = 50.0
 
    def update(self, dt, keys, ps):
        super().update(dt, keys, ps)
        if not self.p1.is_it: self.s1 += dt*3
        if not self.p2.is_it: self.s2 += dt*3
 
    def check_win(self):
        if self.s1 >= self.target: self.winner = 1
        elif self.s2 >= self.target: self.winner = 2
 
    def special(self, p, ps):
        super().special(p, ps)
        opp = self.p2 if p.pid==1 else self.p1
        opp.frozen = 2.2
        ps.burst(opp.x, opp.y, (100,180,255), 28)
 
    def hud(self, surf):
        f = pygame.font.SysFont("Consolas", 26, bold=True)
        for i,(p,s) in enumerate([(self.p1,self.s1),(self.p2,self.s2)]):
            x  = 40 if i==0 else W-55
            bh = 120
            bw = 14
            yb = H-60
            frac = min(1.0, s/self.target)
            pygame.draw.rect(surf, C["dk_gray"], (x,yb-bh,bw,bh), border_radius=7)
            fh = int(bh*frac)
            pygame.draw.rect(surf, p.color, (x,yb-fh,bw,fh), border_radius=7)
            pygame.draw.rect(surf, p.glow, (x,yb-bh,bw,bh), 1, border_radius=7)
            lbl = f.render(f"P{p.pid}:{int(s)}", True, p.glow)
            surf.blit(lbl, (x-12 if i==0 else x-40, yb-bh-28))
 
 
# 4 ── Ghost Tag ───────────────────────────────────────────────────
class GhostTag(Mode):
    name  = "GHOST TAG"
    desc  = "IT is a ghost! Most tags in 60s wins."
    color = C["p2"]
 
    def __init__(self, p1, p2, m):
        super().__init__(p1, p2, m)
        self.tags1 = self.tags2 = 0
        self.time_left = 60.0
 
    def tag(self, tagger, tagged, ps):
        if self.grace > 0: return
        if tagger.pid==1: self.tags1 += 1
        else:             self.tags2 += 1
        super().tag(tagger, tagged, ps)
 
    def update(self, dt, keys, ps):
        super().update(dt, keys, ps)
        self.time_left = max(0.0, self.time_left - dt)
 
    def check_win(self):
        if self.time_left <= 0:
            if   self.tags1 > self.tags2: self.winner = 1
            elif self.tags2 > self.tags1: self.winner = 2
            else:                          self.winner = 0
 
    def hud(self, surf):
        fb = pygame.font.SysFont("Consolas", 40, bold=True)
        fm = pygame.font.SysFont("Consolas", 22, bold=True)
        t  = self.time_left
        c  = C["orange"] if t<10 else C["white"]
        lbl = fb.render(f"{t:.1f}", True, c)
        surf.blit(lbl, (W//2-lbl.get_width()//2, 18))
        for i,(p,tg) in enumerate([(self.p1,self.tags1),(self.p2,self.tags2)]):
            x  = 40 if i==0 else W-200
            l2 = fm.render(f"P{p.pid} TAGS: {tg}", True, p.glow)
            surf.blit(l2, (x, H-50))
 
 
# 5 ── Shrink Tag ──────────────────────────────────────────────────
class ShrinkTag(Mode):
    name  = "SHRINK TAG"
    desc  = "Each tag shrinks you. 3 tags = out!"
    color = C["orange"]
 
    def __init__(self, p1, p2, m):
        super().__init__(p1, p2, m)
        self.hits1 = self.hits2 = 0
 
    def tag(self, tagger, tagged, ps):
        super().tag(tagger, tagged, ps)
        if tagged.pid==1:
            self.hits1 += 1
            tagged.size_mod = max(0.35, 1.0 - self.hits1*0.22)
        else:
            self.hits2 += 1
            tagged.size_mod = max(0.35, 1.0 - self.hits2*0.22)
 
    def check_win(self):
        if self.hits1 >= 3: self.winner = 2
        if self.hits2 >= 3: self.winner = 1
 
    def hud(self, surf):
        f = pygame.font.SysFont("Consolas", 20, bold=True)
        for i,(p,h) in enumerate([(self.p1,self.hits1),(self.p2,self.hits2)]):
            x  = 40 if i==0 else W-220
            bl = "█"*(3-h) + "░"*h
            l1 = f.render(f"P{p.pid}: {bl}", True, p.glow)
            l2 = f.render(f"HITS: {h}/3", True, p.color)
            surf.blit(l1, (x, H-52))
            surf.blit(l2, (x, H-28))
 
 
MODES = [ClassicTag, Survivor, ScoreRush, GhostTag, ShrinkTag]
 
 
# ══════════════════════════════════════════════════════════════════
#  MENU
# ══════════════════════════════════════════════════════════════════
class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.sel_mode = 0
        self.sel_map  = 0
        self.state    = "main"
        self.t        = 0.0
        self.ps       = PS()
        self.FT = pygame.font.SysFont("Consolas", 60, bold=True)
        self.FB = pygame.font.SysFont("Consolas", 30, bold=True)
        self.FM = pygame.font.SysFont("Consolas", 20, bold=True)
        self.FS = pygame.font.SysFont("Consolas", 14)
 
    def run(self):
        clock = pygame.time.Clock()
        while True:
            dt = clock.tick(FPS)/1000
            self.t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                r = self._event(e)
                if r == "start":
                    return self.sel_mode, self.sel_map
 
            if random.random() < 0.25:
                self.ps.emit(random.randint(0,W), H,
                    random.choice([C["p1"],C["p2"],C["purple"]]),
                    n=1, vx=random.uniform(-0.4,0.4),
                    vy=random.uniform(-2.5,-0.8),
                    life=2.2, size=random.uniform(1,3))
            self.ps.update(dt)
            self._draw()
            pygame.display.flip()
 
    def _event(self, e):
        if e.type != pygame.KEYDOWN: return
        k = e.key
        if self.state == "main":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "mode"; SFX["click"].play()
        elif self.state == "mode":
            if k == pygame.K_LEFT:
                self.sel_mode = (self.sel_mode-1)%len(MODES); SFX["click"].play()
            elif k == pygame.K_RIGHT:
                self.sel_mode = (self.sel_mode+1)%len(MODES); SFX["click"].play()
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "map"; SFX["click"].play()
            elif k == pygame.K_ESCAPE:
                self.state = "main"
        elif self.state == "map":
            if k == pygame.K_LEFT:
                self.sel_map = (self.sel_map-1)%len(MAPS); SFX["click"].play()
            elif k == pygame.K_RIGHT:
                self.sel_map = (self.sel_map+1)%len(MAPS); SFX["click"].play()
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                SFX["win"].play(); return "start"
            elif k == pygame.K_ESCAPE:
                self.state = "mode"
 
    def _draw(self):
        surf = self.screen
        surf.fill(C["bg"])
        for x in range(0,W,60): pygame.draw.line(surf,C["grid"],(x,0),(x,H))
        for y in range(0,H,60): pygame.draw.line(surf,C["grid"],(0,y),(W,y))
        self.ps.draw(surf)
 
        tc = (
            int(200+55*math.sin(self.t*1.3)),
            int(40+30*math.sin(self.t*2.1)),
            int(70+30*math.cos(self.t*1.7))
        )
        text_center(surf, "NEON TAG", self.FT, tc, 58)
        sc = C["p2"] if int(self.t*2)%2==0 else C["p2_glow"]
        text_center(surf, "2-PLAYER LOCAL TAG", self.FM, sc, 148)
 
        if self.state == "main":
            text_center(surf, "PRESS ENTER TO START", self.FB, C["white"], 240)
            text_center(surf, "P1: WASD + Q(dodge) + E(special)", self.FS, C["p1_glow"], 310)
            text_center(surf, "P2: ARROWS + RSHIFT(dodge) + RCTRL(special)", self.FS, C["p2_glow"], 334)
            text_center(surf, "5 MODES  ·  5 MAPS  ·  DODGE  ·  FREEZE  ·  SHRINK", self.FM, C["gray"], 395)
 
        elif self.state == "mode":
            text_center(surf, "SELECT GAME MODE", self.FB, C["white"], 198)
            text_center(surf, "◄  ►  to browse  |  ENTER to confirm", self.FS, C["gray"], 238)
            mc = MODES[self.sel_mode]
            card = pygame.Rect(W//2-330, 268, 660, 190)
            glow_rect(surf, mc.color, card, rr=12, gs=12)
            s = pygame.Surface((card.w,card.h), pygame.SRCALPHA); s.fill((0,0,0,115))
            surf.blit(s, card.topleft)
            text_center(surf, mc.name, self.FB, mc.color, 298)
            text_center(surf, mc.desc, self.FM, C["white"], 348)
            for i in range(len(MODES)):
                col = C["white"] if i==self.sel_mode else C["gray"]
                x   = W//2 + (i-len(MODES)//2)*28
                pygame.draw.circle(surf, col, (x,498), 7 if i==self.sel_mode else 4)
 
        elif self.state == "map":
            text_center(surf, "SELECT MAP", self.FB, C["white"], 198)
            text_center(surf, "◄  ►  to browse  |  ENTER to play", self.FS, C["gray"], 238)
            m    = MAPS[self.sel_map]
            card = pygame.Rect(W//2-330, 268, 660, 190)
            glow_rect(surf, m.color, card, rr=12, gs=12)
            s = pygame.Surface((card.w,card.h), pygame.SRCALPHA); s.fill((0,0,0,115))
            surf.blit(s, card.topleft)
            # Mini preview
            sx, sy = 0.44, 0.22
            for w in m.walls:
                wr = pygame.Rect(card.x+15+w.x*sx, card.y+10+w.y*sy,
                                 max(3,w.w*sx), max(3,w.h*sy))
                pygame.draw.rect(surf, m.color, wr, border_radius=2)
            text_center(surf, m.name, self.FB, m.color, 488)
            for i in range(len(MAPS)):
                col = C["white"] if i==self.sel_map else C["gray"]
                x   = W//2 + (i-len(MAPS)//2)*28
                pygame.draw.circle(surf, col, (x,528), 7 if i==self.sel_map else 4)
 
        scanlines(surf)
        vignette(surf)
 
 
# ══════════════════════════════════════════════════════════════════
#  GAME
# ══════════════════════════════════════════════════════════════════
class Game:
    def __init__(self, screen, mode_idx, map_idx):
        self.screen = screen
        self.map    = MAPS[map_idx]
 
        self.p1 = Player(1, 220, H//2, C["p1"], C["p1_glow"], C["p1_dark"],
                         (pygame.K_w,pygame.K_s,pygame.K_a,pygame.K_d),
                         pygame.K_q, pygame.K_e)
        self.p2 = Player(2, W-220, H//2, C["p2"], C["p2_glow"], C["p2_dark"],
                         (pygame.K_UP,pygame.K_DOWN,pygame.K_LEFT,pygame.K_RIGHT),
                         pygame.K_RSHIFT, pygame.K_RCTRL)
 
        random.choice([self.p1, self.p2]).is_it = True
 
        self.ps   = PS()
        self.mode = MODES[mode_idx](self.p1, self.p2, self.map)
        self.win_ps = PS()
        self.state  = "playing"
        self.win_t  = 0.0
 
        self.FT = pygame.font.SysFont("Consolas", 54, bold=True)
        self.FB = pygame.font.SysFont("Consolas", 30, bold=True)
        self.FM = pygame.font.SysFont("Consolas", 22, bold=True)
        self.FS = pygame.font.SysFont("Consolas", 14)
 
        self.bg = pygame.Surface((W,H))
        self.map.draw(self.bg)
 
    def run(self):
        clock = pygame.time.Clock()
        while True:
            dt   = min(clock.tick(FPS)/1000, 0.05)
            keys = pygame.key.get_pressed()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: return "menu"
                    if self.state=="win" and e.key==pygame.K_RETURN: return "menu"
 
            if self.state == "playing":
                self._update(dt, keys)
            else:
                self.win_t -= dt
                wp = self.p1 if self.mode.winner==1 else (self.p2 if self.mode.winner==2 else None)
                if wp:
                    self.win_ps.emit(random.randint(0,W), random.randint(0,H), wp.color,
                                     n=3, vx=random.uniform(-1.5,1.5),
                                     vy=random.uniform(-1.5,1.5), life=1.4)
                self.win_ps.update(dt)
 
            self._draw()
            pygame.display.flip()
 
    def _update(self, dt, keys):
        walls = self.map.walls
        self.p1.update(dt, keys, walls, self.ps, self.map)
        self.p2.update(dt, keys, walls, self.ps, self.map)
        self.mode.update(dt, keys, self.ps)
        self.ps.update(dt)
 
        if self.mode.winner is not None:
            self.state = "win"
            self.win_t = 999
            wp = self.p1 if self.mode.winner==1 else (self.p2 if self.mode.winner==2 else None)
            if wp: self.win_ps.burst(W//2, H//2, wp.color, 80)
            SFX["win"].play()
 
    def _draw(self):
        surf = self.screen
        surf.blit(self.bg, (0,0))
        self.ps.draw(surf)
 
        # Ghost mode: IT player is semi-transparent
        if isinstance(self.mode, GhostTag):
            for p in (self.p1, self.p2):
                if p.is_it:
                    gs = pygame.Surface((W,H), pygame.SRCALPHA)
                    r  = int(p.r)
                    pygame.draw.circle(gs, (*p.color,75), p.pos, r)
                    pygame.draw.circle(gs, (*p.glow,55), p.pos, r+5, 2)
                    surf.blit(gs, (0,0))
                    ax = int(p.x+math.cos(p.angle)*(r-7))
                    ay = int(p.y+math.sin(p.angle)*(r-7))
                    pygame.draw.line(surf, (*p.glow,100), p.pos, (ax,ay), 2)
                else:
                    p.draw(surf)
        else:
            self.p1.draw(surf)
            self.p2.draw(surf)
 
        self._hud()
        if self.state == "win":
            self._win_screen()
 
        scanlines(surf)
        vignette(surf)
 
    def _hud(self):
        surf = self.screen
        bar = pygame.Surface((W,50), pygame.SRCALPHA)
        bar.fill((0,0,0,138))
        surf.blit(bar, (0,0))
 
        mn = self.FS.render(self.mode.name, True, C["gray"])
        surf.blit(mn, (W//2-mn.get_width()//2, 6))
 
        for p in (self.p1, self.p2):
            it_lbl = " [IT]" if p.is_it else ""
            lbl = self.FM.render(f"P{p.pid}{it_lbl}", True, p.glow)
            x = 14 if p.pid==1 else W-lbl.get_width()-14
            surf.blit(lbl, (x,14))
 
        # Special bars
        for p in (self.p1, self.p2):
            frac = 1 - min(1.0, p.special_cd/SPECIAL_CD)
            bw = 80
            x  = 14 if p.pid==1 else W-bw-14
            y  = H-30
            pygame.draw.rect(surf, C["dk_gray"], (x,y,bw,10), border_radius=5)
            pygame.draw.rect(surf, p.color, (x,y,int(bw*frac),10), border_radius=5)
            pygame.draw.rect(surf, p.glow, (x,y,bw,10), 1, border_radius=5)
            sl = self.FS.render("SPECIAL", True, C["gray"])
            surf.blit(sl, (x, y-16))
 
        self.mode.hud(surf)
        el = self.FS.render("ESC=MENU", True, C["gray"])
        surf.blit(el, (W-el.get_width()-10, H-20))
 
    def _win_screen(self):
        surf = self.screen
        self.win_ps.draw(surf)
        ov = pygame.Surface((W,H), pygame.SRCALPHA)
        ov.fill((0,0,0,165))
        surf.blit(ov, (0,0))
 
        w = self.mode.winner
        if w == 0:
            text_center(surf, "DRAW!", self.FT, C["white"], H//2-60)
        else:
            p  = self.p1 if w==1 else self.p2
            text_center(surf, f"PLAYER {w} WINS!", self.FT, p.color, H//2-60)
            glow_circle(surf, p.color, (W//2, H//2+30), 42, layers=6, step=28)
 
        text_center(surf, "PRESS ENTER TO RETURN TO MENU", self.FB, C["gray"], H//2+110)
 
 
# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("NEON TAG — 2-Player Local")
 
    while True:
        mode_idx, map_idx = Menu(screen).run()
        result = Game(screen, mode_idx, map_idx).run()
        if result == "quit":
            break
 
    pygame.quit()
    sys.exit()
 
 
if __name__ == "__main__":
    main()
 