Kick Barrier
------------

.. image:: /miscellaneous/Kick.png
   :scale: 20 %
   :align: center


The Exchange diffusion workflow requires the following inputs::

        inputs = {'host_structure': structure,
                  'initial_position_index':      Int(i1),
            'final_position_index':     Int(i2),
            'interstitial_position': inter_pos,
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


``host_structure`` (**required**): AiiDA StructureData of host system.

``initial_position_index`` ( **required**): AiiDA Int for initial exchange atom index.

``final_position_index`` (**required**): AiiDA Int for final exchange atom index.

``interstitial_position`` (**required**): AiiDA List for kicked atom interstitial position.

``migration_direction`` (**required**):  AiiDA List for migration direction of exchange atoms.

``n_images`` (**required**):AiiDA int for number of images.

``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart.

``neb`` (**required**): AiiDA siesta inputs and lua inputs.

