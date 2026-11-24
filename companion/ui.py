"""Manual second-monitor desktop companion for Kino der Toten."""
from dataclasses import replace

from .model import COLD_WAR, MAP_FILES, MARKERS, MapProfile, Match, World
from .qt import Qt, QtCore as C, QtGui as G, QtWidgets as W
from .schematic import Schematic, font, icon, AMBER, TEAL
from .session import Session
from .solver import Options, find_route, step_balances
from .style import STYLE


def label(text, role=""):
    widget = W.QLabel(text)
    if role:
        widget.setObjectName(role)
    return widget


def button(text, callback):
    result = W.QPushButton(text)
    result.clicked.connect(callback)
    return result


def layout(parent=None, horizontal=False, margins=(0, 0, 0, 0), spacing=8):
    obj = W.QHBoxLayout(parent) if horizontal else W.QVBoxLayout(parent)
    obj.setContentsMargins(*margins)
    obj.setSpacing(spacing)
    return obj


def container(name="clear"):
    widget = W.QWidget()
    widget.setObjectName(name)
    return widget


def card(kind="card", margins=(16, 14, 16, 14)):
    frame = W.QFrame()
    frame.setObjectName(kind)
    return frame, layout(frame, margins=margins, spacing=9)


def line():
    widget = W.QFrame()
    widget.setObjectName("rule")
    widget.setFixedHeight(1)
    return widget


def combo(items):
    widget = W.QComboBox()
    for title, value in items:
        widget.addItem(title, value)
    return widget


