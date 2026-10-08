# Generates the OPEN_WEIGHT LTspice schematics (.asc) as properly wired circuits.
# WARNING: running it overwrites the .asc files in this folder (hand edits made
# in LTspice are lost). Reuse the Sch class / PINS table for other projects.
import os

OUT = os.path.dirname(os.path.abspath(__file__))

PINS = {  # R0 pin coordinates
    "res": {"A": (16, 16), "B": (16, 96)},
    "cap": {"A": (16, 0), "B": (16, 64)},
    "polcap": {"A": (16, 0), "B": (16, 64)},
    "ind": {"A": (16, 16), "B": (16, 96)},
    "voltage": {"+": (0, 16), "-": (0, 96)},
    "current": {"+": (0, 0), "-": (0, 80)},
    "schottky": {"A": (16, 0), "K": (16, 64)},
    "LED": {"A": (16, 0), "K": (16, 64)},
    "pmos": {"D": (48, 0), "G": (0, 80), "S": (48, 96)},
    "LT3042": {"IN": (-240, -144), "EN": (-240, 0), "PG": (-240, 112), "ILIM": (96, 160),
               "PGFB": (224, 160), "SET": (-128, 160), "GND": (0, 160), "OUTS": (304, 80),
               "OUT": (304, 0)},
    "TPS61086_behav": {"IN": (-96, -64), "EN": (-96, 0), "MODE": (-96, 64), "SW": (96, -64),
                       "FB": (96, 32), "COMP": (-48, 96), "SS": (48, 96), "GND": (0, 96)},
}


def tf(rot, p):
    x, y = p
    return {"R0": (x, y), "R90": (-y, x), "R180": (-x, -y), "R270": (y, -x),
            "M0": (-x, y), "M180": (x, -y)}[rot]


WIN = {  # attribute windows for rotated two-pin parts (symbol frame)
    ("res", "R270"): ["WINDOW 0 32 56 VTop 2", "WINDOW 3 0 56 VBottom 2"],
    ("ind", "R270"): ["WINDOW 0 32 56 VTop 2", "WINDOW 3 4 56 VBottom 2"],
    ("schottky", "R270"): ["WINDOW 0 32 32 VTop 2", "WINDOW 3 0 32 VBottom 2"],
}


class Sch:
    def __init__(self, w, h):
        self.head = ["Version 4", f"SHEET 1 {w} {h}"]
        self.w, self.f, self.s, self.t = [], [], [], []
        self.buses = []

    def part(self, sym, pin, at, name, value=None, rot="R0", spiceline=None, value2=None,
             windows=None):
        """Place `sym` so that its pin `pin` lands on `at`; return all pin positions."""
        px, py = tf(rot, PINS[sym][pin])
        ox, oy = at[0] - px, at[1] - py
        s = [f"SYMBOL {sym} {ox} {oy} {rot}"]
        s += windows if windows is not None else WIN.get((sym, rot), [])
        s.append(f"SYMATTR InstName {name}")
        if value is not None:
            s.append(f"SYMATTR Value {value}")
        if value2:
            s.append(f"SYMATTR Value2 {value2}")
        if spiceline:
            s.append(f"SYMATTR SpiceLine {spiceline}")
        self.s += s
        return {k: (ox + tf(rot, v)[0], oy + tf(rot, v)[1]) for k, v in PINS[sym].items()}

    def wire(self, *pts):
        for a, b in zip(pts[:-1], pts[1:]):
            self.w.append(f"WIRE {a[0]} {a[1]} {b[0]} {b[1]}")

    def bus(self, y, xs):
        """Horizontal rail split at every tap so each tap is a real junction."""
        xs = sorted(set(xs))
        for a, b in zip(xs[:-1], xs[1:]):
            self.wire((a, y), (b, y))

    def gnd(self, p, drop=0):
        if drop:
            self.wire(p, (p[0], p[1] + drop))
            p = (p[0], p[1] + drop)
        self.f.append(f"FLAG {p[0]} {p[1]} 0")

    def label(self, p, name):
        self.f.append(f"FLAG {p[0]} {p[1]} {name}")

    def text(self, x, y, txt, size=2, directive=False):
        self.t.append(f"TEXT {x} {y} Left {size} {'!' if directive else ';'}{txt.replace(chr(10), chr(92) + 'n')}")

    def save(self, fname, spread=True):
        def X(x):
            x = int(x)
            return x + (128 if x >= 600 else 0) + (128 if x >= 3600 else 0) if spread else x

        def fix(line):
            t = line.split(" ")
            if t[0] == "WIRE":
                t[1], t[3] = str(X(t[1])), str(X(t[3]))
            elif t[0] in ("FLAG", "TEXT"):
                t[1] = str(X(t[1]))
            elif t[0] == "SYMBOL":
                t[2] = str(X(t[2]))
            return " ".join(t)
        self.w = [fix(l) for l in self.w]
        self.f = [fix(l) for l in self.f]
        self.t = [fix(l) for l in self.t]
        self.s = [fix(l) for l in self.s]
        with open(os.path.join(OUT, fname), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(self.head + self.w + self.f + self.s + self.t) + "\n")


