from aiida.orm.nodes.data.structure import Site
from aiida_siesta.utils.structures import clone_aiida_structure
from aiida_siesta_barrier.utils.interpol import interpolate_two_structures_ase

def ring_atoms(host,list_of_indexes):
    """
    """
    ring_atoms_dict={}
    host_sites=host.sites 
    i=0
    for ind in list_of_indexes:
        print(ind-1)
        ring_atoms_dict [i] = host_sites[ind-1]
        i=i+1
    return ring_atoms_dict


def removing_ring_atoms(host,list_of_indexes):
    """
    """
    host_sites=host.sites
    structure_final = clone_aiida_structure(host)
    structure_final.clear_sites()
    list_of_indexes.sort(reverse=True)
    new_sites = host_sites
    for ind in list_of_indexes:
        print(ind-1)
        final_site = host_sites.pop(ind-1)

    [structure_final.append_site(s) for s in new_sites]

    return structure_final


def add_sites(structure,first_site,final_site,clean_site=False):
    """
    """
    from aiida.orm.nodes.data.structure import Site

    s_initial = clone_aiida_structure(structure)
    s_final = clone_aiida_structure(structure)
    if clean_site:
        s_initial.clear_sites()
        s_final.clear_sites()
    s_initial.append_site(first_site)
    new_atom_site = Site(kind_name=first_site.kind_name,
                         position=final_site.position)

    s_final.append_site(new_atom_site)

    return s_initial,s_final

def n_sites(ring_atoms_info,structure_ring_cavity):
    """
    """
    n_sites_dict = {}
    for site in range(len(ring_atoms_info.keys())-1):
        print (site,site+1)
        n_sites_dict[site]=add_sites(structure_ring_cavity,ring_atoms_info[site],ring_atoms_info[site+1])
    # the last
    i=0
    f=len(ring_atoms_info.keys())-1
    print(f,i)
    n_sites_dict[f]=add_sites(structure_ring_cavity,ring_atoms_info[f],ring_atoms_info[i])

    return n_sites_dict


def specie(n_sites_dict,n_images):
    """
    """
    interpolate_dict ={}
    for ind in n_sites_dict.keys():
        #print(ind)
        interpolate_dict[ind] = interpolate_two_structures_ase(n_sites_dict[ind][0],n_sites_dict[ind][1],n_images)
    
    specie={}
    for sp in range(len(interpolate_dict)):
        position=[]
        #print(sp)
        for i in range(n_images+2):
            position.append(interpolate_dict[sp][i].sites[-1])
        specie [sp]=position 
        
    return specie


def merge_ring(structure_ring_cavity,specie,n_images):
    """
    """
    images ={}
    for i in range(n_images+2):
        structure_final = clone_aiida_structure(structure_ring_cavity)
        for sp in range(len(specie.keys())): 
            structure_final.append_site(specie[sp][i])
        images[i] = structure_final
    return images
