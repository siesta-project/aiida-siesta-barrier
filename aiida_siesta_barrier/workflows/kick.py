from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction ,if_
#from aiida_siesta.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta_barrier.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida_siesta.utils.structures import clone_aiida_structure
from aiida_siesta_barrier.utils.interpol import interpolate_two_structures_ase
from aiida_siesta_barrier.utils.structures import compute_mid_path_position
from aiida_siesta_barrier.utils.structures import find_intermediate_structure
from aiida.orm import Dict,Int


#----------------------------------------------------------------------------
# FIXED:
#       (1) Restarting points 
#       (2) Adding interpolation Methods
#       (3) Adding outputs for WorkChain
#
# TO FIX:
#        -   
#----------------------------------------------------------------------------



@calcfunction
def generate_initial_path_for_kick(s_initial, s_final, nimages,interp_method,migration_direction,i1,i2):
    """
    Wrapper calcfunction to keep provenance
    :param: s1, s2 : StructureData objects
    :param: nimages: Int object
    """
    #
    i1 = i1.value
    i2 = i2.value
    n_images = nimages.value
    migration_direction = migration_direction.get_list()
    interp_method = interp_method.value 
    i1_mid_path_position = compute_mid_path_position(s_initial, i1, i2, migration_direction)
    s_intermediate = find_intermediate_structure(s_initial, i1,i1_mid_path_position, i2)
    first_list = interpolate_two_structures_ase(s_initial, s_intermediate,
                                            n_images // 2,interp_method )
    second_list = interpolate_two_structures_ase(s_intermediate, s_final,
                                             n_images // 2 , interp_method )
    images_list = first_list[:-1] + second_list 
        
    path_object = orm.TrajectoryData(images_list)
    #
    # Use a 'serializable' dictionary instead of the
    # actual kinds list
    #
    _kinds_raw = [k.get_raw() for k in s_initial.kinds]
    path_object.set_attribute('kinds', _kinds_raw)

    return path_object


class KickBarrierWorkChain(WorkChain):
    """
    Workchain to compute the barrier for Kick
    from the host structure , initial, final and interstitial positions
    
    INPUTS :
            initial,
            final,
            neb,
            host_structure,
            initial_position_index,
            final_position_index,
            interstitial_position,
            migration_direction, 
            n_images,
            interpolation_method,
            neb_wk_node,


    """
    @classmethod
    def define(cls, spec):
        super().define(spec)

        spec.expose_inputs(SiestaBaseWorkChain,
                           exclude=('structure', ),
                           namespace="initial")
        
        spec.expose_inputs(SiestaBaseWorkChain,
                           exclude=('structure', ),
                           namespace="final")

        spec.expose_inputs(SiestaBaseNEBWorkChain,
                           exclude=('starting_path', ),
                           namespace="neb")

        spec.input('host_structure',
                   valid_type=orm.StructureData,
                   help='Host structure')

        spec.input('initial_position_index',
                    valid_type=orm.Int,  # validator...
                    help='Initial position of kicking atom in host structure')
        
        spec.input('final_position_index',
                    valid_type=orm.Int,  # validator...
                    help='Final position of kicking atom in host structure')
        
        spec.input('interstitial_position',
                    valid_type=orm.List,  # validator...
                    help='Final position of kicked atom in host structure')
        
        spec.input('migration_direction',
                    valid_type=orm.List,
                    required=False,
                    help='Migration direction (in lattice coordinates)')
 
        spec.input('n_images',
                   valid_type=orm.Int,
                   help='Number of (internal) images  in Path')

        spec.input("interpolation_method",
                    valid_type=orm.Str,
                    default=lambda:orm.Str("idpp"),
                    help="interpolation method (idpp) or (li)")

        spec.input('neb_wk_node',
                    valid_type=orm.Int,
                    help="Restart from intrupted neb workchain",
                    required=False )
        
        

        spec.output('first_structure',valid_type=orm.StructureData)
        spec.output('last_structure',valid_type=orm.StructureData)
        spec.output('initial_path',valid_type=orm.TrajectoryData)
        spec.output('first_structure_wk_pk',valid_type=orm.Int)
        spec.output('last_structure_wk_pk',valid_type=orm.Int)

        spec.expose_outputs(SiestaBaseNEBWorkChain)

        spec.outline(cls.prepare_structures,
                     if_(cls.is_restart)(
                         cls.is_relaxation_restart,
                         cls.relax_initial_or_final_restart,
                         ).else_(
                                 cls.relax_end_points,
                                 ),
                     cls.check_relaxation,
                     if_(cls.is_restart_neb)(
                         cls.run_NEB_workchain,
                         ).else_(cls.prepare_initial_path,
                                 cls.run_NEB_workchain),
                     cls.check_results)


        spec.exit_code( 200,
                        'ERROR_MAIN_WC',
                        message='The end-point relaxation SiestaBaseWorkChain failed')
        spec.exit_code( 250,
                        'ERROR_CONFIG',
                        message='Cannot figure out interstitial position(s)')
        spec.exit_code( 300,
                        'ERROR_NEB_WK',
                        message='NEBWorkChain did not finish correctly')

    
    def is_restart(self):

        """
        """
        if 'neb_wk_node' not in self.inputs :
            self.report("Starting Workchain from Scratch")
            return False 
        else:    
            self.report("Restarting Workchain ...")
            return True 


    def is_relaxation_restart(self):
        """
        Checking Relaxation Restart points
        Not Sure we need it cz SiestaBaseWorkChain workchain will take care of it...
        """
        self.is_relax_initial = False
        self.is_relax_final = False

        neb_wk_node = orm.load_node(self.inputs.neb_wk_node.value)
        self.report(f"Restarting check from node {neb_wk_node.pk}")
        if 'first_structure' not in neb_wk_node.outputs:
            self.report("Need to Restart First Structure Relaxation...")
            self.is_relax_initial = True
        else:
            self.report("First Structure is Relaxed")
            self.out("first_structure_wk_pk", neb_wk_node.outputs.first_structure_wk_pk)
            self.ctx.first_structure = neb_wk_node.outputs.first_structure
            self.out('first_structure',self.ctx.first_structure)
            self.ctx.initial_relaxation_wk = orm.load_node(neb_wk_node.outputs.first_structure_wk_pk.value)

        if 'last_structure' not in neb_wk_node.outputs:
            self.report("Need to Restart Last Structure Relaxation...")
            self.is_relax_final = True
        else:
            self.report("Last Structure is Relaxed")
            self.out("last_structure_wk_pk",neb_wk_node.outputs.last_structure_wk_pk)
            self.ctx.last_structure = neb_wk_node.outputs.last_structure
            self.out("last_structure",self.ctx.last_structure)
            self.ctx.final_relaxation_wk = orm.load_node(neb_wk_node.outputs.last_structure_wk_pk.value)


    def check_relaxation(self):
        """
        """
        if 'initial_relaxation_wk' in self.ctx:
            initial_wk = self.ctx.initial_relaxation_wk
            first_structure_wk_pk = Int(initial_wk.pk)
            first_structure_wk_pk.store()
            self.out('first_structure_wk_pk',first_structure_wk_pk)
            if not initial_wk.is_finished_ok:
                self.report(f"FIRST STRUCTURE WK FAILD! with PK {initial_wk.pk}")
                self.out('first_structure_wk_pk',first_structure_wk_pk)
            else:
                self.ctx.first_structure = initial_wk.outputs.output_structure
                self.out('first_structure',self.ctx.first_structure)
                self.report(f"First Strcuture Relaxation WK is Okay With PK {self.ctx.first_structure.pk} ")

        if 'final_relaxation_wk' in self.ctx:
            final_wk = self.ctx.final_relaxation_wk
            last_structure_wk_pk = Int(final_wk.pk)
            last_structure_wk_pk.store()
            self.out('last_structure_wk_pk',last_structure_wk_pk)
            if not final_wk.is_finished_ok:
                self.report(f"LAST STRUCTURE WK FAILD! with PK {final_wk.pk}")
            else:
                self.ctx.last_structure = final_wk.outputs.output_structure
                self.out('last_structure',self.ctx.last_structure)
                self.report(f"Last Strcuture Relaxation WK is Okay With PK {self.ctx.last_structure.pk}")

        if not initial_wk.is_finished_ok or not final_wk.is_finished_ok:
            return self.exit_codes.ERROR_MAIN_WC




    def prepare_structures_Bugy(self):
        """
        Make copies of host structure and add interstitials
        """
        host = self.inputs.host_structure
        initial_position_index = self.inputs.initial_position_index #.value
        final_position_index = self.inputs.final_position_index #.value
        inter_pos = self.inputs.interstitial_position 
        host_sites=host.sites
        initial_atom_name =  host_sites[initial_position_index.value].kind_name
        initial_atom_symbol = host_sites[initial_position_index.value].kind_name
        final_atom_name =  host_sites[final_position_index.value].kind_name
        final_atom_symbol = host_sites[final_position_index.value].kind_name
        initial_atom_position = host_sites[initial_position_index.value].position
        final_atom_position = host_sites[final_position_index.value].position
        s_final = clone_aiida_structure(host)
        s_final.clear_sites()
        new_sites = host_sites

        if initial_position_index.value > final_position_index.value:
            # Remove initial site from list
            initial_site = new_sites.pop(initial_position_index.value)      
            # Remove initial site from list
            final_site = new_sites.pop(final_position_index.value)  
            [s_final.append_site(s) for s in new_sites]
            s_final.append_atom(symbols=final_atom_symbol,
                    position=initial_atom_position, 
                    name=final_atom_name)
            s_final.append_atom(symbols=initial_atom_symbol,
                    position=inter_pos.get_list(),
                    name=initial_atom_name)
        else:
            final_site = new_sites.pop(final_position_index.value)  
            initial_site = new_sites.pop(initial_position_index.value)  
            [s_final.append_site(s) for s in new_sites]
            s_final.append_atom(symbols=initial_atom_symbol,
                    position=inter_pos.get_list(),
                    name=initial_atom_name)
            s_final.append_atom(symbols=final_atom_symbol,
                    position=initial_atom_position, 
                    name=final_atom_name)

        self.ctx.s_initial = host #s_initial
        self.ctx.s_final = s_final

        self.report('Created initial and final structures')

    def prepare_structures(self):
        """
        Make copies of host structure and add interstitials
        """
        host = self.inputs.host_structure
        initial_position_index = self.inputs.initial_position_index #.value
        final_position_index = self.inputs.final_position_index #.value
        inter_pos = self.inputs.interstitial_position 
        host_sites=host.sites
        initial_atom_name =  host_sites[initial_position_index.value].kind_name
        initial_atom_symbol = host_sites[initial_position_index.value].kind_name
        final_atom_name =  host_sites[final_position_index.value].kind_name
        final_atom_symbol = host_sites[final_position_index.value].kind_name
        initial_atom_position = host_sites[initial_position_index.value].position
        final_atom_position = host_sites[final_position_index.value].position
        s_final = clone_aiida_structure(host)
        s_final.clear_sites()
        s_initial = clone_aiida_structure(host)
        s_initial.clear_sites()
        new_sites = host_sites
        
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # repeating block will fix it later!
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if initial_position_index.value > final_position_index.value:
            self.report('initial index > final index')
            # Remove initial site first from list
            initial_site = new_sites.pop(initial_position_index.value)      
            # Remove final site second from list
            final_site = new_sites.pop(final_position_index.value)  
            [s_final.append_site(s) for s in new_sites]
            s_final.append_atom(symbols=final_atom_symbol,
                                position= inter_pos.get_list(),
                                name=final_atom_name)
            s_final.append_atom(symbols=initial_atom_symbol,
                                position= final_atom_position,
                                name=initial_atom_name)
            # Puting back for initial
            [s_initial.append_site(s) for s in new_sites]
            s_initial.append_atom(symbols=final_atom_symbol,
                                  position=final_atom_position,
                                  name= final_atom_symbol)
            s_initial.append_atom(symbols=initial_atom_symbol,
                                  position=initial_atom_position,
                                  name=initial_atom_name)    
        else:
            self.report('final index > initial index')
            # Remove final index first
            final_site = new_sites.pop(final_position_index.value)
            # Remove initial index second
            initial_site = new_sites.pop(initial_position_index.value)
            [s_final.append_site(s) for s in new_sites]
            s_final.append_atom(symbols=final_atom_symbol,
                                position=inter_pos.get_list(),
                                name=final_atom_name)
            s_final.append_atom(symbols=initial_atom_symbol,
                                position=final_atom_position,
                                name=initial_atom_name)
            #
            [s_initial.append_site(s) for s in new_sites]
            s_initial.append_atom(symbols=final_atom_symbol,
                                  position=final_atom_position,
                                  name= final_atom_symbol)
            s_initial.append_atom(symbols=initial_atom_symbol,
                                  position=initial_atom_position,
                                  name=initial_atom_name)

        self.ctx.s_initial = s_initial
        self.ctx.s_final = s_final

        self.report('Created initial and final structures')



    def relax_initial_or_final_restart(self):
        """
        """
        calculations = {}

        if self.is_relax_initial:
            self.report("DEBUG: Initial")
            inputs_restart =  self.exposed_inputs(SiestaBaseWorkChain, namespace='initial')
            neb_wk_node = orm.load_node(self.inputs.neb_wk_node.value)
            restart_node_wk = orm.load_node(neb_wk_node.outputs.first_structure_wk_pk.value)
            restart_node = orm.load_node(restart_node_wk.called[0].pk)
            self.report(f"Restarting First strcutrure from PK {restart_node.pk}")
            restart_builder = restart_node.get_builder_restart()
            restart_builder.parent_calc_folder = restart_node.outputs.remote_folder
            inputs_restart = {'structure': restart_builder.structure,
                'parameters': restart_builder.parameters,
                'code': restart_builder.code,
                'basis': restart_builder.basis,
                'kpoints': restart_builder.kpoints,
                'pseudos':restart_builder.pseudos,
                'options': Dict(dict=self.inputs['initial']['options'].get_dict()),
                'parent_calc_folder':restart_builder.parent_calc_folder,
                 }

            running = self.submit(SiestaBaseWorkChain, **inputs_restart)
            self.report(f'Restart Launched SiestaBaseWorkChain<{running.pk}> to relax the initial structure.')

            calculations ['initial_relaxation_wk'] = running

        if self.is_relax_final:
            self.report("DEBUG: Final")
            inputs_restart =  self.exposed_inputs(SiestaBaseWorkChain, namespace='final')
            neb_wk_node = orm.load_node(self.inputs.neb_wk_node.value)
            restart_node_wk = orm.load_node(neb_wk_node.outputs.last_structure_wk_pk.value)
            restart_node = orm.load_node(restart_node_wk.called[0].pk)
            self.report(f"Restarting Last strcutrure from PK {restart_node.pk}")
            restart_builder=restart_node.get_builder_restart()
            restart_builder.parent_calc_folder = restart_node.outputs.remote_folder
            inputs_restart = {'structure': restart_builder.structure,
                'parameters': restart_builder.parameters,
                'code': restart_builder.code,
                'basis': restart_builder.basis,
                'kpoints': restart_builder.kpoints,
                'pseudos':restart_builder.pseudos,
                'options': Dict(dict=self.inputs['final']['options'].get_dict()),
                'parent_calc_folder':restart_builder.parent_calc_folder,
                 }

            running = self.submit(SiestaBaseWorkChain, **inputs_restart)
            self.report(f'Restart Launched SiestaBaseWorkChain<{running.pk}> to relax the final structure.'
        )
     
            calculations ['final_relaxation_wk'] = running

        return ToContext(**calculations)

    def is_restart_neb(self):
        """
        """
        if 'neb_wk_node' in self.inputs :
            neb_wk_node = orm.load_node(self.inputs.neb_wk_node.value)
            if "neb_output_package" in neb_wk_node.outputs:
                self.report("DEBUG: Restart NEB from last crash point")
                self.ctx.path = neb_wk_node.outputs.neb_output_package
                self.out("initial_path",neb_wk_node.outputs.initial_path)
                return True
            if "initial_path" in neb_wk_node.outputs:
                self.report("DEBUG: Restart NEB from initial_path")
                self.ctx.path = neb_wk_node.outputs.initial_path
                self.out("initial_path",neb_wk_node.outputs.initial_path)
                return True
        else:
            self.report("Starting NEB From Scratch ...")
            return False


    def relax_end_points(self):
        """
        """
        self.report("DEBUG: STARTING BOTH INTIAL and FINAL")

        # Relaxing Initial (first Strcuture)

        calculations = {}
        inputs = self.exposed_inputs(SiestaBaseWorkChain, namespace='initial')
        inputs['structure'] = self.ctx.s_initial

        running = self.submit(SiestaBaseWorkChain, **inputs)
        self.report(
            f'Launched SiestaBaseWorkChain<{running.pk}> to relax the initial structure.'
        )

        calculations ['initial_relaxation_wk'] = running

        # relaxing Final (last Strcuture)

        inputs = self.exposed_inputs(SiestaBaseWorkChain, namespace='final')
        inputs['structure'] = self.ctx.s_final

        running = self.submit(SiestaBaseWorkChain, **inputs)
        self.report(
            f'Launched SiestaBaseWorkChain<{running.pk}> to relax the final structure.'
        )

        calculations ['final_relaxation_wk'] = running

        return ToContext(**calculations)


    def prepare_initial_path(self):
        """
        Nothing special to do for the interstitial case. If needed, a subclass might implement
        special heuristics to avoid bad guesses for specific cases.
        Here we just interpolate.
        """

        s_initial = self.ctx.first_structure
        s_final = self.ctx.last_structure

        n_images = self.inputs.n_images
        i1 = self.inputs.initial_position_index
        i2 = self.inputs.final_position_index
        migration_direction = self.inputs.migration_direction
        interp_m = self.inputs.interpolation_method
        self.report("Preparing Kick initial Path")
        self.report(f"The Interpolation Method is {interp_m.value} ")
        self.ctx.path = generate_initial_path_for_kick(s_initial,s_final,n_images,interp_m,migration_direction,i1,i2)
        
        if len(self.ctx.path.get_array("positions")) != n_images.value + 2:
            self.report(f"Number of images: {n_images} /= list length")
            return self.exit_codes.ERROR_CONFIG

        self.out('initial_path',self.ctx.path)
        self.report('Generated starting path for NEB.')

    def run_NEB_workchain(self):

        inputs = self.exposed_inputs(SiestaBaseNEBWorkChain, namespace='neb')

        inputs['starting_path'] = self.ctx.path

        running = self.submit(SiestaBaseNEBWorkChain, **inputs)

        self.report(
            f'Launched SiestaBaseNEBWorkChain<{running.pk}> to find MEP for kick.'
        )

        return ToContext(neb_wk=running)

    def check_results(self):
        """
        All checks are done in the NEB workchain
        """

        if not self.ctx.neb_wk.is_finished_ok:
            outps = self.ctx.neb_wk.outputs
            self.out('neb_output_package', outps['neb_output_package'])
            return self.exit_codes.ERROR_NEB_WK

        outps = self.ctx.neb_wk.outputs
        self.out('neb_output_package', outps['neb_output_package'])
        
        barrier = outps['neb_output_package'].get_attribute("barrier")
        self.report(f"The Kick Barrier is {barrier} eV ")

        self.report('Kick Barrier WorkChain done.')