MODELS = (
    ".model PMEG2010EA D(Is=1.686u Rs=.1249 N=1.015 Cjo=90.86p M=.4542 Eg=.69 Xti=2 BV=21 IBV=1u Vj=.1939 Iave=1 Vpk=20 mfg=NXP type=Schottky)\n"
    ".model QTLP690C D(Is=1e-22 Rs=6 N=1.5 Cjo=50p Xti=100 Iave=160m Vpk=5 mfg=Fairchild type=LED)\n"
    ".model SI2303_APPROX VDMOS(pchan Vto=-1.6 Kp=4 Rd=60m Rs=40m Rg=5 Rb=50m Cgdmax=.2n Cgdmin=.03n Cgs=.35n Cjo=.1n Is=10p ksubthres=.1 Vds=-30 Ron=190m Qg=4n)"
)



# ------------------------------------------------------------------ blocks
IC_WIN = ["WINDOW 0 0 -136 Center 2", "WINDOW 3 0 -112 Center 1"]


def boost(s):
    """TPS61086 3.3 V -> 6 V (sheet 6). +3.3V rail at y=0; +6V rail from x=960."""
    Y = 0
    rail33 = [0]
    v = s.part("voltage", "+", (0, Y), "V1", "PWL(0 0 100u 3.3)", spiceline="Rser=20m",
               windows=["WINDOW 0 -104 48 Left 2", "WINDOW 3 -176 80 Left 1", "WINDOW 39 -176 104 Left 1"])
    s.gnd(v["-"])
    s.text(-72, 176, "Host +3.3V (J1 pin 1)", 1)
    for x, n, val, sl in ((176, "C21", "10u", "Rser=5m"), (304, "C22", "1u", "Rser=10m")):
        c = s.part("cap", "A", (x, Y), n, val, spiceline=sl)
        s.gnd(c["B"])
        rail33.append(x)
    i = s.part("current", "+", (432, Y), "I_DVDD", "1m")
    s.gnd(i["-"])
    s.text(400, 176, "AD7190 DVDD", 1)
    r3 = s.part("res", "A", (560, Y), "R3", "100")
    d1 = s.part("LED", "A", (560, 128), "D1", "QTLP690C")
    s.wire(r3["B"], d1["A"])
    s.gnd(d1["K"])
    rail33 += [432, 560, 640, 704]
    s.label((640, Y), "+3.3V")
    # inductor, switch node, diode
    l1 = s.part("ind", "A", (704, Y), "L1", "4.7u", rot="R270", spiceline="Rser=78m")
    s.text(672, -112, "Wurth 7447785004", 1)
    d3 = s.part("schottky", "A", (896, Y), "D3", "PMEG2010EA", rot="R270")
    s.text(872, -112, "PMEG2010AEH", 1)
    s.wire(l1["B"], (848, Y), (896, Y))
    s.label((848, Y), "SW")
    ic = s.part("TPS61086_behav", "SW", (896, 192), "IC2", windows=IC_WIN)
    s.wire(ic["SW"], (896, Y))
    s.wire(ic["IN"], (640, 192), (640, Y))
    s.wire(ic["EN"], (640, 256), (640, 192))
    s.wire(ic["MODE"], (672, 320), (672, 352))
    s.gnd((672, 352))
    s.text(560, 400, "MODE = GND\n(Power Save Mode)", 1)
    s.gnd(ic["GND"], 48)
    # compensation (COMP) and soft-start (SS)
    s.wire(ic["COMP"], (752, 400), (752, 432), (704, 432))
    r18 = s.part("res", "A", (704, 432), "R18", "37.4k")
    c17 = s.part("cap", "A", (704, 560), "C17", "2.2n")
    s.wire(r18["B"], c17["A"])
    s.gnd(c17["B"])
    s.label((752, 400), "COMP")
    s.label(r18["B"], "CC")
    s.wire(ic["SS"], (848, 432), (912, 432))
    c18 = s.part("cap", "A", (912, 432), "C18", "0.1u")
    s.gnd(c18["B"])
    s.label((848, 432), "SS")
    # feedback divider
    r17 = s.part("res", "A", (1056, Y), "R17", "69.8k")
    r15 = s.part("res", "A", (1056, 208), "R15", "18k")
    s.wire(r17["B"], (1056, 144), r15["A"])
    s.gnd(r15["B"])
    s.wire(ic["FB"], (992, 288), (992, 144), (1056, 144))
    s.label((992, 144), "FB")
    rail6 = [d3["K"][0], 1056]
    for x, n in ((1184, "C19"), (1312, "C20")):
        c = s.part("cap", "A", (x, Y), n, "10u", spiceline="Rser=5m")
        s.gnd(c["B"])
        rail6.append(x)
    s.bus(Y, rail33)
    s.text(0, -240, "TPS61086 BOOST  +3.3V -> +6V   (schematic page 6)", 3)
    return rail6


