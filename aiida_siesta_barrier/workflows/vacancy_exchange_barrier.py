from aiida import orm
from aiida.engine import WorkChain, ToContext,calcfunction ,if_
#from aiida_siesta.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta_barrier.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida.orm import Dict,Int,List
from aiida.orm.nodes.data.structure import Site
from aiida_siesta_barrier.utils.structures import find_mid_path_position
from aiida_siesta_barrier.utils.structures import find_intermediate_structure
from aiida_siesta_barrier.utils.interpol import interpolate_two_structures_ase


#----------------------------------------------------------------------------
# FIXED:
#       (1) Restarting points 
#       (2) Adding interpolation Methods
#       (3) Adding outputs for WorkChain
#       (4) Fixing ghost position order consistency   
#
# TO FIX:
#        - fixing name and symbol problem to use get_ase method  
#----------------------------------------------------------------------------

@calcfunction
def generate_initial_path_for_vacancy_diffusion(s1,s2,n_images,interp_method):
    """
    Wrapper calcfunction to keep provenance
    :param: s1, s2 : StructureData objects
    :param: nimages: Int object

    """
    images_list = interpolate_two_structures_ase(s1, 
                s2,
                n_images.value,
                interp_method.value,
                )

    path_object = orm.TrajectoryData(images_list)
    #
    # Use a 'serializable' dictionary instead of the
    # actual kinds list
    #
    _kinds_raw = [k.get_raw() for k in s1.kinds]
    path_object.set_attribute('kinds', _kinds_raw)

    return path_object 

