"""Vector room schematic. Coordinates show connectivity, not navigable distances."""
from math import cos, sin, pi, hypot
from .qt import Qt, QtCore as C, QtGui as G, QtWidgets as W

INK = "#dce4db"
MUTED = "#8c9c94"
AMBER = "#efba62"
TEAL = "#71dfc2"
P = C.QPointF
R = C.QRectF


def pen(color, width=1, style=Qt.PenStyle.SolidLine):
    result = G.QPen(G.QColor(color))
    result.setWidthF(width)
    result.setStyle(style)
    result.setCapStyle(Qt.PenCapStyle.RoundCap)
    result.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return result


def font(px, bold=False, mono=False):
    f = G.QFont("IBM Plex Mono" if mono else "Barlow")
    f.setStyleHint(G.QFont.StyleHint.Monospace if mono else G.QFont.StyleHint.SansSerif)
    f.setFamilies(["IBM Plex Mono", "DejaVu Sans Mono", "Consolas", "monospace"] if mono else
                  ["Barlow", "Open Sans", "Segoe UI", "Arial"])
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def path(points, close=False):
    result = G.QPainterPath(P(*points[0]))
    for x, y in points[1:]:
        result.lineTo(P(x, y))
    if close:
        result.closeSubpath()
    return result


def symbol(p, x, y, key, color, size=1):
    p.save()
    p.translate(x, y)
    p.scale(size, size)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(pen(color, 1.6))
    if key == "power":
        p.drawPath(path([(2,-8),(-5,1),(0,1),(-2,8),(5,-2),(0,-2),(2,-8)]))
    elif key == "jug":
        p.drawPath(path([(-6,-5),(0,-7),(6,-5),(6,0),(4,4),(0,7),(-4,4),(-6,0)], True))
        p.drawLine(P(-2,0), P(2,0))
        p.drawLine(P(0,-2), P(0,2))
    elif key == "speed":
        for dx in [-3,2]:
            p.drawPath(path([(dx-3,-5),(dx+2,0),(dx-3,5)]))
    elif key in {"packed","forged"}:
        p.drawPath(path([(0,-7),(7,-3),(7,4),(0,8),(-7,4),(-7,-3)],True))
        p.drawPath(path([(-7,-3),(0,1),(7,-3)]))
        p.drawLine(P(0,1),P(0,8))
    elif key == "brand":
        for pts in [[(-9,7),(-2,-7),(3,-7),(-4,7)],[(0,7),(7,-7),(11,-7),(4,7)]]:
            p.fillPath(path(pts,True),G.QColor(color))
    p.restore()


def icon(key, color=AMBER, size=24):
    pix = G.QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    painter = G.QPainter(pix)
    painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
    symbol(painter,size,size,key,color,size/10)
    painter.end()
    pix.setDevicePixelRatio(2)
    return G.QIcon(pix)


# Shapes for the ten rooms in the BO1 solo profile.
SHAPES = {
    "lobby":[(-76,-31),(-51,-31),(-44,-41),(44,-41),(51,-31),(76,-31),(76,25),(51,25),(43,34),(-43,34),(-51,25),(-76,25)],
    "stage":[(-80,-27),(-42,-27),(-34,-34),(35,-34),(43,-27),(80,-27),(80,23),(60,23),(50,31),(-50,31),(-61,23),(-80,23)],
    "theater":[(-82,-34),(-57,-42),(57,-42),(82,-34),(78,20),(57,38),(34,47),(-34,47),(-57,38),(-78,20)],
    "upper":[(-65,-24),(-47,-24),(-39,-31),(57,-31),(66,-22),(66,23),(-65,23)],
    "lower":[(-65,-22),(-55,-31),(42,-31),(52,-24),(65,-24),(65,23),(-65,23)],
    "dressing":[(-64,-25),(-41,-25),(-34,-32),(54,-32),(65,-21),(65,25),(-64,25)],
    "back":[(-57,-24),(25,-24),(32,-32),(58,-32),(58,25),(-57,25)],
    "alley":[(-48,-42),(27,-42),(27,-26),(52,-26),(52,35),(-27,35),(-27,24),(-48,24)],
    "foyer":[(-57,-34),(38,-34),(58,-21),(58,31),(38,40),(-57,40)],
    "projector":[(-52,-17),(-44,-24),(44,-24),(52,-17),(52,18),(-52,18)]
}


