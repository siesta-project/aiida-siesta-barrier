#!/usr/bin/env runaiida

#Not required by AiiDA
import os.path as op
import sys

#AiiDA classes and functions
from aiida.engine import submit
from aiida.orm import load_code
from aiida.orm import (Dict, StructureData, KpointsData)
from aiida.orm import SinglefileData
from aiida_pseudo.data.pseudo.psf import PsfData
from aiida_siesta_barrier.workflows.vacancy_exchange_barrier import VacancyExchangeBarrierWorkChain

try:
    codename = sys.argv[1]
    load_code(codename)
except (IndexError, NotExistent):
    print(("The first parameter must be the code to use. Hint: `verdi code list`."),file=sys.stderr)
    sys.exit(1)

try:
    lua_elements_path = sys.argv[2]
except IndexError:
    print(("The second parameter must be the path to the lua scripts in the flos library."),file=sys.stderr)
    print(("Look at the docs for more info. Library can be found at https://github.com/siesta-project/flos"),file=sys.stderr)
    sys.exit(1)


code = load_code(codename)

from aiida.orm import StructureData

cell = [
    [
        9.9678210000,
        0.0000000000,
        0.0000000000,
    ],
    [
        -4.9839090000,
        8.6323860000,
        0.0000000000,
    ],
    [
        0.0000000000,
        0.0000000000,
        35.0000000000,
    ],
]
s = StructureData(cell=cell)
s.append_atom(position=(1.6613036650053632, 0.959153999040846, 17.5),
              symbols='Mg',
              name="Mg")  #1
s.append_atom(position=(3.333333331578814e-07, 1.918307998081692, 17.5),
              symbols='O',
              name="O")  #2
s.append_atom(position=(4.983911666666668, 6.714078001918309, 17.5),
              symbols='Mg',
              name="Mg")  #3
s.append_atom(position=(3.322608334994638, 7.673232000959154, 17.5),
              symbols='O',
              name="O")  #4
s.append_atom(position=(1.6613046600214534, 6.714078001918309, 17.5),
              symbols='Mg',
              name="Mg")  #5
s.append_atom(position=(1.3283494233462534e-06, 7.673232000959154, 17.5),
              symbols='O',
              name="O")  #6
s.append_atom(position=(-1.6613023366559396, 6.714078001918309, 17.5),
              symbols='Mg',
              name="Mg")  #7
s.append_atom(position=(-3.32260566832797, 7.673232000959154, 17.5),
              symbols='O',
              name="O")  #8
s.append_atom(position=(6.645214669989273, 3.836615996163384, 17.5),
              symbols='Mg',
              name="Mg")  #9
s.append_atom(position=(4.983911338317244, 4.79576999520423, 17.5),
              symbols='O',
              name="O")  #10
s.append_atom(position=(3.3226076633440593, 3.836615996163384, 17.5),
              symbols='Mg',
              name="Mg")  #11
s.append_atom(position=(1.6613043316720297, 4.79576999520423, 17.5),
              symbols='O',
              name="O")  #12
s.append_atom(position=(6.666666663157628e-07, 3.836615996163384, 17.5),
              symbols='Mg',
              name="Mg")  #13
s.append_atom(position=(-1.6613026650053635, 4.79576999520423, 17.5),
              symbols='O',
              name="O")  #14
s.append_atom(position=(8.30651766832797, 0.959153999040846, 17.5),
              symbols='Mg',
              name="Mg")  #15
s.append_atom(position=(6.6452143366559415, 1.918307998081692, 17.5),
              symbols='O',
              name="O")  #16
s.append_atom(position=(4.983910661682756, 0.959153999040846, 17.5),
              symbols='Mg',
              name="Mg")  #17
s.append_atom(position=(3.3226073300107264, 1.918307998081692, 17.5),
              symbols='O',
              name="O")  #18

structure = s

# Put a O vacancy in the site number 16, and exchange it with the atom number 18
# Watch out for python base-0 convention...
iv = 15
ia = 17

# Not used in this example
#migration_direction = [ 0.0, 0.0, 1.0 ]    # Z direction

