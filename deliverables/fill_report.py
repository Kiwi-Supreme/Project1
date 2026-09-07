"""
Fills the BCSE497J Project-I Report template with real project content,
editing text in place inside existing template runs/paragraphs so every
font, size, spacing, and indentation rule already in the template is
preserved untouched. New paragraphs are only ever inserted by cloning an
existing template paragraph's formatting, never invented from scratch.

Every purely instructional line in the template -- "(Times New Roman
14, Bold, Upper Case...)", "<Contents, Times New Roman 12, Line spacing
1.15>", "<To define...>" task descriptions, and the Table of Contents --
is left completely untouched, per the "do not change template
instructions" rule.
"""
import copy
import os
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

SRC = r"C:\Users\SHIVANI\Downloads\3 BCSE497J Project I Report - Template.docx"
OUT = os.path.join(os.path.dirname(__file__), "BCSE497J_Project_I_Report_Review2.docx")
FIG = os.path.join(os.path.dirname(__file__), "figures")

doc = Document(SRC)


def collect_paragraphs(document):
    """All paragraphs in the document, including ones inside table cells
    (python-docx's doc.paragraphs only covers top-level body paragraphs) --
    the cover page's Reg. No. / Name / Guide fields live inside tables."""
    result = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                result.extend(cell.paragraphs)
    return result


