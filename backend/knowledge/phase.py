"""
knowledge/phase.py

What phase is a substance in at a given temperature and pressure, and how dense
is it?  Answered from the tables stored in molecules.json (vapour pressure and
saturated-liquid density versus temperature, melting / boiling / critical
points) -- not by the language model.

Simplifications (also stated to the user when they matter):
  * gas density uses the ideal-gas law (fine for the dilute gases this is used on;
    the simulation then MEASURES the real pressure and compares);
  * liquid density is the saturated-liquid value at T (pressure dependence of a
    liquid is small);
  * the solid region is bounded by the 1-atm melting point (and, for helium, the
    minimum solidification pressure).
"""

from backend.units import KB_J, NA

ATM_PA = 101325.0


def _interp(rows, T, col):
    """Piecewise-linear interpolation of column `col` over T; None if outside."""
    if T < rows[0][0] or T > rows[-1][0]:
        return None
    for a, b in zip(rows, rows[1:]):
        if a[0] <= T <= b[0]:
            f = (T - a[0]) / (b[0] - a[0])
            return a[col] + f * (b[col] - a[col])
    return rows[-1][col]


def vapour_pressure_atm(mol, T):
    tab = mol.get("saturation_table")
    if not tab or not tab["rows"]:
        return None
    rows = tab["rows"]
    if T > rows[-1][0]:                       # above the table (near/over critical)
        return rows[-1][1] if T < mol["thermo"]["critical_T_K"] else None
    if T < rows[0][0]:
        return 0.0
    return _interp(rows, T, 1)


def state_at(mol, T_K, P_atm):
    """'solid' | 'liquid' | 'gas' | 'supercritical' for a pure substance."""
    th = mol.get("thermo") or {}
    if not th:
        return "unknown"
    tc, pc = th["critical_T_K"], th["critical_P_atm"]
    if T_K >= tc:
        return "supercritical" if P_atm >= pc else "gas"
    min_p = mol.get("solid_min_pressure_atm")
    if min_p is not None:
        if P_atm >= min_p and T_K < 4.0:
            return "solid"
    elif T_K < th["melting_point_K"]:
        return "solid"
    ps = vapour_pressure_atm(mol, T_K)
    if ps is None:
        return "gas"
    return "liquid" if P_atm > ps else "gas"


def mass_density_g_cm3(mol, T_K, P_atm, state):
    """Mass density for the given state (None if the table cannot say)."""
    m_g = mol["molar_mass_g_mol"]
    if state in ("gas", "supercritical"):
        n = P_atm * ATM_PA / (KB_J * T_K)                 # molecules / m^3 (ideal gas)
        return n * m_g / NA / 1e6                          # g / cm^3
    if state == "liquid":
        rows = mol["saturation_table"]["rows"]
        rho = _interp(rows, T_K, 2)
        if rho is None:                                    # slightly outside the table: nearest end
            rho = rows[0][2] if T_K < rows[0][0] else rows[-1][2]
        return rho
    if state == "solid":
        ref = mol.get("solid_density_ref")
        return ref["rho_g_cm3"] if ref else None
    return None


def typical_conditions(mol, state):
    """A representative (T_K, P_atm) at which `mol` is in `state`; None if it
    has no such state at ordinary pressure.  Used for the Solid / Liquid / Gas
    buttons."""
    th = mol.get("thermo") or {}
    if not th:
        return None
    tm, tb, tc = th["melting_point_K"], th["boiling_point_K"], th["critical_T_K"]
    if state == "gas":
        if tb < 250:
            return (298.15, 1.0)
        return (tb + 30.0, 1.0)
    if state == "liquid":
        if tb <= tm:                                    # no liquid at 1 atm (e.g. CO2 sublimes): use pressure above the triple point
            tt = th.get("triple_T_K") or tm
            t = tt + 0.2 * (tc - tt)
            ps = vapour_pressure_atm(mol, t)
            return (t, 1.5 * ps) if ps else None
        if tm < 298.15 < tb:
            return (298.15, 1.0)
        t = tm + 0.5 * (tb - tm) if tb > tm else tb
        if mol.get("solid_min_pressure_atm") is not None:       # helium
            t = min(3.0, 0.7 * tb)
        return (t, 1.0)
    if state == "solid":
        if not mol.get("solid_density_ref"):
            return None
        if mol.get("solid_min_pressure_atm") is not None:
            return (mol["solid_density_ref"]["T_K"], mol["solid_min_pressure_atm"] + 5.0)
        return (0.8 * tm, 1.0)
    return None