class Schematic(W.QWidget):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.world = profile.initial.world
        self.goals = set()
        self.steps = ()
        self.prohibited = set()
        self.setMinimumSize(400, 235)
        self.setAccessibleName(f"{profile.data['name']} room schematic")
        self.setToolTip("Schematic of room connections. The route tab lists each action in order.")

    def show_state(self, world, goals, steps, prohibited):
        self.world, self.goals, self.steps, self.prohibited = world, goals, steps, prohibited
        self.update()

    def paintEvent(self, event):
        p = G.QPainter(self)
        p.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), G.QColor("#111917"))
        w, h = self.width(), self.height()
        p.setPen(pen("#1d2925", .7))
        for x in range(0, w, 18):
            p.drawLine(x,0,x,h)
        for y in range(0, h, 18):
            p.drawLine(0,y,w,y)
        scale = min((w-14)/838, (h-10)/380)
        p.translate((w-838*scale)/2, (h-380*scale)/2)
        p.scale(scale, scale)
        centers = {z["id"]:(z["x"],z["y"]) for z in self.profile.zones.values()}
        used = {(a.origin,a.dest) for a in self.steps if a.origin != a.dest}
        visited = {x for pair in used for x in pair}
        for edge in self.profile.edges.values():
            a, b = edge["from"], edge["to"]
            x1,y1 = centers[a]
            x2,y2 = centers[b]
            active = (a,b) in used or (b,a) in used
            closed = edge["price"] and edge["id"] not in self.world.opened
            blocked = closed and edge["id"] in self.prohibited
            locked = not set(edge.get("requires", [])) <= self.world.flags
            mid = (x1+x2)/2, (y1+y2)/2
            points = [(x1,y1), (x2,y2)] if a not in {"upper","alley","lower","foyer","back"} or x1==x2 or y1==y2 else [(x1,y1),(x1,mid[1]),(x2,mid[1]),(x2,y2)]
            line = path(points)
            p.setPen(pen("#36463e", 12))
            p.drawPath(line)
            p.setPen(pen("#1a231f", 9))
            p.drawPath(line)
            shade = "#d38179" if blocked else AMBER if active else "#798b80" if not locked else "#48594f"
            p.setPen(pen(shade,2.25 if active else 1.2,Qt.PenStyle.DashLine if locked else Qt.PenStyle.SolidLine))
            p.drawPath(line)
            if not edge["bidirectional"]:
                dx, dy = x2-x1, y2-y1
                length = hypot(dx, dy)
                if length:
                    dx, dy = dx/length, dy/length
                    tx, ty = mid[0]+14*dx, mid[1]+14*dy
                    p.setPen(pen(shade,2))
                    p.drawPath(path([(tx-6*dx-4*dy,ty-6*dy+4*dx),(tx,ty),(tx-6*dx+4*dy,ty-6*dy-4*dx)]))
            if closed:
                p.save()
                p.translate(*mid)
                p.setPen(pen(shade,2.2))
                if blocked:
                    p.drawLine(P(-4,-4),P(4,4))
                    p.drawLine(P(-4,4),P(4,-4))
                else:
                    if abs(x2-x1) < abs(y2-y1) and len(points)==2:
                        p.rotate(90)
                    p.drawLine(P(-2,-5),P(-2,5))
                    p.drawLine(P(2,-5),P(2,5))
                p.restore()
        # Draw directional transfers separately from physical doorways.
        transfers = {(r["at"],r["to"]) for r in self.profile.actions.values() if "to" in r}
        for origin, dest in sorted(transfers):
            active = (origin,dest) in used
            if not active and (origin,dest) != ("stage","projector"):
                continue
            start, end = centers[origin], centers[dest]
            if origin in {"crash", "pond"}:
                corridor_y = 136 if origin == "crash" else 360
                waypoints = [start, (start[0],corridor_y), (end[0],corridor_y), end]
            else:
                bend = (start[0],end[1]) if origin == "projector" else (end[0],start[1])
                waypoints = [start,bend,end]
            p.setPen(pen(AMBER if active else "#536e65",1.6,Qt.PenStyle.DashLine))
            p.drawPath(path(waypoints))
        for key,(x,y) in centers.items():
            current = self.world.zone == key
            route = key in visited
            p.save()
            p.translate(x,y)
            half = max(46, min(85, len(self.profile.zones[key]["name"]) * 4.3 + 12))
            generic = [(-half,-20),(-half+8,-28),(half-10,-28),(half,-18),(half,23),(-half,23)]
            outline = path(SHAPES.get(key, generic), True)
            p.fillPath(outline,G.QColor("#12362e" if current else "#292a20" if route else "#1c2823"))
            p.setPen(pen(TEAL if current else "#a08859" if route else "#516258",1.8))
            p.drawPath(outline)
            p.save()
            p.scale(.93,.82)
            p.setPen(pen("#38594e" if current else "#3b4336",.8))
            p.drawPath(outline)
            p.restore()
            # Seating banks and stairs identify the map's central theater and wings.
            p.setPen(pen("#53604d",.9))
            if key == "theater":
                for dx in (-48,-26,26,48):
                    for dy in (18,23,28):
                        p.drawLine(P(dx-6,dy),P(dx+6,dy-1))
            elif key in {"upper","lower","dressing","back"}:
                for i in range(5):
                    p.drawLine(P(-44+i*4,12),P(-44+i*4,19))
            elif key == "stage":
                p.drawLine(P(-55,21),P(55,21))
            p.setFont(font(13 if key in {"projector","accelerator"} else 16, True))
            p.setPen(G.QColor(TEAL if current else INK))
            name=self.profile.zones[key]["name"]
            p.drawText(R(-77,-13,154,25), Qt.AlignmentFlag.AlignCenter, name)
            if current:
                p.setPen(pen(TEAL,1))
                p.setBrush(G.QColor("#173b31"))
                p.drawEllipse(P(0,-27),7,7)
                p.setBrush(G.QColor(TEAL))
                p.drawEllipse(P(0,-27),3,3)
            targets=[g for g in self.profile.goals if g in self.goals and self.profile.goals[g]["zone"]==key and g not in self.world.flags]
            if targets:
                p.setBrush(G.QColor("#372e1f"))
                p.setPen(pen(AMBER,1.1))
                p.drawEllipse(P(50,-19),10,10)
                symbol(p,50,-19,targets[0],AMBER,.9)
            p.restore()
        p.end()