def ldo(s, rail6):
    """LT3042 +6V -> +5VA (sheet 5) + loads on +5VA."""
    Y = 0
    c16 = s.part("cap", "A", (1472, Y), "C16", "4.7u", spiceline="Rser=5m")
    s.gnd(c16["B"])
    r14 = s.part("res", "A", (1600, Y), "R14", "200k")
    u2 = s.part("LT3042", "IN", (1792, Y), "U2", "LT3042")
    s.wire(r14["B"], (1600, 256), (1696, 256), u2["PG"])
    s.label((1696, 256), "PG")
    s.wire(u2["EN"], (1712, 144), (1712, Y))
    s.bus(Y, rail6 + [1392, 1472, 1600, 1712, 1792])
    s.label((1392, Y), "+6V")
    # SET network
    s.wire(u2["SET"], (1904, 400), (1840, 400), (1744, 400))
    r9 = s.part("res", "A", (1904, 400), "R9", "50k")
    s.gnd(r9["B"])
    c14 = s.part("polcap", "A", (1744, 400), "C14", "2.2u", spiceline="Rser=3")
    s.gnd(c14["B"])
    s.label((1840, 400), "SET")
    s.text(1664, 560, "C14 = TAJA225K016 (tantalum)", 1)
    s.gnd(u2["GND"], 48)
    s.gnd(u2["ILIM"], 48)
    # PGFB divider
    Y5 = 144
    r12 = s.part("res", "A", (2528, Y5), "R12", "715k")
    r13 = s.part("res", "A", (2528, 336), "R13", "50k")
    s.wire(r12["B"], (2528, 288), r13["A"])
    s.gnd(r13["B"])
    s.wire(u2["PGFB"], (2256, 384), (2448, 384), (2448, 288), (2528, 288))
    s.label((2448, 288), "PGFB")
    s.wire(u2["OUTS"], (2400, 224), (2400, Y5))
    rail5 = [u2["OUT"][0], 2400, 2464, 2528]
    x = 2656
    for n, val, esr in (("C15", "10u", "3m"), ("C13", "4.7u", "3m"), ("C4", "10u", "3m"),
                        ("C12", "10u", "3m"), ("C3", "0.1u", "20m"), ("C26", "0.1u", "20m")):
        c = s.part("cap", "A", (x, Y5), n, val, spiceline=f"Rser={esr}")
        s.gnd(c["B"])
        rail5.append(x)
        x += 128
    s.text(2912, 272, "C4 C12 C3 C26 = AD7190 AVDD decoupling", 1)
    r16 = s.part("res", "A", (3424, Y5), "R16", "620")
    d4 = s.part("LED", "A", (3424, 272), "D4", "QTLP690C")
    s.wire(r16["B"], d4["A"])
    s.gnd(d4["K"])
    i = s.part("current", "+", (3552, Y5), "I_AVDD", "4.5m")
    s.gnd(i["-"])
    s.text(3584, 256, "AD7190 AVDD", 1)
    rail5 += [3424, 3552]
    s.label((2464, Y5), "+5VA")
    s.text(1472, -240, "LT3042 LDO  +6V -> +5VA   (schematic page 5)", 3)
    return rail5


