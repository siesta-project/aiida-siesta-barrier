Exchange barrier
----------------

.. image:: /miscellaneous/Exchange-VacancyExchange.png
   :scale: 20 %
   :align: center


The Exchange diffusion workflow requires the following inputs::

        inputs = {'initial_structure': host,
          'first_index': Int(i1),
          'second_index':Int(i2),
          'migration_direction': List(list=migration_direction),
          'interpolation_method': Str('li'),
          'n_images': Int(n_images_in_script), 
          'initial': endpoint_inputs,
          'final': endpoint_inputs,
          #'neb_wk_node':Int(8084),
          'neb': {'neb_script': lua_script,
                  'parameters': neb_parameters,
                  'code': code,
                  'basis': basis,
                  'kpoints': kpoints_neb,
                  'pseudos': pseudos_dict,
                  'options': Dict(dict=options_neb)},}


``initial_structure`` (**required**): AiiDA StructureData of host system.

``first_index`` ( **required**): AiiDA Int for initial exchange atom index.

``second_index`` (**required**): AiiDA Int for final exchange atom index.

``migration_direction`` (**required**):  AiiDA list for migration direction of exchange atoms.

``n_images`` (**required**):AiiDA int for number of images.

``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart. 

``neb`` (**required**): AiiDA siesta inputs and lua inputs. 

Example: Silicon-Silicon Exchange 
+++++++++++++++++++++++++++++++++
One could copy/paste and run the following script in jupyter notebook ::

        #AiiDA classes and functions
        import aiida
        import os.path as op
        from aiida import orm
        from aiida.engine import submit
        from aiida.orm import load_code
        from aiida.orm import (Dict, StructureData, KpointsData,Int,Str,List)
        from aiida.orm import SinglefileData
        from aiida_pseudo.data.pseudo.psf import PsfData
        from aiida.engine import submit,run
        from aiida_siesta_barrier.workflows.exchange_barrier import ExchangeBarrierWorkChain
        aiida.load_profile()

        codename = 'siesta-lua@mylaptop'
        code = load_code(codename)
        # Si8 cubic cell as host
        alat = 5.430
        cell = [[1.0*alat, 0.0 , 0.0,],
                [0.0, 1.0*alat , 0.0,],
                [0.0, 0.0 , 1.0*alat,],
                ]
        host = StructureData(cell=cell)
        host.append_atom(position=(   alat*0.000, alat*0.000, alat*0.000),symbols='Si',name='Si')#1 0
        host.append_atom(position=(   alat*0.500, alat*0.500, alat*0.000),symbols='Si',name='Si')#2 1
        host.append_atom(position=(   alat*0.500, alat*0.000, alat*0.500),symbols='Si',name='Si')#3 2
        host.append_atom(position=(   alat*0.000, alat*0.500, alat*0.500),symbols='Si',name='Si')#4 3
        host.append_atom(position=(   alat*0.250, alat*0.250, alat*0.250),symbols='Si',name='Si')#5 4
        host.append_atom(position=(   alat*0.750, alat*0.750, alat*0.250),symbols='Si',name='Si')#6 5
        host.append_atom(position=(   alat*0.750, alat*0.250, alat*0.750),symbols='Si',name='Si')#7 6 'Si_exchange'
        host.append_atom(position=(   alat*0.250, alat*0.750, alat*0.750),symbols='Si',name='Si')#8 7 'Si_exchange'


        i1 = 6
        i2 = 7
        migration_direction = [ 1.0, 1.0, 0.0 ]    # Z direction
        n_images_in_script=5

        # Parameters: very coarse for speed of test
        parameters = dict={"mesh-cutoff": "50 Ry",
                   "dm-tolerance": "0.001",
                   "DM-NumberPulay ":  "3",
                   "DM-History-Depth":  "0",
                   "SCF-Mixer-weight":  "0.02",
                   "SCF-Mix":   "density",
                   "SCF-Mixer-kick":  "35",
                   "MD-VariableCell":  "F",
                   "MD-MaxCGDispl":  "0.3 Bohr",
                   "MD-MaxForceTol":  " 0.04000 eV/Ang"}
        # All other atoms are fixed (...)
        constraints = dict={"%block geometryconstraints":
                    """
                    atom [ 1 -- 6 ]
                    %endblock geometryconstraints"""}

                    #
        # Use this for constraints
        #       
        parameters.update(constraints)
        #
        neb_parameters = Dict(dict=parameters)

        # Extra parameter for end-point relaxation
        relaxation = dict={'md-steps': 150}
        parameters.update(relaxation)
        endpoint_parameters = Dict(dict=parameters)
        # The basis set
        basis = Dict(dict={'pao-energy-shift': '300 meV',
                    '%block pao-basis-sizes': """
                    Si SZ
                    %endblock pao-basis-sizes""",})


        # The kpoints
        kpoints_endpoints = KpointsData()
        kpoints_endpoints.set_kpoints_mesh([2,2,2])

        kpoints_neb = KpointsData()
        kpoints_neb.set_kpoints_mesh([1,1,1])

        # The pseudopotentials
        pseudos_dict = {}
        raw_pseudos = [("Si.psf", ['Si'])]
        for fname, kinds in raw_pseudos:
            absname = op.join("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/sample_psf", fname)
            pseudo = PsfData.get_or_create(absname)
            if not pseudo.is_stored:
                print("\nCreated the pseudo for {}".format(kinds))
            else:
                print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
            for j in kinds:
                pseudos_dict[j]=pseudo
                #Resources
        options = {
            "max_wallclock_seconds": 3600,
            'withmpi': True,
            "resources": {
                "num_machines": 1,
                "num_mpiprocs_per_machine": 2,
            }
        }

        # Lua Stuff
        lua_elements_path ="/home/aakhtar/Projects/flos_nick/?.lua;/home/aakhtar/Projects/flos_nick/?/init.lua;;;"
        absname = op.abspath("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/lua_scripts/neb.lua")
        lua_script = SinglefileData(absname)
        # For finer-grained compatibility with script
        options_neb = {"max_wallclock_seconds": 86400,
                       "withmpi": True,
                       "resources": {"num_machines": 1,
                                     "num_mpiprocs_per_machine": 2,},
                       "environment_variables":{"LUA_PATH":lua_elements_path},}

        endpoint_inputs= {'parameters': endpoint_parameters,
                          'code': code,
                          'basis': basis,
                          'kpoints': kpoints_endpoints,
                          'pseudos': pseudos_dict,
                          'options': Dict(dict=options)}


        inputs = {'initial_structure': host,
          'first_index': Int(i1),
          'second_index':Int(i2),
          'migration_direction': List(list=migration_direction),
          'interpolation_method': Str('li'),
          'n_images': Int(n_images_in_script),
          'initial': endpoint_inputs,
          'final': endpoint_inputs,
          #'neb_wk_node':Int(8084),
          'neb': {'neb_script': lua_script,
                  'parameters': neb_parameters,
                  'code': code,
                  'basis': basis,
                  'kpoints': kpoints_neb,
                  'pseudos': pseudos_dict,
                  'options': Dict(dict=options_neb)},}


        process = submit(ExchangeBarrierWorkChain, **inputs)    
        print("Submitted ExchangeBarrier workchain; ID={}".format(process.pk))
        print("For information about this workchain type: verdi process show {}".format(process.pk))
        print("For a list of running processes type: verdi process list")
                                                                          
