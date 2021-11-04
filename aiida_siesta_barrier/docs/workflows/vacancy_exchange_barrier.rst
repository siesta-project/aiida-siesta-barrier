Vacancy Exchange Diffusion Barrier
----------------------------------

.. image:: /miscellaneous/DiffusionVacancy-interstitial.png
   :scale: 20 %
   :align: center


The Interstitial diffusion workflow requires following inputs::

        inputs = { 'host_structure': host,
        'interstitial_species': Dict(dict={ 'symbol': 'H', 'name': 'H' }),
        'initial_position': List(list=initial_position),
        'final_position':   List(list=final_position),
        'migration_direction': List(list=migration_direction),
        'n_images': Int(5),
        'interpolation_method': Str('li'),
        'initial': endpoint_inputs,
        'final': endpoint_inputs,
        'neb_wk_node':Int(6034),
        'neb': {'neb_script': lua_script,
                'parameters': neb_parameters,
                 'code': code,
                 'basis': basis,
                 'kpoints': kpoints_neb,
                 'pseudos': pseudos_dict,
                 'options': Dict(dict=options_neb)}}
      
``host_structure`` (**required**): AiiDA StructureData of host system.

``interstitial_species`` ( **required**): AiiDA Dictionary.

``initial_position`` (**required**): AiiDA list for initial atom position.

``final_position`` (**required**):  AiiDA list for final atom position.

``migration_direction`` (**required**): AiiDA list for migration direction.

``n_images`` (**required**):AiiDA int for number of images.

``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart. 

``neb`` (**required**): AiiDA siesta inputs and lua inputs. 

