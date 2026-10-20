"""
knowledge/checks.py

Domain validation: does this request make sense for THESE substances?  It runs
after the numeric range checks in validation/schema.py and uses the chemical
knowledge base.  It is the guard that stops the language model (or a slider)
from asking the engine for something physically meaningless.

    errors   -> the run is refused, with the reason
    warnings -> the run goes ahead, but the user is told what to expect
"""

from backend.engine import plan as P
from backend.knowledge import phase
from backend.knowledge.kb import get_kb
from backend.units import thermal_de_broglie_A

N_A = 6.02214076e23


def domain_check(plan):
    kb = get_kb()
    errors, warnings = list(plan.errors), list(plan.warnings)
    if errors:
        return errors, warnings
    prm = plan.params
    sp = {s.id: s for s in plan.species}

    # --- ions need a polar solvent, and the cell must be neutral --------------
    ions = [s for s in plan.species if s.mol.get("category") == "ion"]
    if ions and "water" not in sp:
        errors.append("Ions were requested without a polar solvent. Free ions have no meaningful gas-phase model here; "
                      "add water (e.g. 'sodium chloride dissolved in water').")
    net = sum(s.charge_total for s in plan.species)
    if net != 0:
        errors.append(f"The system is not electrically neutral (net charge {net:+d} e). Use equal numbers of positive and negative ions.")

    # --- time step / cost -----------------------------------------------------------
    if plan.engine == "charged" and plan.dt_fs > 2.5:
        errors.append(f"Time step {plan.dt_fs:.2f} fs is too large for rigid water (limit 2.5 fs): lower 'Timestep dt'.")
    if plan.engine == "reaxff":
        if plan.n_atoms > P.MAX_REAXFF_ATOMS:
            errors.append(f"Reactive simulations are limited to {P.MAX_REAXFF_ATOMS} atoms in this application "
                          f"(requested {plan.n_atoms}); reduce 'Particles'.")
        if plan.steps > P.MAX_REAXFF_STEPS:
            errors.append(f"Reactive run would need {plan.steps} steps at {P.REAXFF_DT_FS} fs "
                          f"({plan.total_fs / 1000:.1f} ps); the limit is {P.MAX_REAXFF_STEPS} steps -- shorten 'Run length'.")
    est = plan.estimated_seconds()
    if est > P.MAX_SECONDS:
        errors.append(f"Estimated run time {est / 60:.0f} min is too long; reduce particles or run length.")
    elif est > 90:
        warnings.append(f"This run will take roughly {est:.0f} s.")

    # --- is the model valid at this temperature? ----------------------------------------
    for s in plan.species:
        rng = s.model.get("valid_temperature_K")
        if rng and plan.engine != "hard_sphere" and not (rng[0] <= plan.T_K <= rng[1]):
            warnings.append(f"{s.mol['name']} model ({s.model['type']}) was parameterised near ambient conditions "
                            f"({rng[0]}-{rng[1]} K); {plan.T_K:.0f} K is outside that range, so quantitative results are unreliable.")
        if s.model["type"] == "lj_sphere" and plan.engine in ("lj", "hard_sphere"):
            lam = thermal_de_broglie_A(s.mol["molar_mass_g_mol"], max(plan.T_K, 0.1))
            sig = s.model["sites"][0]["sigma_A"]
            if lam / sig > 0.3:
                warnings.append(f"Quantum effects: at {plan.T_K:.1f} K the thermal de Broglie wavelength of {s.mol['name']} "
                                f"({lam:.2f} A) is {lam / sig:.2f} of its atomic size (> 0.3), so classical molecular dynamics "
                                f"is only qualitative here.")

    # --- phase consistency (knowledge base: critical point, melting point, saturated liquid density)
    mol = plan.primary.mol
    th = mol.get("thermo") or {}
    if th and len(plan.species) == 1 and plan.engine in ("lj", "hard_sphere"):
        rho_g = plan.number_density_A3 * 1e24 * mol["molar_mass_g_mol"] / N_A         # g/cm3
        state = prm.state
        tc, tm = th["critical_T_K"], th["melting_point_K"]
        rows = (mol.get("saturation_table") or {}).get("rows")
        rho_liq = phase._interp(rows, plan.T_K, 2) if rows else None
        if plan.T_K >= tc and state in ("solid", "liquid"):
            warnings.append(f"{mol['name']} at {plan.T_K:.0f} K is above its critical temperature ({tc:.1f} K): there is no distinct "
                            f"{state} phase; expect a dense supercritical fluid or gas.")
        elif state == "solid" and plan.T_K > tm * 1.05 and mol.get("solid_min_pressure_atm") is None:
            warnings.append(f"A solid was requested, but {plan.T_K:.0f} K is above the melting point of {mol['name']} ({tm:.1f} K): the lattice will melt.")
        elif state == "solid" and mol.get("solid_min_pressure_atm") and plan.T_K > 4.0:
            warnings.append(f"{mol['name']} does not solidify at ordinary pressure; it needs more than {mol['solid_min_pressure_atm']:.0f} atm "
                            f"and very low temperature. At {plan.T_K:.1f} K this will not stay solid.")
        elif state == "liquid" and rho_liq and rho_g < 0.5 * rho_liq:
            warnings.append(f"Density {rho_g:.3g} g/cm3 is far below the liquid density of {mol['name']} at {plan.T_K:.0f} K "
                            f"({rho_liq:.3g} g/cm3): expect a gas or a gas-liquid mixture, not a uniform liquid.")
        elif state == "gas" and rho_liq and rho_g > 0.5 * rho_liq and plan.T_K < tc:
            warnings.append(f"Density {rho_g:.3g} g/cm3 is liquid-like for {mol['name']} at {plan.T_K:.0f} K.")
    return errors, warnings
