# Chemical knowledge base

This folder is the **single place the application gets chemistry from**.  The language
model never supplies a mass, a force-field parameter, a boiling point or a charge: it only
works out *which substance* the user means.  Everything else is looked up here and is
used to configure the molecular-dynamics simulation.

```
chemical_knowledge/
    elements.json          118 elements
    molecules.json         the substances the simulator can handle (atoms, molecules, ions)
    force_parameters.json  the force-field parameters each substance is simulated with
    interactions.json      kinds of intermolecular force, mixing rules, reactions
    build_dataset.py       regenerates the four files from published datasets (developer tool)
```

The program reads these files through `backend/knowledge/kb.py`; `phase.py` answers
"what phase is it in / how dense is it" from the tables stored here.

## Where the data comes from

| File | Content | Source |
|---|---|---|
| `elements.json` | atomic number, mass, group, period, electronegativity (Pauling), van der Waals and covalent radii, ionisation energy, melting/boiling point | the `mendeleev` Python package (compiled from NIST and the CRC Handbook) |
| `molecules.json` | formula, CAS number, SMILES, molar mass, composition | `chemicals` package (CAS registry data), masses summed from `elements.json` |
|  | critical point, melting/boiling point, triple point, acentric factor, dipole moment | `chemicals` / `thermo` (DIPPR, CRC Handbook, NIST WebBook-derived) |
|  | vapour-pressure and saturated-liquid-density tables vs temperature; solid density | `thermo` correlations (DIPPR / Yaws) |
|  | gas-phase formation enthalpy | `thermo` / DIPPR; **reaction enthalpies in `interactions.json` are computed from these, not typed** |
|  | molecular geometry (bond lengths, angles) | NIST CCCBDB experimental geometries (textbook values; the only hand-entered numbers, tagged with their source) |
|  | polarity, intermolecular forces, polar bonds | **derived** from the dipole moment, the electronegativity difference across each bond and the presence of an H bonded to N/O/F |
|  | helium solidifies only above ~25 atm | textbook fact (Keesom 1926), field `solid_min_pressure_atm` |
|  | water diffusion coefficient, O-O peak | experimental values used **only to compare results against** (Holz et al. 2000; Soper 2000) |
| `force_parameters.json` | Lennard-Jones sigma and epsilon of neutral species | LJ parameters tabulated in `chemicals` (Poling, Prausnitz & O'Connell 2001; Magalhaes et al. 2013). Rule used to choose between tabulated sets (recorded in each entry): discard implausible sets (sigma outside 2-5 A, epsilon/k < 5 K), then keep the set whose predicted critical temperature 1.31 eps/k (the Lennard-Jones fluid's critical point) is closest to the **experimental** critical temperature. Rejected sets are stored too |
|  | water (TIP3P: charges, sigma, epsilon, geometry, bond/angle constants) | Jorgensen et al., J. Chem. Phys. 79, 926 (1983), read from OpenMM's `tip3p.xml` |
|  | Na+ and Cl- | Joung & Cheatham, J. Phys. Chem. B 112, 9020 (2008), read from OpenMM's `amber14/tip3p.xml` |
|  | reactive force field | ReaxFF CHO, Chenoweth, van Duin & Goddard, J. Phys. Chem. A 112, 1040 (2008) (file shipped with LAMMPS) |
| `interactions.json` | list of interaction types, mixing rule, ionic/solvent rules | general-chemistry classification of intermolecular forces |

Nothing is "tuned until it looks right". If a value could not be sourced it is not in the
file, and the simulator refuses that substance rather than guessing.

## What is in each substance entry (`molecules.json`)

`name`, `aliases`, `formula`, `cas`, `smiles`, `category` (`noble_gas_atom`, `diatomic_molecule`,
`polyatomic_molecule`, `ion`, `ionic_compound`), `n_atoms`, `composition`, `net_charge`,
`molar_mass_g_mol`, `monatomic`, `structure` (geometry, atoms with coordinates, bonds with
order), `polarity` (dipole, polar?, largest bond electronegativity difference), `intermolecular_forces`,
`thermo` (melting, boiling, critical point, triple point), `saturation_table`, `solid_density_ref`,
`reactivity` (class, description, whether ReaxFF covers it), `force_model` (key into
`force_parameters.json`).

## How the simulation uses it

| Knowledge-base field | Where it changes the simulation |
|---|---|
| `molar_mass_g_mol` / site `mass` | the mass in Newton's law `F = m a` (LAMMPS `mass`), the velocity scale, the time unit tau |
| site `sigma_A`, `epsilon_*` | the Lennard-Jones potential `4 eps[(sigma/r)^12 - (sigma/r)^6]` (LAMMPS `pair_coeff`); the reduced temperature `T* = kT/eps` |
| unlike-pair mixing | Lorentz-Berthelot (`pair_modify mix arithmetic`) |
| site `charge`, water geometry, bond/angle constants | Coulomb forces with particle-mesh Ewald, SHAKE-rigid water, `atom_style full` |
| `thermo` melting/boiling/critical + `saturation_table` | which phase the requested conditions are, the starting density (and hence box size) for the requested T and P, validation warnings |
| `solid_min_pressure_atm` | refusing / warning about "solid helium at room temperature" |
| `reactivity.reaxff_supported`, `structure` | whether a reaction can be simulated with ReaxFF, and the molecule geometries used to build it |
| `interactions.json` reactions | the expected overall reaction and its enthalpy in the explanation |
| `polarity`, `category`, `intermolecular_forces` | the explanation of why the substance behaves as it does; ion/solvent rules |
| `de_boer_parameter`, `quantum_effects_significant` | the warning when classical MD is unreliable (light atoms at low temperature) |

## Known limitations (also reported to the user)

* Small molecules (H2, O2, N2, CO2, CH4) are single spherical Lennard-Jones sites: rotation,
  vibration and quadrupole interactions are not represented.
* LJ sets are fitted to gas properties; liquid-phase accuracy is approximate.
* Water is TIP3P (diffuses about twice as fast as real water); ions use the TIP3P-compatible set.
* Gas density uses the ideal-gas law; the simulation then *measures* the pressure and reports it.
* Classical MD cannot form or break bonds; reactions use ReaxFF (empirical bond-order potential) only
  where its parameter file covers the elements (H, C, O).

## Regenerating

```
pip install -r requirements-dev.txt
python chemical_knowledge/build_dataset.py
```

To add a substance: add it to `SPECIES` (and `STRUCTURE`, `REACTIVITY`) in `build_dataset.py`.
Neutral molecules get a Lennard-Jones model automatically from the `chemicals` tables; anything
else (a new water model, new ions) must be added with its published source.
