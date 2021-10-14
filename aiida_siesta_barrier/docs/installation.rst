Installation
++++++++++++

It would be a good idea to create and switch to a new python virtual
environment before the installation.

Because the package is under development, in order to enjoy the most recent features
one can clone the github repository
(https://github.com/siesta-project/aiida-siesta-barrier) and install
from the top level of the plugin directory with::

    pip install -e .

As a pre-requisite, both commands above will install an appropriate version of the
``aiida-core`` and ``aiida-siesta``, if this is not already installed.
In case of a fresh install of ``aiida-core``, follow the `AiiDA documentation`_
in order to configure aiida.

.. important:: In any case, do not forget to run the following commands after the 
   installation::
                
        reentry scan -r aiida
        verdi daemon restart


.. _AiiDA documentation: https://aiida.readthedocs.io/projects/aiida-core/en/stable/
