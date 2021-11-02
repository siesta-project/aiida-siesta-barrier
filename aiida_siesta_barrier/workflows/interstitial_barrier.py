from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction, if_
#from aiida_siesta.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta_barrier.workflows.neb_base import SiestaBaseNEBWorkChain
from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida_siesta.utils.structures import clone_aiida_structure
from aiida_siesta_barrier.utils.interpol import interpolate_two_structures_ase
from aiida.orm import Dict,Int

#----------------------------------------------------------------------------
# FIXED:
#       (1) Restarting points 
#       (2) Adding interpolation Methods
#       (3) Adding outputs for WorkChain 
#
# TO FIX:
#        - fixing name and symbol problem to use get_ase method  
#        - geometryconstraints should be used instead of Geometry-Constraints
#----------------------------------------------------------------------------

@calcfunction
def generate_initial_path_for_interstitial(s1, s2, nimages, interp_method):
    """
    Wrapper calcfunction to keep provenance
    :param: s1, s2 : StructureData objects
    :param: nimages: Int object
    """

    images_list = interpolate_two_structures_ase(s1, s2, nimages.value,interp_method.value )
    path_object = orm.TrajectoryData(images_list)
    #
    # Use a 'serializable' dictionary instead of the
    # actual kinds list
    #
    _kinds_raw = [k.get_raw() for k in s1.kinds]
    path_object.set_attribute('kinds', _kinds_raw)

    return path_object


class InterstitialBarrierWorkChain(WorkChain):
    """
    Workchain to compute the barrier for interstitial
    diffusion starting from the host structure and
    initial and final interstitial positions
    
    INPUTS :
            initial,
            final,
            neb,
            host_structure,
            interstitial_species,
            initial_position,
            final_position,
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
        
        spec.input('interstitial_species',
                    valid_type=orm.Dict,
                    help='Species in interstitials (symbol and name)')
        #
        # These should be lists of floats. Pending validations
        #
        spec.input('initial_position',
                    valid_type=orm.List,  # validator...
                    help='Initial position of interstitial in host structure')
        
        spec.input('final_position',
                    valid_type=orm.List,  # validator...
                    help='Final position of interstitial in host structure')

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



        spec.exit_code(
            200,
            'ERROR_MAIN_WC',
            message='The end-point relaxation SiestaBaseWorkChain failed')
        spec.exit_code(250,
                       'ERROR_CONFIG',
                       message='Cannot figure out interstitial position(s)')
        spec.exit_code(300,
                       'ERROR_NEB_WK',
                       message='NEBWorkChain did not finish correctly')



    def is_restart(self):

        """
        checking if neb workchain no provided or not 
        """
        if 'neb_wk_node' not in self.inputs :
            self.report("Starting Workchain from Scratch")
            return False
        else:
            self.report("Restarting Workchain ... ")
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
        Make copies of host structure and add interstitials
        """

        host = self.inputs.host_structure
        initial_position = self.inputs.initial_position.get_list()
        final_position = self.inputs.final_position.get_list()

        int_atom = self.inputs.interstitial_species.get_dict()
        int_atom_name = int_atom['name']
        int_atom_symbol = int_atom['symbol']

        # With pseudo families and smart fallback to chemical symbol,
        # the addition of, e.g., '_int' for the interstitial atom's name
        # is easily supported
        # If not, the pseudo must be manually included.
        #
        s_initial = clone_aiida_structure(host)
        s_final = clone_aiida_structure(host)

        try:
            s_initial.append_atom(symbols=int_atom_symbol,
                                  position=initial_position,
                                  name=int_atom_name)

            s_final.append_atom(symbols=int_atom_symbol,
                                position=final_position,
                                name=int_atom_name)
        except:
            self.report("Problem adding atom to end-points")
            return self.exit_codes.ERROR_CONFIG

        self.ctx.s_initial = s_initial
        self.ctx.s_final = s_final
        self.ctx.atom_symbol = int_atom_symbol

        self.report('Created initial and final structures')

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

        n_images = self.inputs.n_images.value

        #
        # Add here any heuristics, before handling the
        # path for further refinement
        #
        # starting_path = ....
        #
        #
        # We will need a more general refiner, with an
        # actual path, and not just end-points
        #
        # refined_path = refine_neb_path(starting_path)

        # Here we simply interpolate with the ASE method
        # (use a calcfunction to wrap)
        
        inter_m = self.inputs.interpolation_method
        self.report(f"The Interpolation Method is {inter_m.value} ")
        self.ctx.path = generate_initial_path_for_interstitial(s_initial, s_final,
                                           orm.Int(n_images),
                                           inter_m,
                                           )
        
        self.out("initial_path",self.ctx.path)
        self.report('Generated starting path for NEB.')

    def run_NEB_workchain(self):

        inputs = self.exposed_inputs(SiestaBaseNEBWorkChain, namespace='neb')

        print(inputs)

        inputs['starting_path'] = self.ctx.path

        running = self.submit(SiestaBaseNEBWorkChain, **inputs)

        self.report(
            f'Launched SiestaBaseNEBWorkChain<{running.pk}> to find MEP for {self.ctx.atom_symbol} interstitial diffusion.'
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
        self.report(f"The InterstitialBarrier is {barrier} eV ")
        self.report('InterstitialBarrier WorkChain DONE.')


#    @classmethod
#    def inputs_generator(cls):  # pylint: disable=no-self-argument,no-self-use
#        from aiida_siesta.utils.inputs_generators import BaseWorkChainInputsGenerator
#        return BaseWorkChainInputsGenerator(cls)