def set_text(paragraph, text):
    """Puts `text` into a paragraph's first run (keeping that run's
    formatting) and empties every other run in the paragraph."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def find_para(paragraphs, prefix, start=0):
    for i in range(start, len(paragraphs)):
        if paragraphs[i].text.startswith(prefix):
            return i
    raise ValueError("paragraph not found: " + prefix)


def clone_after(paragraph, text=None):
    """Duplicates a paragraph's XML (so it keeps identical formatting)
    and inserts the copy immediately after it. Returns the new Paragraph."""
    new_p_elem = copy.deepcopy(paragraph._p)
    # Word bookmark IDs must be unique document-wide; a cloned paragraph
    # that carried one would otherwise collide with its original.
    # Bookmarks aren't needed on these cloned body paragraphs, so drop them.
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for tag in ("bookmarkStart", "bookmarkEnd"):
        for el in new_p_elem.findall(ns + tag):
            new_p_elem.remove(el)
    paragraph._p.addnext(new_p_elem)
    from docx.text.paragraph import Paragraph
    new_para = Paragraph(new_p_elem, paragraph._parent)
    if text is not None:
        set_text(new_para, text)
    return new_para


def clone_many_after(paragraph, texts):
    """Clones `paragraph` once per item in `texts`, chaining each new
    paragraph after the last, and removes the original template
    paragraph this was cloned from (its job was just to be the style
    template)."""
    anchor = paragraph
    new_paras = []
    for t in texts:
        p = clone_after(anchor, t)
        new_paras.append(p)
        anchor = p
    return new_paras


def add_picture_after(paragraph, image_path, width_in=5.6):
    """Inserts a new, centered paragraph containing a picture right
    after `paragraph`, cloning its formatting for the container
    paragraph (then clearing text/alignment so only the image shows)."""
    new_p = clone_after(paragraph, "")
    new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    new_p.add_run().add_picture(image_path, width=Inches(width_in))
    return new_p


paras = collect_paragraphs(doc)

# ============================================================
# COVER PAGE (first, real, fillable block -- not the sample block)
# ============================================================
set_text(paras[find_para(paras, "<Title of Project>")],
         "AI-ASSISTED GENERATION OF CUDA-BASED MOLECULAR DYNAMICS "
         "SIMULATIONS FROM NATURAL-LANGUAGE DESCRIPTIONS")
set_text(paras[find_para(paras, "Reg. No. 1")], "23BDS0085")
set_text(paras[find_para(paras, "Student Name 1")], "SHIVANI SRIVASTAVA")
set_text(paras[find_para(paras, "Project Guide Name")], "Dr. Vijayasherly V")
# "Designation" left untouched -- not provided in the project materials.

# ============================================================
# ABSTRACT (the real, fillable block -- separate from the sample below it)
# ============================================================
i = find_para(paras, "The rapid advancement of technology")  # sample para 1 (to be overwritten)
set_text(paras[i],
    "Setting up a molecular dynamics (MD) simulation traditionally requires expertise in "
    "both computational physics and low-level programming, a combination few students and "
    "researchers possess together. This project addresses that gap by building a local, "
    "browser-based tool that lets a user describe a simulation in plain English, or fill in "
    "a short form, and receive a real, physically simulated result. A lightweight, fully "
    "local rule-based language component reads the natural-language description and "
    "extracts structured simulation parameters -- particle count, state of matter, "
    "interaction model, container type, and boundary conditions -- without relying on any "
    "external AI service.")
i2 = find_para(paras, "ML algorithms, such as supervised")
set_text(paras[i2],
    "The extracted (or manually entered) parameters are validated against physically "
    "sensible ranges before being handed to a compiled C++ molecular dynamics engine, which "
    "performs the actual computation: Lennard-Jones or Hard-Sphere particle interactions, "
    "velocity-Verlet time integration, and periodic, cuboidal, or spherical boundary "
    "handling. The engine represents solid, liquid, and gas states through genuine "
    "differences in initial arrangement, density, and motion rather than cosmetic labels, "
    "and produces real particle trajectories and energy data as output.")
i3 = find_para(paras, "Through case studies and experimental")
set_text(paras[i3],
    "These results are displayed through an interactive, hand-built 3D visualization -- "
    "supporting rotation, zooming, and inspection of the actual simulated particle motion "
    "inside its container -- alongside an energy-versus-time plot that verifies the physical "
    "correctness of the run. The current implementation runs entirely on the CPU, with the "
    "simulation engine deliberately structured so its core force and integration routines "
    "can later be ported to CUDA for GPU acceleration, without requiring changes to the "
    "surrounding system.")
i4 = find_para(paras, "Keywords - Artificial Intelligence")
set_text(paras[i4],
    "Keywords - Molecular Dynamics, Lennard-Jones Potential, Natural Language Processing, "
    "Local Language Model, C++ Simulation Engine, Interactive 3D Visualization, CUDA/GPU "
    "Acceleration.")

# ============================================================
# 1.1 BACKGROUND
# ============================================================
i = find_para(paras, "The rapid digitization of various sectors")
set_text(paras[i],
    "Molecular dynamics (MD) simulation is a well-established computational technique used "
    "to study how atoms and particles move and interact over time, with applications ranging "
    "from materials science to drug design. Running an MD simulation typically requires the "
    "user to write or configure simulation code directly, which demands familiarity with "
    "numerical integration methods, interatomic potentials, and often low-level, "
    "high-performance programming such as C++ or CUDA.")
i = find_para(paras, "In response to these challenges, Machine Learning")
set_text(paras[i],
    "This dual requirement -- physics knowledge and systems-programming skill -- makes MD "
    "simulation inaccessible to many students and early researchers who understand the "
    "underlying concepts but lack experience writing simulation software from scratch. "
    "Existing MD packages such as LAMMPS and GROMACS are powerful but require substantial "
    "configuration effort and do not offer a natural-language entry point.")
i = find_para(paras, "This project seeks to explore the role of ML")
set_text(paras[i],
    "This project explores whether a lightweight, entirely local language-understanding "
    "component can bridge that gap: reading a plain-English description of a desired "
    "simulation, extracting the parameters that matter, and handing them to a fixed, "
    "hand-verified simulation engine -- so the user only needs to describe what they want, "
    "not implement how to compute it.")

# ============================================================
# 1.2 MOTIVATION
# ============================================================
i = find_para(paras, "The ever-evolving landscape of cyber threats")
set_text(paras[i],
    "The motivation for this project comes from direct experience: a prior summer "
    "internship (Biotech Department, IIT Bombay, 2024) involved hand-writing and debugging a "
    "C++ Lennard-Jones molecular dynamics simulation, and attempting a CUDA port of the same "
    "code. That experience made clear how much of the effort in building an MD simulation "
    "lies not in the physics itself, but in correctly wiring together initialization, force "
    "calculation, boundary conditions, and numerical integration -- work that is repetitive "
    "across simulations that only differ in their input parameters.")
i = find_para(paras, "This project is motivated by the potential")
set_text(paras[i],
    "This observation motivated the idea of separating \u201cwhat to simulate\u201d from "
    "\u201chow to simulate it\u201d: a fixed, verified simulation engine that never changes, "
    "driven by parameters a user can either enter manually or describe in natural language. "
    "Restricting any language component to parameter extraction alone -- never letting it "
    "generate or modify simulation logic -- keeps the physics trustworthy while still "
    "lowering the barrier to running a simulation.")
i = find_para(paras, "The goal of this project is to explore how ML")
set_text(paras[i],
    "Using a local, rule-based language component rather than an external AI API was also a "
    "deliberate choice, motivated by the goal of keeping the entire system self-contained, "
    "explainable, and runnable without an internet connection or ongoing service dependency "
    "-- properties that matter for a tool meant to be understood and demonstrated end to "
    "end.")

# ============================================================
# 1.3 SCOPE OF THE PROJECT
# ============================================================
i = find_para(paras, "The scope of this project focuses on exploring")
set_text(paras[i],
    "The scope of this project covers the full pipeline from user input to visualized "
    "output. It supports two ways of specifying a simulation -- a manual form and a "
    "natural-language description -- both converted into the same structured parameter set "
    "and checked by a single shared validator before any simulation runs.")
i = find_para(paras, "The project will involve the development")
set_text(paras[i],
    "The simulation engine supports two interaction models (Lennard-Jones and Hard-Sphere "
    "elastic collisions), two boundary types (periodic and a real container, either cuboidal "
    "or spherical), and three states of matter (solid, liquid, and gas), each represented "
    "through genuine differences in particle arrangement, density, and motion rather than "
    "separate visual effects. The current implementation is entirely CPU-based, targeting "
    "particle counts and simulation lengths suitable for interactive, real-time "
    "demonstration.")
i = find_para(paras, "The project also considers the ethical")
set_text(paras[i],
    "Out of scope for this prototype are GPU/CUDA execution (identified as future work in "
    "Section 4), multiple simultaneous simulation types beyond the two implemented, and "
    "simulation of more complex molecular systems such as bonded structures or multiple "
    "particle species. The project also does not use any external AI API; the "
    "natural-language component is a local, rule-based extractor, with a real local "
    "language model identified as a future upgrade.")

# ============================================================
# 2.1 LITERATURE REVIEW  (no sample block in template -- insert new)
# ============================================================
anchor = paras[find_para(paras, "< Maximum of 50 journal papers")]
clone_many_after(anchor, [
    "Frenkel and Smit\u2019s \u201cUnderstanding Molecular Simulation\u201d establishes the "
    "classical algorithms this project builds on -- the Lennard-Jones potential, "
    "Verlet-family integrators, and periodic boundary conditions -- and served as the "
    "physical basis for the C++ simulation engine implemented here. Large-scale MD packages "
    "such as LAMMPS (Plimpton, 1995) and GROMACS (Abraham et al., 2015) demonstrate that MD "
    "simulation scales well with parallel and GPU-accelerated computation, but both require "
    "the user to write or configure simulation scripts directly, with no natural-language "
    "entry point -- confirming both the performance potential of parallel MD and the "
    "configuration burden this project aims to reduce for smaller-scale, exploratory use.",
    "On the language-understanding side, work on constraining large language model output "
    "to structured formats (OpenAI function calling; White et al., 2023, on prompt pattern "
    "design) informed the decision to restrict any language component in this system to "
    "producing a fixed parameter schema rather than free-form code or text. The NVIDIA CUDA "
    "C++ Programming Guide provided the reference for how the simulation engine\u2019s core "
    "routines are structured so that a future GPU port remains a contained change rather "
    "than a rewrite.",
])
# refresh the paragraph list -- the document changed
paras = collect_paragraphs(doc)

# ============================================================
# 2.2 RESEARCH GAP  (no sample block -- insert new)
# ============================================================
anchor = paras[find_para(paras, "<To identify the areas or aspects")]
clone_after(anchor,
    "Existing MD packages provide performance and flexibility but assume the user already "
    "knows how to configure a simulation; general-purpose AI coding assistants can generate "
    "code but offer no guarantee that the generated physics is correct, since nothing "
    "constrains them to verified simulation logic. No readily available tool combines a "
    "natural-language entry point with a fixed, hand-verified simulation engine in a way "
    "that keeps the language component\u2019s role strictly limited to parameter extraction. "
    "This project addresses that gap directly: the language-understanding step is "
    "architecturally prevented from touching simulation logic, so the correctness of the "
    "physics does not depend on the reliability of the language step.")
paras = collect_paragraphs(doc)

# ============================================================
# 2.3 OBJECTIVES  (bullet list, cloned from a bold-lead-in style bullet)
# ============================================================
anchor = paras[find_para(paras, "< To clearly define what the project")]
clone_many_after(anchor, [
    "Parameter Schema: Design a structured parameter schema capturing particle count, "
    "density/temperature (or particle speed), state of matter, interaction model, and "
    "container/boundary settings.",
    "Local Language Understanding: Build a local, rule-based natural-language extraction "
    "component that reliably converts a plain-English description into this schema, without "
    "relying on any external AI service.",
    "Validation: Implement a validation layer that checks extracted or manually entered "
    "parameters against physically sensible ranges before simulation.",
    "Simulation Engine: Develop a compiled C++ molecular dynamics engine supporting "
    "Lennard-Jones and Hard-Sphere interaction models, periodic and container (cuboidal/"
    "spherical) boundary conditions, and solid/liquid/gas states as genuine physical "
    "presets.",
    "Visualization: Produce real particle trajectory and energy output from the engine, and "
    "build an interactive 3D visualization to play it back with rotation and zoom controls.",
    "Future Extensibility: Structure the simulation engine so its core computation can be "
    "extended to CUDA/GPU acceleration in future work, without requiring changes to the "
    "surrounding system.",
])
paras = collect_paragraphs(doc)

# ============================================================
# 2.4 PROBLEM STATEMENT  (no sample block -- insert new)
# ============================================================
anchor = paras[find_para(paras, "< Clearly define the issue or challenge")]
clone_after(anchor,
    "Running a molecular dynamics simulation currently requires a user to already know how "
    "to translate a physical scenario into correct simulation code and parameters -- a "
    "requirement that excludes many students and early researchers who understand the "
    "underlying physics conceptually but lack low-level programming experience -- and "
    "existing MD tools do not accept a natural-language description of the desired "
    "simulation. This project addresses the problem of providing a natural-language and "
    "manual-input interface to a real, verified molecular dynamics simulation, without "
    "compromising the correctness of the underlying physics by letting a language component "
    "generate simulation logic directly.")
paras = collect_paragraphs(doc)

# ============================================================
# 2.5 PROJECT PLAN  (insert Gantt chart image above its caption)
# ============================================================
caption = paras[find_para(paras, "Fig. 1. Gantt chart")]
add_picture_after(paras[find_para(paras, "<A Gantt chart helps")], os.path.join(FIG, "fig1_gantt.png"))

# ============================================================
# 3.1.1 FUNCTIONAL REQUIREMENTS (8 bullets -- same count as template)
# ============================================================
func_items = [
    ("Natural-Language Input", ": The system shall accept a plain-English description of a "
     "desired simulation and extract structured parameters from it using a local, rule-based "
     "language component."),
    ("Manual Parameter Input", ": The system shall allow a user to directly enter or select "
     "simulation parameters through a form-based interface as an alternative to "
     "natural-language input."),
    ("Parameter Validation", ": The system shall validate all parameters, from either input "
     "path, against physically sensible ranges and reject infeasible requests with a "
     "specific, human-readable reason before simulation."),
    ("Simulation Execution", ": The system shall run the validated parameters through a "
     "compiled C++ molecular dynamics engine implementing Lennard-Jones and Hard-Sphere "
     "interaction models."),
    ("Boundary and Container Handling", ": The system shall support periodic boundaries as "
     "well as real cuboidal and spherical containers, with particles reflecting elastically "
     "off container walls when enabled."),
    ("State-of-Matter Representation", ": The system shall represent solid, liquid, and gas "
     "states through distinct initial particle arrangement, density, and motion, driven by "
     "the simulation engine rather than the interface."),
    ("Trajectory and Energy Output", ": The system shall record real particle positions over "
     "time and system energy values from the simulation engine for playback and "
     "verification."),
    ("Interactive 3D Visualization", ": The system shall display the recorded particle "
     "trajectory as an interactive, rotatable and zoomable 3D animation alongside an "
     "energy-versus-time chart."),
]
labels = ["Data Collection", "Data Preprocessing", "Model Training", "Real-time Monitoring",
          "Anomaly Detection", "Alert Generation", "User Interface", "Reporting"]
for label, (new_label, new_desc) in zip(labels, func_items):
    idx = find_para(paras, label)
    p = paras[idx]
    p.runs[0].text = new_label
    # the rest of that paragraph's runs carry the ": description" text
    if len(p.runs) > 1:
        p.runs[1].text = new_desc
        for r in p.runs[2:]:
            r.text = ""
    else:
        p.add_run(new_desc)

# ============================================================
# 3.1.2 NON-FUNCTIONAL REQUIREMENTS (6 bullets)
# ============================================================
nonfunc_items = [
    ("Performance", ": The system should complete a typical simulation (up to 500 "
     "particles, a few reduced time units) within a few seconds on a standard laptop CPU."),
    ("Locality and Privacy", ": The system should perform all computation, including "
     "language understanding and simulation, entirely on the local machine, without "
     "depending on an external AI API or network connection."),
    ("Reliability", ": The simulation engine\u2019s physics should be fixed and "
     "hand-verified, so its output does not depend on the reliability of the "
     "language-understanding component."),
    ("Usability", ": The interface should present a simple, clear setup-review-run "
     "workflow, showing extracted or entered parameters for confirmation before any "
     "simulation runs."),
    ("Maintainability", ": The codebase should be organized into clearly separated, "
     "well-commented modules -- language extraction, validation, simulation engine, "
     "visualization -- so each part can be understood and modified independently."),
    ("Extensibility", ": The simulation engine should be structured so its core computation "
     "can be extended to CUDA/GPU acceleration in future work without redesigning the "
     "surrounding system."),
]
nf_labels = ["Performance", "Scalability", "Reliability", "Usability", "Maintainability", "Compliance"]
for label, (new_label, new_desc) in zip(nf_labels, nonfunc_items):
    idx = find_para(paras, label)
    p = paras[idx]
    p.runs[0].text = new_label
    if len(p.runs) > 1:
        p.runs[1].text = new_desc
        for r in p.runs[2:]:
            r.text = ""
    else:
        p.add_run(new_desc)

# ============================================================
# 3.2.1 TECHNICAL FEASIBILITY (4 bullets)
# ============================================================
tf_items = [
    ("Technology Availability", ": The project uses well-documented, freely available "
     "technologies -- standard C++, Python (FastAPI), and plain HTML/CSS/JavaScript -- "
     "requiring no specialized or proprietary tools."),
    ("Technical Expertise", ": The implementation builds directly on C++ molecular dynamics "
     "code developed and debugged during a prior internship, reducing the technical risk of "
     "the core physics implementation."),
    ("Infrastructure", ": The current CPU-based implementation runs on any standard laptop "
     "with a C++ compiler and Python installed; no GPU or specialized hardware is required "
     "for this prototype."),
    ("Integration", ": The frontend, backend, and simulation engine communicate through a "
     "small, well-defined set of local API endpoints and file formats, keeping integration "
     "straightforward and easy to verify."),
]
tf_labels = ["Technology Availability", "Technical Expertise", "Infrastructure", "Integration"]
for label, (new_label, new_desc) in zip(tf_labels, tf_items):
    idx = find_para(paras, label)
    p = paras[idx]
    p.runs[0].text = new_label
    if len(p.runs) > 1:
        p.runs[1].text = new_desc
        for r in p.runs[2:]:
            r.text = ""
    else:
        p.add_run(new_desc)

# ============================================================
# 3.2.2 ECONOMIC FEASIBILITY (4 bullets)
# ============================================================
ef_items = [
    ("Cost-Benefit Analysis", ": The project uses only free and open-source tools and "
     "libraries, so implementation cost is limited to development time; the benefit is a "
     "reusable, explainable simulation tool with no ongoing service cost."),
    ("Budget", ": No paid infrastructure, cloud services, or external AI API subscriptions "
     "are required to build, run, or demonstrate this project."),
    ("Return on Investment (ROI)", ": The primary return is educational and demonstrative -- "
     "a working, understandable system suitable for a final-year project review and as a "
     "foundation for future GPU-accelerated extensions."),
    ("Funding", ": No external funding is required for this prototype; all development was "
     "carried out using freely available tools on a personal laptop."),
]
ef_labels = ["Cost-Benefit Analysis", "Budget", "Return on Investment (ROI)", "Funding"]
for label, (new_label, new_desc) in zip(ef_labels, ef_items):
    idx = find_para(paras, label)
    p = paras[idx]
    p.runs[0].text = new_label
    if len(p.runs) > 1:
        p.runs[1].text = new_desc
        for r in p.runs[2:]:
            r.text = ""
    else:
        p.add_run(new_desc)

# ============================================================
# 3.2.3 SOCIAL FEASIBILITY (4 bullets)
# ============================================================
sf_items = [
    ("User Acceptance", ": The natural-language and manual input options are intended to "
     "make molecular dynamics simulation approachable for students without requiring "
     "simulation-programming experience."),
    ("Training and Support", ": The project’s README documents installation, usage, "
     "and the reasoning behind each design decision, so a new user or reviewer can "
     "understand and run the system without additional support."),
    ("Ethical Considerations", ": The system performs all computation locally and does not "
     "collect, transmit, or store any personal data, avoiding the privacy concerns "
     "associated with cloud-based AI services."),
    ("Impact on Workforce", ": The project is an educational and research tool; it does not "
     "replace or displace any existing workflow or role."),
]
sf_labels = ["User Acceptance", "Training and Support", "Ethical Considerations", "Impact on Workforce"]
for label, (new_label, new_desc) in zip(sf_labels, sf_items):
    idx = find_para(paras, label)
    p = paras[idx]
    p.runs[0].text = new_label
    if len(p.runs) > 1:
        p.runs[1].text = new_desc
        for r in p.runs[2:]:
            r.text = ""
    else:
        p.add_run(new_desc)

# ============================================================
# 3.3.1 HARDWARE SPECIFICATION
# ============================================================
hw_map = {
    "Processor": "Processor: Any modern multi-core CPU (Intel/AMD, x64) -- no specialized "
                 "processor required for this prototype.",
    "Memory (RAM)": "Memory (RAM): 4 GB or more recommended for compiling and running the "
                     "simulation engine and local web server.",
    "Storage": "Storage: Under 100 MB for the project source code and dependencies.",
    "Graphics Processing Unit (GPU)": "Graphics Processing Unit (GPU): Not required for the "
        "current CPU-based implementation; an NVIDIA GPU with CUDA support would be needed "
        "for the future GPU-accelerated extension described in Section 4.",
    "Monitor": "Monitor: A standard display capable of rendering a web browser, used to "
               "view and interact with the 3D visualization.",
}
for label, text in hw_map.items():
    idx = find_para(paras, label)
    set_text(paras[idx], text)

# ============================================================
# 3.3.2 SOFTWARE SPECIFICATION
# ============================================================
sw_map = {
    "Operating System:": "Operating System: Windows, Linux, or macOS (developed and tested "
                          "on Windows).",
    "Programming Languages:": "Programming Languages: C++ (simulation engine), Python "
                               "(backend), HTML/CSS/JavaScript (frontend).",
    "Development Environment:": "Development Environment: Any standard code editor (e.g. "
        "VS Code) with a C++ compiler (g++/MinGW) and Python 3.10+.",
    "Libraries and Frameworks:": "Libraries and Frameworks: FastAPI, Pydantic, and Uvicorn "
        "(Python backend); no external frontend framework is used.",
    "Database:": "Database: None -- simulation parameters and results are exchanged as "
                  "request/response data and local files; no persistent database is used.",
    "Security Tools:": "Security Tools: Not applicable -- the system runs entirely locally "
        "with no external network exposure or authentication requirements.",
}
for label, text in sw_map.items():
    idx = find_para(paras, label)
    set_text(paras[idx], text)

# ============================================================
# 4.1 SYSTEM ARCHITECTURE (explanation + Fig. 2)
# ============================================================
idx = find_para(paras, "/** Sample **/", start=find_para(paras, "4.1 System Architecture"))
add_picture_after(paras[idx], os.path.join(FIG, "fig2_architecture.png"))
paras = collect_paragraphs(doc)
idx = find_para(paras, "<Explanation>")
set_text(paras[idx],
    "Figure 2 shows the system’s architecture. The frontend (plain HTML/CSS/JavaScript) "
    "collects a manual or natural-language simulation request and sends it to the backend "
    "over three local API endpoints -- extract, validate, and simulate. The backend’s "
    "language-extraction and validation modules never touch simulation logic; validated "
    "parameters are written to a configuration file and passed to a separately compiled C++ "
    "molecular dynamics engine, which performs the actual simulation and writes real "
    "particle trajectory and energy files. The backend reads these files and returns them to "
    "the frontend, where an interactive 3D renderer and an energy chart display the real "
    "simulation output. This separation keeps the simulation engine fixed and independently "
    "verifiable, regardless of which input path produced its parameters.")

# ============================================================
# 4.2 DESIGN (DFD, Use Case = mandatory; Class, Sequence = optional, included)
# ============================================================
paras = collect_paragraphs(doc)
idx = find_para(paras, "4.2.1 Data Flow Diagram")
add_picture_after(paras[idx], os.path.join(FIG, "fig3_dfd.png"))
paras = collect_paragraphs(doc)
idx = find_para(paras, "4.2.2 Use Case Diagram")
add_picture_after(paras[idx], os.path.join(FIG, "fig4_usecase.png"))
paras = collect_paragraphs(doc)
idx = find_para(paras, "4.2.3 Class Diagram")
add_picture_after(paras[idx], os.path.join(FIG, "fig5_class.png"))
paras = collect_paragraphs(doc)
idx = find_para(paras, "4.2.4 Sequence Diagram")
add_picture_after(paras[idx], os.path.join(FIG, "fig6_sequence.png"))

# ============================================================
# 5. REFERENCES
# ============================================================
paras = collect_paragraphs(doc)
set_text(paras[find_para(paras, "https://www.cloudflare.com")],
    "https://github.com/Kiwi-Supreme/Molecular-Dynamics-Simulation-of-Particles-in-a-Box")
set_text(paras[find_para(paras, "http://www.thedailybeast.com")],
    "https://platform.openai.com/docs/guides/function-calling")

# This paragraph holds BOTH journal citations across its 7 runs (the
# template itself merged them this way) -- edited run-by-run so the
# italic journal-name run stays italic.
p = paras[find_para(paras, "Apruzzese, Giovanni")]
p.runs[0].text = "S. Plimpton, “Fast parallel algorithms for short-range molecular dynamics,” "
p.runs[1].text = "Journal of Computational Physics,"
p.runs[2].text = " vol. 117, no. 1, pp. 1-19, 1995."
p.runs[4].text = (" M. J. Abraham, T. Murtola, R. Schulz, S. Páll, J. C. Smith, B. Hess, and E. "
                   "Lindahl, “GROMACS: High performance molecular simulations through "
                   "multi-level parallelism from laptops to supercomputers,” ")
p.runs[5].text = "SoftwareX,"
p.runs[6].text = " vol. 1-2, pp. 19-25, 2015."

p = paras[find_para(paras, " Kumar, Sarvesh")]
p.runs[1].text = ("J. White, Q. Fu, S. Hays, M. Sandborn, C. Olea, H. Gilbert, A. Elnashar, "
                   "J. Spencer-Smith, and D. C. Schmidt, “A prompt pattern catalog to "
                   "enhance prompt engineering with ChatGPT,” ")
p.runs[2].text = "arXiv preprint arXiv:2302.11382,"
p.runs[3].text = " 2023."

# No real conference paper was part of this project's research -- left as
# an explicit placeholder rather than inventing one.
p = paras[find_para(paras, "Salih, Azar")]
p.runs[0].text = "<Add a relevant conference reference here, if applicable.>"
for r in p.runs[1:]:
    r.text = ""

set_text(paras[find_para(paras, "A.P. Malvino and D.P. Leach")],
    "D. Frenkel and B. Smit, Understanding Molecular Simulation: From Algorithms to "
    "Applications, 2nd ed. San Diego, CA: Academic Press, 2002.")
paras = collect_paragraphs(doc)
book_para = paras[find_para(paras, "D. Frenkel and B. Smit")]
clone_after(book_para,
    "NVIDIA Corporation, CUDA C++ Programming Guide, Release 12.5, NVIDIA, 2024.")

doc.save(OUT)
print("Stage 2 saved:", OUT)