def excitation(s, rail5, p3):
    """Q1 high-side switch + load-cell bridge (sheet 4)."""
    Y5 = 144
    q1 = s.part("pmos", "S", (3744, Y5), "Q1", "SI2303_APPROX", rot="M180",
                windows=["WINDOW 0 64 -40 Left 2", "WINDOW 3 64 -8 Left 1"])
    s.wire(q1["G"], (3648, 160), (3648, 208))
    r10 = s.part("res", "A", (3648, 208), "R10", "1k",
                 windows=["WINDOW 0 -8 40 Right 2", "WINDOW 3 -8 72 Right 2"])
    vp = s.part("voltage", "+", (3648, 400), "V_P3", p3)
    s.wire(r10["B"], (3648, 352), (3648, 400))
    s.gnd(vp["-"])
    s.label((3648, 352), "P3")
    s.text(3600, 528, "AD7190 P3 (GPOCON)", 1)
    s.text(3808, 16, "SI2303CDS\n(approx. model)", 1)
    rail5.append(3744)
    # SENSE+ / SENSE- network
    YP, YN = 448, 640
    s.wire(q1["D"], (3744, YP))
    xs = [3744, 3808]
    for x, n, val in ((3872, "C11", "0.1u"), (4000, "C23", "0.1u"), (4128, "C7", "10n")):
        c = s.part("cap", "A", (x, YP), n, val)
        s.gnd(c["B"])
        xs.append(x)
    rb = s.part("res", "A", (4256, YP), "R_BRIDGE", "{Rbridge}")
    c5 = s.part("cap", "A", (4448, YP), "C5", "0.1u")
    xs += [4256, 4448]
    s.bus(YP, xs)
    s.label((3808, YP), "SENSE+")
    s.wire(rb["B"], (4256, YN))
    s.wire(c5["B"], (4448, YN))
    c9 = s.part("cap", "A", (4640, YN), "C9", "10n")
    s.gnd(c9["B"])
    rsw = s.part("res", "A", (4768, YN), "R_BPDSW", "3")
    s.gnd(rsw["B"])
    s.bus(YN, [4256, 4448, 4544, 4640, 4768])
    s.label((4544, YN), "SENSE-")
    s.text(4192, 720, "load cell\n(350 ohm bridge)", 1)
    s.text(4720, 800, "AD7190 BPDSW\n(low-side switch)", 1)
    s.text(3600, -240, "LOAD-CELL EXCITATION   (schematic page 4)", 3)


def six_volt_source(s, value, value2=None, note="+6V (settled boost output)"):
    v = s.part("voltage", "+", (1312, 0), "V_6V", value, spiceline="Rser=10m", value2=value2)
    s.gnd(v["-"])
    s.text(1200, 176, note, 1)
    return [1312]


def header(s, title, sub):
    s.text(0, -448, title, 4)
    s.text(0, -376, sub, 2)


# ============================================================ 01 start-up
s = Sch(5000, 1400)
header(s, "OPEN_WEIGHT - 01 - Power chain start-up : +3.3V -> TPS61086 -> +6V -> LT3042 -> +5VA",
       "Switching simulation of the complete start-up (600 ms): +5VA needs about 5 x R9 x C14 = 550 ms "
       "to settle at 5 V. Q1 kept OFF (P3 high) as after reset.\n"
       "Long run (about 30 min, 2.8 GB of waveforms). Set .tran 0 25m to look at the boost soft-start only.")
