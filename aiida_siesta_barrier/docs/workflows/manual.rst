Manual Barrier
--------------


The Manual workflow requires the following inputs::

       inputs = {
                'initial_structure': s1,
                'final_structure': s2,
                'interpolation_method': Str('li'),
                'n_images': Int(n_images_in_script),
                'initial': endpoint_inputs,
                'final': endpoint_inputs,
                #'neb_wk_node': Int(8214) , #first no relaxed ,last relaxed,
                'neb': {
                        'neb_script': lua_script,
                        'parameters': neb_parameters,
                        'code': code,
                        'basis': basis,
                        'kpoints': kpoints_neb,
                        'pseudos': pseudos_dict,
                        'options': Dict(dict=options_neb)
                    }}




``initial_structure`` (**required**): AiiDA StructureData of initial system.

``first_structure`` ( **required**): AiiDA StructureData of final system.

``n_images`` (**required**):AiiDA int for number of images.

``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart.

``neb`` (**required**): AiiDA siesta inputs and lua inputs.