@calcfunction
def generate_initial_path_for_vacancy_exchange(s_initial,s_final,n_images,interp_method,migration_direction, pos1,pos2 ,atom_site_index):
    """

    """
    migration_direction = migration_direction.get_list()

    pos1 = pos1.get_list()
    pos2 = pos2.get_list()
    atom_site_index_v = atom_site_index.value
    n_images = n_images.value
    # ... this would be unrelaxed:  pos2 = self.ctx.vacancy_position
    atom_mid_path_position = find_mid_path_position(
                s_initial, pos1, pos2, migration_direction)
    print(f"Using mid-path point {atom_mid_path_position}")

    s_intermediate = find_intermediate_structure(s_initial, atom_site_index_v, atom_mid_path_position)

    # The starting_path is now built from two sections
    # We assume that the number of internal images is odd,
    # so that n_images // 2 is the number of internal images
    # of each section

    first_list = interpolate_two_structures_ase(
                s_initial, s_intermediate, n_images // 2,interp_method.value )
    second_list = interpolate_two_structures_ase(
                s_intermediate, s_final, n_images // 2,interp_method.value )

    #
    # Remove duplicate central point
    #
    images_list = first_list[:-1] + second_list

    path_object = orm.TrajectoryData(images_list)
    #
    # Use a 'serializable' dictionary instead of the
    # actual kinds list
    #
    #_kinds_raw = [k.get_raw() for k in s1.kinds]
    _kinds_raw = [k.get_raw() for k in s_initial.kinds]
    path_object.set_attribute('kinds', _kinds_raw)

    return path_object


class VacancyExchangeBarrierWorkChain(WorkChain):
    """
    Workchain to compute the barrier for exchange of a vacancy and an atom
    in a structure.
    
    INPUTS :
            initial,
            final,
            neb,
            host_structure,
            vacancy_index,
            atom_index,
            ghost_species,
            migration_direction,
            n_images,
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

        spec.input('vacancy_index',
                    valid_type=orm.Int,
                    help='Index of vacancy in structure')
        spec.input('atom_index',
                    valid_type=orm.Int,
                    help='Index of atom (to be exchanged) in structure')

        # This is required in this version.
        spec.input('ghost_species',
                    valid_type=orm.Dict,
                    help='Ghost species to provide extra basis orbitals')

        spec.input('migration_direction',
                    valid_type=orm.List,
                    required=False,
                    help='Migration direction (in lattice coordinates)')

        spec.input('n_images',
                    valid_type=orm.Int,
                    help='Number of (internal) images in Path (odd!!)')  # validate

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


        spec.exit_code(
            200,
            'ERROR_MAIN_WC',
            message='The end-point relaxation SiestaBaseWorkChain failed')
        spec.exit_code(250,
                       'ERROR_CONFIG',
                       message='Cannot generate initial path correctly')
        spec.exit_code(
            300,
            'ERROR_NEB_WK',
            message='SiestaBaseNEBWorkChain did not finish correctly')
        
        spec.exit_code(
            400,
            'ERROR_WC_Restart',
            message='The Restart input string is wrong ...')
 
 
    def is_restart(self):

        """
        checking if neb workchain no provided or not 
        """
        if 'neb_wk_node' not in self.inputs :
            self.report("Starting Workchain from Scratch")
            return False
        else:
            self.report("Restarting Workchain")
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


    def prepare_structures(self):
        """
        Generate structures:
            initial: host with the vacancy site removed
            final:   as the initial, but with the coordinates of the
                     moving atom set to those of the original vacancy.
        """

        s_host = self.inputs.host_structure

        iv = self.inputs.vacancy_index.value
        ia = self.inputs.atom_index.value

        sites = s_host.sites
        atom_site = sites[ia]

        s_initial = s_host.clone()
        s_initial.clear_sites()

        new_sites = sites
        vacancy_site = new_sites.pop(iv)  # Remove site from list
        vacancy_position = vacancy_site.position

        [s_initial.append_site(s) for s in new_sites]
        # Atom index might have changed with removal of vacancy
        new_ia = new_sites.index(atom_site)

        # Insert site with final position of atom in place of the original.
        new_atom_site = Site(kind_name=atom_site.kind_name,
                             position=vacancy_position)
        new_sites[new_ia] = new_atom_site

        s_final = s_initial.clone()
        s_final.clear_sites()
        [s_final.append_site(s) for s in new_sites]

        self.ctx.s_initial = s_initial
        self.ctx.s_final = s_final
        self.ctx.vacancy_position = vacancy_position
        self.ctx.atom_site_index = new_ia
        self.ctx.original_atom_site = atom_site
        self.ctx.original_vacancy_site = vacancy_site

        self.report('Created initial and final structures')

    #def relax_initial(self):
    def relax_end_points(self):
        """
        """
        calculations ={}
        # =========================================
        # Run First Structure
        # ===========================================
        self.report('Preparing First Strcuture to Relax')
        inputs = self.exposed_inputs(SiestaBaseWorkChain, namespace='initial')
        inputs['structure'] = self.ctx.s_initial

        #
        # Update basis dict with floating orbitals at vacancy site
        # (and at 'atom' site, for symmetry)

        basis_dict = inputs['basis'].get_dict()

        # First attempt with the same species as ghosts does not quite work,
        # so now an arbitrary species can be specified.

        # orig_atom_name = self.ctx.original_atom_site.kind_name
        # ghost_atom_name = orig_atom_name+"_ghost"
        #orig_vac_name = self.ctx.original_vacancy_site.kind_name
        #ghost_vac_name = orig_vac_name+"_ghost"

        ghost = self.inputs.ghost_species.get_dict()
        ghost_name = ghost['name']
        ghost_symbol = ghost['symbol']

        orig_atom_position = self.ctx.original_atom_site.position
        orig_vac_position = self.ctx.original_vacancy_site.position

        floating = {
            'floating_sites': [{
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_atom_position
            }, {
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_vac_position
            }]
        }

        basis_dict.update(floating)
        inputs['basis'] = Dict(dict=basis_dict)

        # adding Label 
        inputs['metadata']['label'] = 'first'
        # Update params dict with constraints for floating orbitals
        # (Must be done in driver for now)

        running = self.submit(SiestaBaseWorkChain, **inputs)
        self.report(
            f'Launched SiestaBaseWorkChain<{running.pk}> to relax the initial structure.'
        )
        
        calculations ['initial_relaxation_wk'] = running
        
        #self.to_context(**{'initial_relaxation_wk':running})
        #return ToContext(initial_relaxation_wk=running)
    
        #def relax_final(self):
        # =========================================
        # Run Final Structure
        # ===========================================
 
        self.report('Preparing Last Strcuture to Relax')
        inputs = self.exposed_inputs(SiestaBaseWorkChain, namespace='final')
        inputs['structure'] = self.ctx.s_final

        # Update basis dict with floating orbitals at vacancy site
        # (and at 'atom' site, for symmetry)

        basis_dict = inputs['basis'].get_dict()

        ghost = self.inputs.ghost_species.get_dict()
        ghost_name = ghost['name']
        ghost_symbol = ghost['symbol']

        # orig_atom_name = self.ctx.original_atom_site.kind_name
        # ghost_atom_name = orig_atom_name+"_ghost"
        #orig_vac_name = self.ctx.original_vacancy_site.kind_name
        #ghost_vac_name = orig_vac_name+"_ghost"
        
        # Old
        #orig_vac_position = self.ctx.original_vacancy_site.position
        #orig_atom_position = self.ctx.original_atom_site.position

        # Note reversed positions
        #floating = {
        #    'floating_sites': [{
        #        "symbols": ghost_symbol,
        #        "name": ghost_name,
        #        "position": orig_vac_position
        #    }, {
        #        "symbols": ghost_symbol,
        #        "name": ghost_name,
        #        "position": orig_atom_position
        #    }]
        #}


        orig_atom_position = self.ctx.original_atom_site.position
        orig_vac_position = self.ctx.original_vacancy_site.position

        floating = {
            'floating_sites': [{
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_atom_position
            }, {
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_vac_position
            }]
        }



        basis_dict.update(floating)
        inputs['basis'] = Dict(dict=basis_dict)
        # adding Label 
        inputs["metadata"]["label"] = 'last'
 
        running = self.submit(SiestaBaseWorkChain, **inputs)
        self.report(
            f'Launched SiestaBaseWorkChain<{running.pk}> to relax the final structure.'
        )

        calculations ['final_relaxation_wk'] = running 
        #self.to_context(**{'final_relaxation_wk':running})

        return ToContext(**calculations)
        #return ToContext(final_relaxation_wk=running)

    def prepare_initial_path(self):
        """
        Perhaps more heuristics are needed?
        Here we either just interpolate or allow for a "migration direction"
        specification. The latter is not as critical in this case, since there
        can be no collisions with the "exchanged vacancy".
        """

        #initial_wk = self.ctx.initial_relaxation_wk
        #if not initial_wk.is_finished_ok:
        #    return self.exit_codes.ERROR_MAIN_WC

        #final_wk = self.ctx.final_relaxation_wk
        #if not final_wk.is_finished_ok:
            #return self.exit_codes.ERROR_MAIN_WC

        #s_initial = initial_wk.outputs.output_structure
        #s_final = final_wk.outputs.output_structure
        
        #s_initial = self.ctx.initial_relaxation_wk.outputs.output_structure
        #s_final = self.ctx.final_relaxation_wk.outputs.output_structure



        #s_initial = self.ctx.initial_relaxation_wk.outputs.output_structure
        #s_final = self.ctx.final_relaxation_wk.outputs.output_structure

        s_initial = self.ctx.first_structure 
        s_final = self.ctx.last_structure 


        # Find relaxed position of moving atom in initial structure
        # and in the final structure. These will be the positions of
        # the ghosts in the NEB run.

        self.ctx.relaxed_initial_atom_position = s_initial.sites[
            self.ctx.atom_site_index].position
        self.ctx.relaxed_final_atom_position = s_final.sites[
            self.ctx.atom_site_index].position

        #n_images = self.inputs.n_images.value
        n_images = self.inputs.n_images
        
        interp_m = self.inputs.interpolation_method 
        #
        # Add here any more heuristics, before handling the
        # path for further refinement

        if 'migration_direction' in self.inputs:

            #migration_direction = self.inputs.migration_direction.get_list()

            #pos1 = self.ctx.relaxed_initial_atom_position
            #pos2 = self.ctx.relaxed_final_atom_position

            # ... this would be unrelaxed:  pos2 = self.ctx.vacancy_position
            #atom_mid_path_position = find_mid_path_position(
            #    s_initial, pos1, pos2, migration_direction)
            #self.report(f"Using mid-path point {atom_mid_path_position}")

            #s_intermediate = find_intermediate_structure(
            #    s_initial, self.ctx.atom_site_index, atom_mid_path_position)

            # The starting_path is now built from two sections
            # We assume that the number of internal images is odd,
            # so that n_images // 2 is the number of internal images
            # of each section

            #first_list = interpolate_two_structures_ase(
            #    s_initial, s_intermediate, n_images // 2)
            #second_list = interpolate_two_structures_ase(
            #    s_intermediate, s_final, n_images // 2)

            #
            # Remove duplicate central point
            #
            #images_list = first_list[:-1] + second_list

            #if len(images_list) != n_images + 2:
            #    self.report(f"Number of images: {n_images} /= list length")
            #    return self.exit_codes.ERROR_CONFIG

            self.report("Preparing Vacancy Diffusion initial Path")
            self.report(f"The Interpolation Method is {interp_m.value} ")
            migration_direction = self.inputs.migration_direction
            pos1 = List(list=list(self.ctx.relaxed_initial_atom_position))
            pos2 = List(list=list(self.ctx.relaxed_final_atom_position))
            atom_site_index = Int(self.ctx.atom_site_index)            
            self.ctx.path = generate_initial_path_for_vacancy_exchange(s_initial,
                    s_final,n_images,interp_m, migration_direction,pos1,pos2,atom_site_index
                    )

            if len(self.ctx.path.get_array("positions")) != n_images.value + 2:
                self.report(f"Number of images: {n_images} /= list length")
                return self.exit_codes.ERROR_CONFIG

           
        else:
            
            #
            # Use a 'serializable' dictionary instead of the
            # actual kinds list
            #
            #_kinds_raw = [k.get_raw() for k in s_initial.kinds]
            #path_object.set_attribute('kinds', _kinds_raw)

            #self.ctx.path = path_object
            self.report("Preparing Vacancy Diffusion initial Path")
            self.ctx.path = generate_initial_path_for_vacancy_diffusion(
                s_initial, 
                s_final,
                n_images,
                interp_m,
                )


        #self.ctx.path =  images_list  #orm.TrajectoryData(images_list)


        self.out("initial_path",self.ctx.path)
        self.report('Generated starting path for NEB.')

    def run_NEB_workchain(self):

        inputs = self.exposed_inputs(SiestaBaseNEBWorkChain, namespace='neb')

        #print(inputs)

        inputs['starting_path'] = self.ctx.path

        basis_dict = inputs['basis'].get_dict()

        ghost = self.inputs.ghost_species.get_dict()
        ghost_name = ghost['name']
        ghost_symbol = ghost['symbol']

        
        # Old
        #atom_position = self.ctx.relaxed_initial_atom_position
        #vac_position = self.ctx.relaxed_final_atom_position

        # Note: ghost positions are fixed at their locations in the end points

        #floating = {
        #    'floating_sites': [{
        #        "symbols": ghost_symbol,
        #        "name": ghost_name,
        #        "position": atom_position
        #    }, {
        #        "symbols": ghost_symbol,
        #        "name": ghost_name,
        #        "position": vac_position
        #    }]
        #}


        orig_atom_position = self.ctx.original_atom_site.position
        orig_vac_position = self.ctx.original_vacancy_site.position

        floating = {
            'floating_sites': [{
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_atom_position
            }, {
                "symbols": ghost_symbol,
                "name": ghost_name,
                "position": orig_vac_position
            }]
        }



        basis_dict.update(floating)
        inputs['basis'] = Dict(dict=basis_dict)

        running = self.submit(SiestaBaseNEBWorkChain, **inputs)

        self.report(
            f'Launched SiestaBaseNEBWorkChain<{running.pk}> to find MEP for vacancy exchange.'
        )

        return ToContext(neb_wk=running)

    def check_results(self):
        """
        All checks are done in the NEB base workchain
        """

        if not self.ctx.neb_wk.is_finished_ok:
            outps = self.ctx.neb_wk.outputs
            self.out('neb_output_package', outps['neb_output_package'])
            return self.exit_codes.ERROR_NEB_WK

        outps = self.ctx.neb_wk.outputs
        self.out('neb_output_package', outps['neb_output_package'])
        barrier = outps['neb_output_package'].get_attribute("barrier")
        self.report(f"The Vacancy Exchange barrier is {barrier} eV ")
        self.report('VacancyExchangeBarrier workchain done.')


#    @classmethod
#    def inputs_generator(cls):  # pylint: disable=no-self-argument,no-self-use
#        from aiida_siesta.utils.inputs_generators import BaseWorkChainInputsGenerator
#        return BaseWorkChainInputsGenerator(cls)
