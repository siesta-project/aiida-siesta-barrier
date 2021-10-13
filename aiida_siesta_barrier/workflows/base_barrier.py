#======================================================
# Base Barrier 
#=======================================================

class BaseBarrierWorkChain(WorkChain):
    """
    Workchain to compute the barrier for different paths.
    """
    @classmethod
    def define(cls, spec):
        super().define(spec)

