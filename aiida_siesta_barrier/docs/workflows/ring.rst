Ring or n-Exchange Barrier
--------------------------


.. image:: /miscellaneous/Ring-nExchange.png
   :scale: 20 %
   :align: center


The Exchange diffusion workflow requires the following inputs::

        inputs = {
                  'host_structure': structure,
                  'list_of_position_index': list_of_position_index,
                  'n_images': Int(n_images_in_script),
                  #'neb_wk_node': Int(3838) ,
                  'initial': endpoint_inputs,
                  'final': endpoint_inputs,
                  'neb': {
                          'neb_script': lua_script,
                          'parameters': neb_parameters,
                          'code': code,
                          'basis': basis,
                          'kpoints': kpoints_neb,
                          'pseudos': pseudos_dict,
                          'options': Dict(dict=options_neb)}}




``host_structure`` (**required**): AiiDA StructureData of host system.

``list_of_position_index`` (**required**):  AiiDA list for migration indexes in `order` for exchange atoms.

``n_images`` (**required**):AiiDA int for number of images.

.. comment::

                ``interpolation_method`` ( **optional**): AiiDA string for interpolation method (the default is *idpp*).

``initial`` (**required**): AiiDA siesta inputs for initial structure.

``final`` (**required**): AiiDA siesta inputs for final structure.

``neb_wk_node`` (**optional**):AiiDA pk of previous interrupted workflow to restart. 

``neb`` (**required**): AiiDA siesta inputs and lua inputs. 
