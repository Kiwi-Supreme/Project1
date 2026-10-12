"""
units.py

Unit conversions between what a person says (kelvin, atm, nm, ps, g/cm^3) and
what the simulator uses.

Two systems are involved:
  * LAMMPS 'real' units: angstrom, femtosecond, kcal/mol, kelvin, atm, g/mol.
  * The interface's *reduced* (Lennard-Jones) units, in which the reference
    species' sigma, epsilon and mass are all 1.  They are what the sliders and
    the plots use, and they are what makes the law of corresponding states
    visible: T* = k_B T / epsilon, rho* = N sigma^3 / V, time in tau.

    tau = sigma * sqrt(m / epsilon)       (real units: see tau_fs below)
"""

import math

KB = 0.0019872041            # Boltzmann constant, kcal/(mol K)
NA = 6.02214076e23
MVV2E = 48.88821291 ** 2     # LAMMPS 'real' units: converts (g/mol)(A/fs)^2 to kcal/mol
ATM_A3_TO_KCALMOL = 101325.0 * 1e-30 * NA / 4184.0   # 1 atm * A^3 per mole, in kcal/mol
H_PLANCK = 6.62607015e-34
KB_J = 1.380649e-23

_TO_KELVIN = {"k": lambda v: v, "kelvin": lambda v: v,
              "c": lambda v: v + 273.15, "celsius": lambda v: v + 273.15, "°c": lambda v: v + 273.15,
              "f": lambda v: (v - 32.0) * 5.0 / 9.0 + 273.15, "fahrenheit": lambda v: (v - 32.0) * 5.0 / 9.0 + 273.15}
_TO_ATM = {"atm": 1.0, "bar": 0.986923, "pa": 1 / 101325.0, "kpa": 1000 / 101325.0, "mpa": 1e6 / 101325.0,
           "gpa": 1e9 / 101325.0, "torr": 1 / 760.0, "mmhg": 1 / 760.0, "psi": 0.068046}
_TO_ANGSTROM = {"a": 1.0, "å": 1.0, "angstrom": 1.0, "angstroms": 1.0, "nm": 10.0, "nanometer": 10.0,
                "nanometers": 10.0, "nanometre": 10.0, "nanometres": 10.0, "pm": 0.01}
_TO_FS = {"fs": 1.0, "femtosecond": 1.0, "femtoseconds": 1.0, "ps": 1e3, "picosecond": 1e3,
          "picoseconds": 1e3, "ns": 1e6, "nanosecond": 1e6, "nanoseconds": 1e6}
_TO_GCC = {"g/cm3": 1.0, "g/cm^3": 1.0, "g/ml": 1.0, "g/cc": 1.0, "kg/m3": 1e-3, "kg/m^3": 1e-3}


def to_kelvin(value, unit):
    return _TO_KELVIN[unit.lower()](float(value))


def to_atm(value, unit):
    return float(value) * _TO_ATM[unit.lower()]


def to_angstrom(value, unit):
    return float(value) * _TO_ANGSTROM[unit.lower()]


def to_fs(value, unit):
    return float(value) * _TO_FS[unit.lower()]


def to_g_cm3(value, unit):
    return float(value) * _TO_GCC[unit.lower().replace(" ", "")]


class Reference:
    """Reduced-unit system defined by one reference site (sigma [A], epsilon
    [kcal/mol], mass [g/mol])."""

    def __init__(self, sigma_A, eps_kcal, mass):
        self.sigma, self.eps, self.mass = float(sigma_A), float(eps_kcal), float(mass)

    @property
    def eps_over_k(self):                       # kelvin
        return self.eps / KB

    @property
    def tau_fs(self):
        return self.sigma * math.sqrt(MVV2E * self.mass / self.eps)

    def T_to_star(self, T_K):
        return T_K / self.eps_over_k

    def T_from_star(self, T_star):
        return T_star * self.eps_over_k

    def speed_unit_A_per_fs(self):
        return self.sigma / self.tau_fs


def thermal_de_broglie_A(mass_gmol, T_K):
    """Thermal de Broglie wavelength h / sqrt(2 pi m k T), in angstrom."""
    m = mass_gmol / 1000.0 / NA
    return H_PLANCK / math.sqrt(2 * math.pi * m * KB_J * T_K) * 1e10


def pressure_atm_from_virial(P_atm, V_A3, N, T_K):
    """Compressibility factor Z = P V / (N k T)."""
    return P_atm * V_A3 * ATM_A3_TO_KCALMOL / (N * KB * T_K)