r6 = boost(s)
r5 = ldo(s, r6)
excitation(s, r5, "5")
s.bus(144, r5)
# trtol/reltol: 3.5x faster than the LTspice defaults, same results within 0.2 %
s.text(0, 960, ".tran 0 600m\n.options method=gear trtol=7 reltol=0.003", 2, True)
s.text(0, 1040, ".param Rbridge=350", 2, True)
s.text(0, 1080, ".save V(+3.3V) V(+6V) V(+5VA) V(SS) V(SET) V(PG) I(L1)", 2, True)
s.text(0, 1120, ".meas tran V6_final AVG V(+6V) FROM 590m TO 600m\n.meas tran V6_max MAX V(+6V)\n"
               ".meas tran T6_90 WHEN V(+6V)=5.436 RISE=1\n.meas tran IL_peak MAX I(L1)\n"
               ".meas tran T_PG WHEN V(PG)=3 RISE=1\n.meas tran V5_25m FIND V(+5VA) AT 25m\n"
               ".meas tran T5_99 WHEN V(+5VA)=4.95 RISE=1\n.meas tran T5_999 WHEN V(+5VA)=4.995 RISE=1\n"
               ".meas tran V5_final AVG V(+5VA) FROM 590m TO 600m", 2, True)
s.text(1664, 960, MODELS, 1, True)
s.save("01_Power_Chain_Startup.asc")

# ============================================================ 02 LDO start-up
s = Sch(5000, 1400)
header(s, "OPEN_WEIGHT - 02 - LT3042 start-up (1 s), Power-Good and load-cell excitation turn-on",
       "The boost is replaced by its settled output (12 ms ramp, see 01). At t = 800 ms P3 goes low: "
       "Q1 turns ON and the 350 ohm bridge loads +5VA.")
r5 = ldo(s, six_volt_source(s, "PWL(0 0 12m 6.04)", note="+6V from the boost\n(12 ms ramp)"))
excitation(s, r5, "PWL(0 5 800m 5 800.01m 0)")
s.bus(144, r5)
s.text(0, 960, ".tran 0 1 0 50u", 2, True)
s.text(0, 1000, ".param Rbridge=350", 2, True)
s.text(0, 1040, ".meas tran T_PG WHEN V(PG)=3 RISE=1\n.meas tran T_99 WHEN V(+5VA)=4.95 RISE=1\n"
               ".meas tran V5_before AVG V(+5VA) FROM 700m TO 790m\n.meas tran V5_min MIN V(+5VA) FROM 800m TO 810m\n"
               ".meas tran V5_after AVG V(+5VA) FROM 900m TO 1\n.meas tran V_EXC AVG V(SENSE+,SENSE-) FROM 900m TO 1", 2, True)
s.text(1664, 960, MODELS, 1, True)
s.save("02_LT3042_Startup.asc")

# ============================================================ 03 ripple
s = Sch(5000, 1400)
header(s, "OPEN_WEIGHT - 03 - Steady-state ripple : boost switching noise on +6V vs. +5VA (LT3042 PSRR)",
       "Starts from the operating point (.ic) with the excitation ON (worst-case load). "
       "Ripple measured over 3..4 ms, spectrum (FFT) over 2..6 ms.")
r6 = boost(s)
r5 = ldo(s, r6)
excitation(s, r5, "0")
s.bus(144, r5)
s.text(0, 960, ".tran 0 6m 0 5n uic", 2, True)
# numdgt > 6: waveforms saved in double precision (the +5VA ripple is in the nV range)
s.text(0, 1000, ".param Rbridge=350\n.options plotwinsize=0 numdgt=15", 2, True)
s.text(0, 1080, ".ic V(+6V)=6.04 V(+5VA)=5 V(SET)=5 V(SS)=1.5 V(COMP)=0.7 V(CC)=0.7 V(PG)=6 V(SENSE+)=4.9 V(SENSE-)=0.05", 2, True)
s.text(0, 1120, ".save V(+6V) V(+5VA) V(SW) I(L1) I(V1) V(COMP)", 2, True)
s.text(0, 1160, ".meas tran V6_avg AVG V(+6V) FROM 3m TO 4m\n.meas tran V6_pp PP V(+6V) FROM 3m TO 4m\n"
               ".meas tran V5_avg AVG V(+5VA) FROM 3m TO 4m\n.meas tran V5_pp PP V(+5VA) FROM 3m TO 4m\n"
               ".meas tran I3V3 AVG I(V1) FROM 3m TO 4m", 2, True)