ghost_species = Dict(dict={'symbol': 'H', 'name': 'H_ghost'})

# Lua script
absname = op.abspath(op.join(op.dirname(__file__), "fixtures/lua_scripts/neb.lua"))
n_images_in_script = 5
lua_script = SinglefileData(absname)

# Parameters: very coarse for speed. Not physical, and might lead to
# a NEB search that actually takes too long to converge.

parameters = dict = {
    "mesh-cutoff": "50 Ry",
    "dm-tolerance": "0.003",
    "DM-NumberPulay ": "3",
    "DM-History-Depth": "0",
    "SCF-Mixer-weight": "0.02",
    "SCF-Mix": "density",
    "SCF-Mixer-kick": "35",
    "MD-VariableCell": "F",
    "MD-MaxCGDispl": "0.3 Bohr",
    "MD-MaxForceTol": " 0.06000 eV/Ang"
}

# Original maximal constraint for physical atoms:    atom [ 1 -- 15 ]
constraints = dict = {
    "%block Geometry-Constraints":
    """
    atom [ 1 -- 12 ]
    atom [ 18 -- 19 ]
    %endblock Geometry-Constraints"""
}

#
# Use this for constraints
#
parameters.update(constraints)
#
neb_parameters = Dict(dict=parameters)

# Specific parameter for end-point relaxation
relaxation = dict = {'md-steps': 20}

parameters.update(relaxation)
endpoint_parameters = Dict(dict=parameters)

# The basis set dictionary can include info for the ghost species

basis = Dict(
    dict={
        'pao-energy-shift':
        '300 meV',
        '%block pao-basis-sizes':
        """
Mg SZ
O SZ
H_ghost SZ
%endblock pao-basis-sizes""",
    })

# k-point sampling can be different for end-points or neb runs
kpoints_endpoints = KpointsData()
kpoints_endpoints.set_kpoints_mesh([1, 1, 1])

kpoints_neb = KpointsData()
kpoints_neb.set_kpoints_mesh([1, 1, 1])

# The pseudopotentials for ghost species have to be added by hand if this
# method of construction is used. It could be automated if using a pseudo family.
pseudos_dict = {}
raw_pseudos = [("Mg.psf", ['Mg']), ("O.psf", ['O']), ("H.psf", ['H_ghost'])]
for fname, kinds in raw_pseudos:
    absname = op.realpath(
        op.join(op.dirname(__file__), "fixtures/sample_psf", fname))
    pseudo = PsfData.get_or_create(absname)
    if not pseudo.is_stored:
        print("\nCreated the pseudo for {}".format(kinds))
    else:
        print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
    for j in kinds:
        pseudos_dict[j] = pseudo

#Resources
options = {
    "max_wallclock_seconds": 3600,
    'withmpi': True,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 2,
    }
}

#
# For finer-grained compatibility with script. Give it more time
#
options_neb = {
    "max_wallclock_seconds": 7200,
    'withmpi': True,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 2,
    },
    "environment_variables":{"LUA_PATH":lua_elements_path},
}

endpoint_inputs = {
    'parameters': endpoint_parameters,
    'code': code,
    'basis': basis,
    'kpoints': kpoints_endpoints,
    'pseudos': pseudos_dict,
    'options': Dict(dict=options)
}

# Final inputs for the workchain:

inputs = {
    'host_structure': structure,
    'vacancy_index': Int(iv),
    'atom_index': Int(ia),
    'ghost_species': ghost_species,
    #  'migration_direction': List(list=migration_direction),
    'n_images': Int(n_images_in_script),
    'initial': endpoint_inputs,
    'final': endpoint_inputs,
    'neb': {
        'neb_script': lua_script,
        'parameters': neb_parameters,
        'code': code,
        'basis': basis,
        'kpoints': kpoints_neb,
        'pseudos': pseudos_dict,
        'options': Dict(dict=options_neb)
    },
}

process = submit(VacancyExchangeBarrierWorkChain, **inputs)
print("Submitted VacancyExchangeBarrier workchain; ID={}".format(process.pk))
print(
    "For information about this workchain type: verdi process show {}".format(
        process.pk))
print("For a list of running processes type: verdi process list")