class Check(W.QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = W.QStyleOptionButton()
        self.initStyleOption(option)
        box = self.style().subElementRect(W.QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        painter = G.QPainter(self)
        painter.setRenderHint(G.QPainter.RenderHint.Antialiasing)
        box = C.QRectF(box).adjusted(0.8,0.8,-0.8,-0.8)
        tint = AMBER if self.isChecked() else "#68796b"
        painter.setPen(G.QPen(G.QColor(tint),1.2))
        painter.setBrush(G.QColor(AMBER if self.isChecked() else "#19231e"))
        painter.drawRoundedRect(box,2,2)
        if self.isChecked():
            painter.setPen(G.QPen(G.QColor("#161d17"),1.7))
            x,y,w,h = box.x(),box.y(),box.width(),box.height()
            trace = G.QPainterPath(C.QPointF(x+w*.2,y+h*.52))
            trace.lineTo(x+w*.42,y+h*.74)
            trace.lineTo(x+w*.82,y+h*.24)
            painter.drawPath(trace)
        painter.end()


def bind_field(text, widget):
    name = label(text, "small")
    name.setBuddy(widget)
    widget.setAccessibleName(text)
    col = layout(spacing=4)
    col.addWidget(name)
    col.addWidget(widget)
    return col


def time_text(seconds):
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


class StateEditor(W.QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit match state")
        self.setMinimumWidth(470)
        self.session = session
        profile, match = session.profile, session.match
        world = match.world
        out = layout(self, margins=(20,18,20,18), spacing=12)
        out.addWidget(label("Edit match state", "section"))
        tabs = W.QTabWidget()
        out.addWidget(tabs)
        state = container()
        fields = layout(state, margins=(6,12,6,8))
        self.zone = combo([(r["name"], k) for k,r in profile.zones.items()])
        self.zone.setCurrentIndex(self.zone.findData(world.zone))
        self.points = W.QSpinBox()
        self.points.setRange(0, 2147483647)
        self.points.setValue(match.points)
        row = layout(horizontal=True)
        row.addLayout(bind_field("Current zone", self.zone),1)
        row.addLayout(bind_field("Available points", self.points),1)
        fields.addLayout(row)
        self.flags = {}
        for key, title in [("power","Power is on"),("jug","Juggernog owned"),("speed","Speed Cola owned"),("packed","Pack-a-Punch used")]:
            c = Check(title)
            c.setChecked(key in world.flags)
            self.flags[key] = c
            fields.addWidget(c)
        self.charge = self.cooldown = self.other_perks = None
        if profile.data["id"] == COLD_WAR:
            self.other_perks = W.QSpinBox()
            self.other_perks.setRange(0, profile.other_perk_limit)
            self.other_perks.setValue(world.other_perks)
            fields.addLayout(bind_field("Other perks held (excluding Juggernog and Speed Cola)", self.other_perks))
            quest = container()
            quest_fields = layout(quest, margins=(6,12,6,8))
            for key, title in [
                ("hydro", "Hydro-Energy terminal active"),
                ("cyclotron", "Cyclotron terminal active"),
                ("aether", "Inside the setup Dark Aether visit"),
                ("part", "Machine part carried"),
                ("forged", "Pack-a-Punch machine forged"),
            ]:
                check = Check(title)
                check.setChecked(key in world.flags)
                self.flags[key] = check
                quest_fields.addWidget(check)
            quest_fields.addStretch()
            tabs.addTab(quest, "Machine setup")
        else:
            self.charge = combo([("Idle / ready to initialize",""),("Initialized at stage","primed"),("Linked at lobby","linked")])
            phase = next((x for x in ("primed","linked") if x in world.flags), "")
            self.charge.setCurrentIndex(self.charge.findData(phase))
            self.cooldown = W.QSpinBox()
            self.cooldown.setRange(0,60)
            self.cooldown.setValue(world.cooldown)
            self.cooldown.setSuffix(" s")
            tele_row = layout(horizontal=True)
            tele_row.addLayout(bind_field("Teleporter",self.charge),2)
            tele_row.addLayout(bind_field("Cooldown left", self.cooldown),1)
            fields.addLayout(tele_row)
        fields.addStretch()
        tabs.insertTab(0,state,"Player & utilities")
        tabs.setCurrentIndex(0)
        doors = container()
        grid = W.QGridLayout(doors)
        self.doors = {}
        for i,(key,e) in enumerate(profile.doors.items()):
            title = f"{profile.zones[e['from']]['name']} – {profile.zones[e['to']]['name']}"
            grid.addWidget(label(title),i,0)
            choice = combo([("Closed","closed"),("Open","open"),("Keep closed","restricted")])
            choice.setAccessibleName(title)
            choice.setCurrentIndex(1 if key in world.opened else 2 if key in session.prohibited else 0)
            self.doors[key] = choice
            grid.addWidget(choice,i,1)
        tabs.addTab(doors,"Doors")
        self.problem = label("", "error")
        self.problem.setWordWrap(True)
        out.addWidget(self.problem)
        foot = layout(horizontal=True)
        foot.addStretch()
        foot.addWidget(button("Cancel",self.reject))
        self.save = button("Apply changes", self.apply_changes)
        self.save.setObjectName("primary")
        foot.addWidget(self.save)
        out.addLayout(foot)

    def apply_changes(self):
        flags = {key for key,control in self.flags.items() if control.isChecked()}
        flags.update(self.session.match.world.flags & MARKERS)
        if self.charge and self.charge.currentData():
            flags.add(self.charge.currentData())
        opened = frozenset(key for key,c in self.doors.items() if c.currentData()=="open")
        restricted = frozenset(key for key,c in self.doors.items() if c.currentData()=="restricted")
        world = World(self.zone.currentData(), opened, frozenset(flags),
                      self.cooldown.value() if self.cooldown else 0,
                      self.other_perks.value() if self.other_perks else 0)
        match = Match(world, self.points.value())
        try:
            self.session.record("STATE_CORRECTED", "Edited match state", match, restricted)
        except ValueError as exc:
            self.problem.setText(str(exc))
            return
        self.accept()


class Companion(W.QMainWindow):
    def __init__(self, profile=None):
        super().__init__()
        maps = [MapProfile.load(path) for path in MAP_FILES.values()]
        self.profiles = {m.data["id"]: m for m in maps}
        self.profile = profile or maps[0]
        self.profiles[self.profile.data["id"]] = self.profile
        self.sessions = {key: Session(m) for key, m in self.profiles.items()}
        self.selections = {key: {"power", "jug"} & m.goals.keys() for key, m in self.profiles.items()}
        self.resize(1200, 822)
        self.setWindowIcon(icon("brand"))
        self.build_view(Options())

    def switch_map(self):
        selected = self.map_selector.currentData()
        if selected == self.profile.data["id"]:
            return
        options = Options(self.mode.currentData(), self.budget.currentData(), self.weight.value())
        self.profile = self.profiles[selected]
        self.build_view(options)

    def build_view(self, options):
        map_id = self.profile.data["id"]
        self.session = self.sessions[map_id]
        self.goals = self.selections[map_id]
        self.setWindowTitle(f"{self.profile.data['name']} · Route Companion")
        self.setStyleSheet(STYLE)
        root = container()
        self.setCentralWidget(root)
        outer = layout(root, spacing=0)
        bar = container("bar")
        header = layout(bar, True, (24,10,24,10), 12)
        mark = label("")
        mark.setPixmap(icon("brand").pixmap(32,32))
        header.addWidget(mark)
        header.addWidget(label("Route Companion", "brand"))
        self.map_selector = combo([(m.data["name"], key) for key, m in self.profiles.items()])
        self.map_selector.setAccessibleName("Map")
        self.map_selector.setCurrentIndex(self.map_selector.findData(map_id))
        header.addWidget(label("Map", "small"))
        header.addWidget(self.map_selector)
        header.addStretch()
        header.addWidget(label("●  Manual tracking", "status"))
        self.undo_button = button("Undo",self.undo)
        header.addWidget(self.undo_button)
        self.reset_button = button("Reset match",self.reset)
        header.addWidget(self.reset_button)
        outer.addWidget(bar)
        scroller = W.QScrollArea()
        scroller.setWidgetResizable(True)
        outer.addWidget(scroller)
        body = container()
        scroller.setWidget(body)
        content = layout(body, margins=(24,16,24,18), spacing=14)
        intro = layout(spacing=1)
        intro.addWidget(label(self.profile.data["title"].upper().replace(": ", "  /  "), "gold"))
        intro.addWidget(label(self.profile.data["name"],"hero"))
        intro.addWidget(label(self.profile.data["release"], "dim"))
        content.addLayout(intro)
        cols = layout(horizontal=True, spacing=16)
        content.addLayout(cols,1)
        left = layout(spacing=12)
        right = layout(spacing=12)
        cols.addLayout(left, 2)
        cols.addLayout(right, 1)
        view, inside = card(margins=(12,7,12,8))
        view.setMinimumWidth(520)
        self.tabs = W.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.map = Schematic(self.profile)
        self.tabs.addTab(self.map,"Map schematic")
        self.route_table = W.QTableWidget(0,4)
        self.route_table.setAccessibleName("Ordered recommended route")
        self.route_table.setHorizontalHeaderLabels(["Step","Action","Points","Funding"])
        self.route_table.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.route_table.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.route_table.setAlternatingRowColors(True)
        self.route_table.setShowGrid(False)
        self.route_table.verticalHeader().hide()
        hdr = self.route_table.horizontalHeader()
        hdr.setSectionResizeMode(W.QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1,W.QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.route_table,"Route steps")
        self.history = W.QListWidget()
        self.tabs.addTab(self.history,"History")
        inside.addWidget(self.tabs,1)
        self.legend = container()
        legend = layout(self.legend,True,(5,2,5,1),12)
        for text, color in [("◉  Player",TEAL),("━  Route",AMBER),("Ⅱ  Closed door","#a3aea1"),("×  Keep closed","#cf8a7c")]:
            item=label(text,"small")
            item.setStyleSheet(f"color: {color};")
            legend.addWidget(item)
        legend.addStretch()
        inside.addWidget(self.legend)
        self.tabs.currentChanged.connect(lambda i:self.legend.setVisible(i==0))
        left.addWidget(view,1)

        next_card, next_col = card("nextCard")
        next_col.addWidget(label("NEXT ACTION","gold"))
        self.action_title = label("", "action")
        self.action_title.setWordWrap(True)
        next_col.addWidget(self.action_title)
        row = layout(horizontal=True,spacing=12)
        self.action_meta = label("", "dim")
        self.action_meta.setWordWrap(True)
        row.addWidget(self.action_meta,1)
        self.confirm_button = button("Confirm step",self.confirm)
        self.confirm_button.setObjectName("primary")
        self.confirm_button.setToolTip("Record this step after completing it in your match.")
        row.addWidget(self.confirm_button)
        next_col.addLayout(row)
        left.addWidget(next_card)
        totals, summary = card(margins=(16,12,16,12))
        measures = layout(horizontal=True,spacing=12)
        self.numbers = []
        self.metric_labels = []
        for name in ["REMAINING COST","EST. ROUTE TIME","POINTS NEEDED"]:
            box = layout(spacing=2)
            metric_name = label(name, "metricName")
            self.metric_labels.append(metric_name)
            box.addWidget(metric_name)
            n=label("","number")
            box.addWidget(n)
            self.numbers.append(n)
            measures.addLayout(box,1)
        summary.addLayout(measures)
        left.addWidget(totals)

        player, controls = card()
        row = layout(horizontal=True)
        row.addWidget(label("Match state","section"))
        row.addStretch()
        self.edit_button = button("Edit state", self.edit_state)
        row.addWidget(self.edit_button)
        controls.addLayout(row)
        self.zone = combo([(r["name"],k) for k,r in self.profile.zones.items()])
        self.points = W.QSpinBox()
        self.points.setRange(0,2147483647)
        self.points.setGroupSeparatorShown(True)
        self.points.setKeyboardTracking(False)
        form = layout(horizontal=True,spacing=10)
        form.addLayout(bind_field("Current zone",self.zone),1)
        form.addLayout(bind_field("Available points",self.points),1)
        controls.addLayout(form)
        self.marker = None
        if map_id == COLD_WAR:
            self.marker = combo([("Not seen yet", ""), ("Crash Site", "marker_crash"), ("Pond", "marker_pond")])
            self.marker.setToolTip("Enter the marked surface tunnel shown in the Dark Aether, or select a location to preview that scenario.")
            controls.addLayout(bind_field("Marked Aether Tunnel", self.marker))
            self.marker.currentIndexChanged.connect(self.change_marker)
        self.state_summary = label("","small")
        controls.addWidget(self.state_summary)
        right.addWidget(player)
        obj, targets = card()
        targets.addWidget(label("Objectives","section"))
        self.target_boxes = {}
        self.target_prices = {}
        for key, goal in self.profile.goals.items():
            row = layout(horizontal=True)
            check = Check(goal["name"])
            check.setIcon(icon(key,AMBER,17))
            check.setChecked(key in self.goals)
            check.toggled.connect(lambda checked,k=key:self.toggle(k,checked))
            self.target_boxes[key] = check
            row.addWidget(check)
            row.addStretch()
            self.target_prices[key] = label("", "small")
            row.addWidget(self.target_prices[key])
            targets.addLayout(row)
        right.addWidget(obj)
        settings, prefs = card()
        prefs.addWidget(label("Planning","section"))
        self.mode = combo([("Point economy","Economy"),("Speedrun","Speed"),("Balanced","Balanced")])
        self.budget = combo([("Full setup","Setup"),("Immediate","Immediate")])
        self.mode.setToolTip("Point economy minimizes spending. Speedrun minimizes estimated travel and interaction time.")
        self.budget.setToolTip("Full setup marks future purchases. Immediate requires enough points for the whole route.")
        prefs.addLayout(bind_field("Optimize for",self.mode))
        prefs.addLayout(bind_field("Budget policy",self.budget))
        self.weight_box = container()
        wlayout = layout(self.weight_box,True)
        wlayout.addWidget(label("Economy weight","small"))
        self.weight = W.QSpinBox()
        self.weight.setRange(0,100)
        self.weight.setValue(options.economy_weight)
        self.weight.setSuffix("%")
        self.weight.setToolTip("At 50%, 1,000 points and 30 seconds have equal weight.")
        wlayout.addWidget(self.weight)
        prefs.addWidget(self.weight_box)
        right.addWidget(settings)
        right.addStretch()
        self.mode.setCurrentIndex(self.mode.findData(options.mode))
        self.budget.setCurrentIndex(self.budget.findData(options.budget))
        self.map_selector.currentIndexChanged.connect(self.switch_map)
        self.zone.currentIndexChanged.connect(self.change_zone)
        self.points.valueChanged.connect(self.change_points)
        for control in [self.mode,self.budget]:
            control.currentIndexChanged.connect(self.refresh)
        self.weight.valueChanged.connect(self.refresh)
        self.refresh()

    def toggle(self, key, checked):
        if checked:
            self.goals.add(key)
        else:
            self.goals.discard(key)
        self.refresh()

    def change_marker(self):
        selected = self.marker.currentData()
        match = self.session.match
        flags = match.world.flags - MARKERS
        if selected:
            flags = flags | {selected}
        world = replace(match.world, flags=flags)
        self.session.record("MARKER_UPDATED", f"Aether Tunnel: {self.marker.currentText()}", replace(match, world=world))
        self.refresh()

    def change_points(self, value):
        self.session.record("POINTS_UPDATED",f"Set balance to {value:,} pts",replace(self.session.match,points=value))
        self.refresh()

    def change_zone(self):
        key = self.zone.currentData()
        current = self.session.match
        updated = replace(current, world=replace(current.world,zone=key))
        try:
            self.session.record("ZONE_CHANGED",f"Moved to {self.profile.zones[key]['name']}",updated)
        except ValueError as exc:
            self.sync_state()
            W.QMessageBox.information(self,"Check match state",str(exc) + " Use Edit state to change both together.")
        self.refresh()

    def edit_state(self):
        if StateEditor(self.session,self).exec():
            self.refresh()

    def confirm(self):
        if self.plan.steps:
            self.session.confirm(self.plan.steps[0])
            self.refresh()

    def undo(self):
        self.session.undo()
        self.refresh()

    def reset(self):
        self.session.reset()
        self.refresh()

    def sync_state(self):
        match = self.session.match
        for widget, setter in [(self.zone,lambda:self.zone.setCurrentIndex(self.zone.findData(match.world.zone))),
                               (self.points,lambda:self.points.setValue(match.points))]:
            old = widget.blockSignals(True)
            setter()
            widget.blockSignals(old)

    def refresh(self):
        match = self.session.match
        self.sync_state()
        if self.marker:
            selected = next(iter(match.world.flags & MARKERS), "")
            old = self.marker.blockSignals(True)
            self.marker.setCurrentIndex(self.marker.findData(selected))
            self.marker.blockSignals(old)
        options = Options(self.mode.currentData(),self.budget.currentData(),self.weight.value())
        self.weight_box.setVisible(options.mode=="Balanced")
        self.plan = find_route(self.profile,match,self.goals,options,self.session.prohibited)
        plan = self.plan
        self.map.show_state(match.world,self.goals,plan.steps,self.session.prohibited)
        self.state_summary.setText(f"Power {'on' if 'power' in match.world.flags else 'off'}   ·   {len(match.world.opened)} of {len(self.profile.doors)} doors open")
        self.undo_button.setEnabled(bool(self.session.history))
        self.reset_button.setEnabled(match != self.profile.initial or bool(self.session.prohibited))
        readiness = tuple(plan.readiness(match.points))
        self.confirm_button.setEnabled(bool(plan.steps) and readiness[0] == 0)
        self.confirm_button.setVisible(bool(plan.steps))
        if plan.steps:
            first = plan.steps[0]
            place = self.profile.zones[match.world.zone]["name"]
            if first.origin != first.dest:
                place += " → " + self.profile.zones[first.dest]["name"]
            price = f"{first.cost:,} pts" if first.cost else "Free"
            detail = f"{place}  ·  {price}  ·  ~{first.seconds}s"
            if readiness[0]:
                detail += f"  ·  Need {readiness[0]:,} more pts"
            elif first.reserve:
                detail += f"  ·  Carry {step_balances(plan.steps)[0]:,} pts"
            if plan.to_marker:
                detail += "  ·  Route ends at the tunnel reveal"
            self.action_title.setText(first.label)
            self.action_meta.setText(detail)
        else:
            title,detail = {
                "visit_required":("Re-enter the Dark Aether", "Follow the next anomaly in-game. In Edit state, record your current zone and active visit to continue with the part."),
                "marker_required":("Set the Aether Tunnel marker", "Select Crash Site or Pond once its marker appears. Full setup can plan to the reveal."),
                "complete":("Objectives complete","All selected objectives are recorded in this match."),
                "no_targets":("Choose an objective","Select a utility or power to calculate a route."),
                "over_budget":("More points needed",f"Earn {plan.shortfall:,} more pts for the cheapest route, or select Full setup to see future steps."),
                "unreachable":("No route available","Review doors marked Keep closed and your observed match state."),
            }[plan.status]
            self.action_title.setText(title)
            self.action_meta.setText(detail)
        vals = [f"{plan.cost:,} pts", f"~{time_text(plan.seconds)}" if plan.seconds else "0s",f"{plan.shortfall:,} pts"]
        self.metric_labels[0].setText("COST TO REVEAL" if plan.to_marker else "REMAINING COST")
        self.metric_labels[1].setText("TIME TO REVEAL" if plan.to_marker else "EST. ROUTE TIME")
        if plan.status in {"unreachable", "marker_required", "visit_required"}:
            vals = ["—","—","—"]
        elif plan.status=="over_budget":
            vals[1] = "—"
        for control,value in zip(self.numbers,vals):
            control.setText(value)
        self.route_table.setRowCount(len(plan.steps))
        for i,(step,short) in enumerate(zip(plan.steps,readiness)):
            funding = f"Need {short:,}" if short else "Ready"
            for j,value in enumerate((str(i+1),step.label,f"{step.cost:,}",funding)):
                item = W.QTableWidgetItem(value)
                if j==3:
                    item.setForeground(G.QColor(AMBER if short else TEAL))
                item.setToolTip(f"{self.profile.zones[step.origin]['name']}  →  {self.profile.zones[step.dest]['name']}  ·  ~{step.seconds}s")
                self.route_table.setItem(i,j,item)
        self.tabs.setTabText(1,f"Route steps ({len(plan.steps)})")
        self.history.clear()
        for event in reversed(self.session.history):
            self.history.addItem(f"{event.when:%H:%M:%S}   {event.detail}   ·   {event.after.points:,} pts")
        if not self.session.history:
            initial = self.profile.initial
            self.history.addItem(f"Match started in {self.profile.zones[initial.world.zone]['name']} with {initial.points:,} points.")
        for key,check in self.target_boxes.items():
            goal = self.profile.goals[key]
            price = goal["price"]
            if key in self.profile.perk_flags:
                price += self.profile.perk_surcharge(match.world)
            price_text = f"{price:,} pts" if price else ("Switch" if key == "power" else "Build")
            self.target_prices[key].setText("Done" if key in match.world.flags else price_text)
            check.setText(self.profile.goals[key]["name"] + ("  ✓" if key in match.world.flags else ""))


def configure_app(app):
    app.setStyle("Fusion")
    app.setFont(font(13))
    palette = G.QPalette()
    for role, color in {
        "Window":"#151a18", "WindowText":"#e4e8e0", "Base":"#141a16",
        "AlternateBase":"#252e26", "Text":"#e4e8e0", "Button":"#2b322b",
        "ButtonText":"#e4e8e0", "Highlight":"#496752", "HighlightedText":"#ffffff",
        "Light":"#5f6c60", "Mid":"#455045", "Dark":"#171e19"
    }.items():
        palette.setColor(getattr(G.QPalette.ColorRole, role),G.QColor(color))
    app.setPalette(palette)


def launch(profile=None):
    app = W.QApplication.instance() or W.QApplication([])
    configure_app(app)
    win = Companion(profile)
    win.show()
    return app.exec()