s.text(1664, 960, MODELS, 1, True)
s.save("03_Power_Ripple.asc")

# ============================================================ 04 PSRR
s = Sch(5000, 1400)
header(s, "OPEN_WEIGHT - 04 - LT3042 PSRR : transfer from +6V ripple to +5VA",
       "PSRR(dB) = -20*log10|V(+5VA)/V(+6V)|.  1.2 MHz = TPS61086 switching frequency.")
r5 = ldo(s, six_volt_source(s, "6.04", value2="AC 1", note="+6V with\n1 V AC ripple"))
excitation(s, r5, "0")
s.bus(144, r5)
s.text(0, 960, ".ac dec 50 10 10Meg", 2, True)
s.text(0, 1000, ".param Rbridge=350", 2, True)
s.text(0, 1040, ".meas ac PSRR_1k FIND mag(V(+5VA)) AT 1k\n.meas ac PSRR_100k FIND mag(V(+5VA)) AT 100k\n.meas ac PSRR_1M2 FIND mag(V(+5VA)) AT 1.2Meg", 2, True)
s.text(1664, 960, MODELS, 1, True)
s.save("04_LT3042_PSRR.asc")

# ============================================================ 05 input filter
s = Sch(2000, 900)


def filt(s, ox, oy, tag, vp, vn, title):
    yp, yn = oy, oy + 256
    for y, v, r, rr, net_in, net_out, lab in ((yp, vp, "Rs_p", "R4", "INP", "OUTP", "AIN2"),
                                               (yn, vn, "Rs_n", "R5", "INN", "OUTN", "AIN1")):
        src = s.part("voltage", "+", (ox, y), f"V{r[-1]}{tag}", "2.5", value2=v)
        s.gnd(src["-"])
        rs = s.part("res", "A", (ox + 96, y), f"{r}{tag}", "175", rot="R270")
        s.wire((ox, y), rs["A"])
        r4 = s.part("res", "A", (ox + 320, y), f"{rr}{tag}", "100", rot="R270")
        s.wire(rs["B"], (ox + 248, y), r4["A"])
        s.label((ox + 248, y), f"{net_in}{tag}")
        s.wire(r4["B"], (ox + 496, y), (ox + 624, y), (ox + 752, y))
        s.label((ox + 752, y), f"{net_out}{tag}")
        s.text(ox + 784, y - 8, f"-> {lab}", 1)
    c27 = s.part("cap", "A", (ox + 496, yp), f"C27{tag}", "10n")
    s.gnd(c27["B"])
    c28 = s.part("cap", "A", (ox + 624, yp), f"C28{tag}", "0.1u")
    s.wire(c28["B"], (ox + 624, yn))
    c29 = s.part("cap", "A", (ox + 496, yn), f"C29{tag}", "10n")
    s.gnd(c29["B"])
    s.text(ox - 40, yn + 176, "load-cell output: 350 ohm bridge = 175 ohm per leg", 1)
    s.text(ox, oy - 128, title, 3)


header(s, "OPEN_WEIGHT - 05 - AD7190 analog input RC filter (J4 channel)",
       "R4/R5 = 100 ohm, C27/C29 = 10 nF, C28 = 100 nF. Same topology on J2 (R1/R2, C6, C8, C10).")
filt(s, 0, 0, "d", "AC 0.5", "AC 0.5 180", "DIFFERENTIAL signal")
filt(s, 1200, 0, "c", "AC 1", "AC 1", "COMMON-MODE disturbance")
s.text(0, 640, ".ac dec 100 10 100Meg", 2, True)
s.text(0, 680, ".meas ac F3dB_diff WHEN mag(V(OUTPd,OUTNd))=0.7071\n.meas ac F3dB_cm WHEN mag(V(OUTPc))=0.7071\n"
               ".meas ac ATT_diff_1M2 FIND mag(V(OUTPd,OUTNd)) AT 1.2Meg", 2, True)
s.save("05_AD7190_Input_Filter.asc", spread=False)
print("ok")