Example: MgO sheet Oxygen-Vacancy Exchange diffusion
++++++++++++++++++++++++++++++++++++++++++++++++++++
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
        aiida.load_profile()
        from aiida_siesta_barrier.workflows.vacancy_exchange_barrier_restart import VacancyExchangeBarrierWorkChain
        codename = 'siesta-lua@mylaptop' # PROVIDE YOUR CODE
        code = load_code(codename)

        cell = [[9.9678210000,0.0000000000,0.0000000000],
                [-4.9839090000,8.6323860000,0.0000000000],
                [0.0000000000,0.0000000000,35.0000000000]]
                
        s = StructureData(cell=cell)
        s.append_atom(position=(1.6613036650053632, 0.959153999040846, 17.5),symbols='Mg',name="Mg")  #1
        s.append_atom(position=(3.333333331578814e-07, 1.918307998081692, 17.5),symbols='O',name="O")  #2
        s.append_atom(position=(4.983911666666668, 6.714078001918309, 17.5),symbols='Mg',name="Mg")  #3
        s.append_atom(position=(3.322608334994638, 7.673232000959154, 17.5),symbols='O',name="O")  #4
        s.append_atom(position=(1.6613046600214534, 6.714078001918309, 17.5),symbols='Mg',name="Mg")  #5
        s.append_atom(position=(1.3283494233462534e-06, 7.673232000959154, 17.5),symbols='O',name="O")  #6
        s.append_atom(position=(-1.6613023366559396, 6.714078001918309, 17.5),symbols='Mg',name="Mg")  #7
        s.append_atom(position=(-3.32260566832797, 7.673232000959154, 17.5),symbols='O',name="O")  #8
        s.append_atom(position=(6.645214669989273, 3.836615996163384, 17.5),symbols='Mg',name="Mg")  #9
        s.append_atom(position=(4.983911338317244, 4.79576999520423, 17.5),symbols='O',name="O")  #10
        s.append_atom(position=(3.3226076633440593, 3.836615996163384, 17.5),symbols='Mg',name="Mg")  #11
        s.append_atom(position=(1.6613043316720297, 4.79576999520423, 17.5),symbols='O',name="O")  #12
        s.append_atom(position=(6.666666663157628e-07, 3.836615996163384, 17.5),symbols='Mg',name="Mg")  #13
        s.append_atom(position=(-1.6613026650053635, 4.79576999520423, 17.5),symbols='O',name="O")  #14
        s.append_atom(position=(8.30651766832797, 0.959153999040846, 17.5),symbols='Mg',name="Mg")  #15
        s.append_atom(position=(6.6452143366559415, 1.918307998081692, 17.5),symbols='O',name="O")  #16
        s.append_atom(position=(4.983910661682756, 0.959153999040846, 17.5),symbols='Mg',name="Mg")  #17
        s.append_atom(position=(3.3226073300107264, 1.918307998081692, 17.5),symbols='O',name="O")  #18
        structure=s             

        iv = 15
        ia = 17
        # Not used in this example
        migration_direction = [ 0.0, 0.0, 1.0 ]    # Z direction
        ghost_species = Dict(dict={'symbol': 'O', 'name': 'O_ghost'})

        # The pseudopotentials for ghost species have to be added by hand if this
        # method of construction is used. It could be automated if using a pseudo family.
        pseudos_dict = {}
        raw_pseudos = [("Mg.psf", ['Mg']), ("O.psf", ['O',"O_ghost"])]
        for fname, kinds in raw_pseudos:
            absname = op.join("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/sample_psf", fname)
            pseudo = PsfData.get_or_create(absname)
            if not pseudo.is_stored:
                print("\nCreated the pseudo for {}".format(kinds))
            else:
                print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
            for j in kinds:
                pseudos_dict[j] = pseudo
        # Lua script
        lua_elements_path ="/home/aakhtar/Projects/flos_nick/?.lua;/home/aakhtar/Projects/flos_nick/?/init.lua;;;"
        absname = op.abspath("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/lua_scripts/neb.lua")
        n_images_in_script = 5
        lua_script = SinglefileData(absname)       

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
            "MD-MaxForceTol": " 0.06000 eV/Ang",
            "WriteCoorXmol": "T",
        }

        # Original maximal constraint for physical atoms:    atom [ 1 -- 15 ]
        constraints = dict = {
            "%block geometryconstraints":
            """
            #species-i 3
            atom [ 1 -- 16 ]
            atom [ 18 -- 19 ]
            %endblock geometryconstraints"""
        }

        parameters.update(constraints)
        #
        neb_parameters = Dict(dict=parameters)
        # Specific parameter for end-point relaxation
        relaxation = dict = {'md-steps': 150}
        parameters.update(relaxation)
        endpoint_parameters = Dict(dict=parameters)            

        # k-point sampling can be different for end-points or neb runs
        kpoints_endpoints = KpointsData()
        kpoints_endpoints.set_kpoints_mesh([2, 2, 1])
        kpoints_neb = KpointsData()
        kpoints_neb.set_kpoints_mesh([2, 2, 1])

        basis = Dict(
            dict={
        'pao-energy-shift':
        '300 meV',
        "%block PAO-Basis":
        """
        # Define Basis set
        Mg                    1                    # Species label, number of l-shells
         n=3   0   1                         # n, l, Nzeta
           6.620
           1.000
        O                     2                    # Species label, number of l-shells
         n=2   0   1                         # n, l, Nzeta
           3.223
           1.000
         n=2   1   1                         # n, l, Nzeta
           3.840
           1.000
        O_ghost                     2                    # Species label, number of l-shells
         n=2   0   1                         # n, l, Nzeta
           3.023
           1.000
         n=2   1   1                         # n, l, Nzeta
           3.0840
           1.000
        %endblock PAO.Basis
        
        """

         })

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
        from aiida.orm import Int,Str
        inputs = {
            'host_structure': structure,
            'vacancy_index': Int(iv),
            'atom_index': Int(ia),
            'ghost_species': ghost_species,
            'interpolation_method': Str('li'),
            'migration_direction': List(list=migration_direction),
            'n_images': Int(n_images_in_script),
            'initial': endpoint_inputs,
            'final': endpoint_inputs,
            'neb_wk_node': Int(7155) , #first no relaxed ,last relaxed,
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

