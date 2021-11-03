Vacancy & Interstitial Diffusion Barrier
----------------------------------------

.. image:: /miscellaneous/DiffusionVacancy-interstitial.png
   :scale: 20 %
   :align: center


The Interstitial diffusion workflows required following inputs::

        inputs = { 'host_structure': host,
        'interstitial_species': Dict(dict={ 'symbol': 'H', 'name': 'H' }),
        'initial_position': List(list=initial_position),
        'final_position':   List(list=final_position),
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

``n_images`` (**required**):AiiDA int for number of images.

``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart. 

``neb`` (**required**): AiiDA siesta inputs and lua inputs. 

Example: Silicon H diffusiom
++++++++++++++++++++++++++++
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
        from aiida_siesta_barrier.workflows.interstitial_barrier import InterstitialBarrierWorkChain
        codename = 'siesta-lua@mylaptop' # PROVIDE YOUR CODE
        code = load_code(codename)
        # Si8 cubic cell as host
        alat = 5.430
        cell = [[1.0*alat, 0.0 , 0.0,],
                [0.0, 1.0*alat , 0.0,],
                [0.0, 0.0 , 1.0*alat,],
                ]
        host = StructureData(cell=cell)
        host.append_atom(position=(   alat*0.000, alat*0.000, alat*0.000),symbols='Si',)
        host.append_atom(position=(   alat*0.500, alat*0.500, alat*0.000),symbols='Si')
        host.append_atom(position=(   alat*0.500, alat*0.000, alat*0.500),symbols='Si')
        host.append_atom(position=(   alat*0.000, alat*0.500, alat*0.500),symbols='Si')
        host.append_atom(position=(   alat*0.250, alat*0.250, alat*0.250),symbols='Si')
        host.append_atom(position=(   alat*0.750, alat*0.750, alat*0.250),symbols='Si')
        host.append_atom(position=(   alat*0.750, alat*0.250, alat*0.750),symbols='Si')
        host.append_atom(position=(   alat*0.250, alat*0.750, alat*0.750),symbols='Si')
        # Interstitial
        initial_position=[alat*0.000, alat*0.250, alat*0.250]
        final_position=[alat*0.250, alat*0.250, alat*0.000]
        interstitial_species= Dict(dict={ 'symbol': 'H', 'name': 'H' })
        n_images_in_script = 5
        # Lua Stuff
        lua_elements_path ="/home/aakhtar/Projects/flos_nick/?.lua;/home/aakhtar/Projects/flos_nick/?/init.lua;;;"   # YOUR LUA ENVIRONMENT
        absname = op.abspath("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/lua_scripts/neb.lua") # YOUR LUA NEB SCRIPT

        lua_script = SinglefileData(absname)
        
        # The pseudopotentials
        pseudos_dict = {}
        raw_pseudos = [("Si.psf", ['Si']), ("H.psf", ['H'])]
        for fname, kinds in raw_pseudos:
            absname = op.join("/home/aakhtar/Projects/aiida-siesta-barrier/aiida_siesta_barrier/examples/fixtures/sample_psf", fname)
            pseudo = PsfData.get_or_create(absname)
            if not pseudo.is_stored:
                print("\nCreated the pseudo for {}".format(kinds))
            else:
                print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
            for j in kinds:
                pseudos_dict[j]=pseudo
           # Parameters: very coarse for speed of test
        # Note the all the Si atoms are fixed...
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
        constraints = dict={"%block geometryconstraints":
                             """
                            atom [ 1 -- 8 ]
                            %endblock geometryconstraints"""}
        relaxation = dict={'md-steps': 100}
        #
        # Use this for constraints
        #
        parameters.update(constraints)
        #
        neb_parameters = Dict(dict=parameters)

        parameters.update(relaxation)
        endpoint_parameters = Dict(dict=parameters)
        #The basis set
        basis = Dict(dict={
        'pao-energy-shift': '300 meV',
        '%block pao-basis-sizes': """
        Si SZ
        H SZ
        %endblock pao-basis-sizes""",})


        #The kpoints
        kpoints_endpoints = KpointsData()
        kpoints_endpoints.set_kpoints_mesh([2,2,2])

        kpoints_neb = KpointsData()
        kpoints_neb.set_kpoints_mesh([1,1,1])

        # For finer-grained compatibility with script
        #Resources
        options = {"max_wallclock_seconds": 3600,
                   'withmpi': True,
                   "resources": {"num_machines": 1,
                   "num_mpiprocs_per_machine": 2,}}
        options_neb = {"max_wallclock_seconds": 86400,#7200,
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
        inputs = {'host_structure': host,
                  'interstitial_species': interstitial_species,
                  'initial_position': List(list=initial_position),
                  'final_position':   List(list=final_position),
                  'n_images': Int(5),
            'interpolation_method': Str('li'),
            'initial': endpoint_inputs,
            'final': endpoint_inputs,
            #'neb_wk_node':Int(6034),
        'neb': {'neb_script': lua_script,
        'parameters': neb_parameters,
        'code': code,
        'basis': basis,
        'kpoints': kpoints_neb,
        'pseudos': pseudos_dict,
        'options': Dict(dict=options_neb)},}

