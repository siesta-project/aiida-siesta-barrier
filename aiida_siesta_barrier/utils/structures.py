import numpy as np
from aiida.orm.nodes.data.structure import Site
from aiida_siesta.utils.structures import clone_aiida_structure


def exchange_sites_in_structure(struct, index1, index2):
    """
    Given a structure s, return another structure with the coordinates of i1, i2 sites interchanged
    :param: struct  a StructureData object
    :param: index1, index2     site indexes to be exchanged
    """
    sites = struct.sites

    site1 = sites[index1]
    site2 = sites[index2]
    pos1 = site1.position
    pos2 = site2.position
    newsite1 = Site(kind_name=site1.kind_name, position=pos2)
    newsite2 = Site(kind_name=site2.kind_name, position=pos1)
    sites[index1] = newsite1
    sites[index2] = newsite2

    truct = clone_aiida_structure(struct)
    truct.clear_sites()

    for site in sites:
        truct.append_site(site)

    return truct


def find_intermediate_structure(struct,
                                index1,
                                intermediate_position,
                                index2=None):
    """
    Given a structure and the indexes of two sites, and an
    intermediate point, generate an intermediate structure in which
    the index1 atom has moved to the intermediate point. If a second atom
    index is input, the second atom is moved to an image point with an
    opposite relative displacement. This is useful to 'prime' a path
    to avoid head-on collissions, for example.

    :param: struct  a StructureData object
    :param: index1, index2,  indexes of atoms in the structure struct
            If index2 is None (default), only the first atom is moved.
    :param: intermediate_position, a list of floats

    """
    i1_path_position = np.array(intermediate_position)

    sites = struct.sites

    pos1 = np.array(sites[index1].position)
    site1 = sites[index1]
    newsite1 = Site(kind_name=site1.kind_name, position=i1_path_position)
    sites[index1] = newsite1

    # The second atom's image position is obtained by
    # reversing the sign of the above relative position for i1
    if index2 is not None:
        pos2 = np.array(sites[index2].position)
        # Relative position of the path point and the first atom
        p_wrt_p1 = i1_path_position - pos1
        i2_path_position = pos2 - p_wrt_p1
        site2 = sites[index2]
        newsite2 = Site(kind_name=site2.kind_name, position=i2_path_position)
        sites[index2] = newsite2

    intermediate_structure = clone_aiida_structure(struct)
    intermediate_structure.clear_sites()
    for site in sites:
        intermediate_structure.append_site(site)

    return intermediate_structure


def compute_mid_path_position(struct, index1, index2, migration_direction):
    """
    The basic heuristic here is to avoid head-on collissions
    by defining an "avoidance cylinder" around the line
    joining the two atoms exchanged. The input "migration_direction"
    serves to define a point on the surface of that cylinder, at
    the mid-point, which is used as the mid-point of the starting path.

    :param: struct  a StructureData object
    :param: index1, index2,  indexes of the atoms
    :param: migration direction, in lattice coordinates
    """
    AVOIDANCE_RADIUS = 1.00  # 1.0 angstrom

    cell = np.array(struct.cell)
    cell_direction = np.array(migration_direction)

    cart_direction = np.matmul(cell, cell_direction)

    # Find positions of i1 and i2
    sites = struct.sites
    pos1 = np.array(sites[index1].position)
    pos2 = np.array(sites[index2].position)

    # Find the unit vector parallel to the line index1-index2
    direction = pos2 - pos1
    dmod = np.sqrt(direction.dot(direction))
    unit_vec = direction / dmod

    # Sanity check: migration direction should not be near-parallel
    # to the line joining the exchanged atoms...
    cross_product = np.cross(direction, cart_direction)
    mod_cross_product = np.sqrt(cross_product.dot(cross_product))
    mod_cd = np.sqrt(np.dot(cart_direction, cart_direction))

    if np.abs(mod_cross_product / (mod_cd * dmod)) < 1.0e-2:
        print("Migration direction near parallel to line of sight")
        return None

    # Find component of cart_direction perpendicular to the index1-index2 line,
    # and unit vector
    c_perp = cart_direction - unit_vec.dot(cart_direction) * unit_vec
    c_perp_mod = np.sqrt(c_perp.dot(c_perp))
    u_perp = c_perp / c_perp_mod

    # The mid-point of the path is now determined by the vector sum
    # of half of d and u_perp times the radius of the avoidance cylinder
    path_mid_point = pos1 + 0.5 * dmod * unit_vec + AVOIDANCE_RADIUS * u_perp

    return path_mid_point.tolist()


def find_mid_path_position(struct, pos1, pos2, migration_direction):
    """
    The basic heuristic here is to avoid head-on collissions
    by defining an "avoidance cylinder" around the line
    joining the initial and final points . The input "migration_direction"
    serves to define a point on the surface of that cylinder, at
    the mid-point, which is used as the mid-point of the starting path.

    :param: struct  a StructureData object
    :param: pos1, pos2,  initial and final positions
    :param: migration direction, in lattice coordinates
    """
    AVOIDANCE_RADIUS = 1.00  # 1.0 angstrom

    cell = np.array(struct.cell)
    cell_direction = np.array(migration_direction)

    cart_direction = np.matmul(cell, cell_direction)

    # Find positions of index1 and index2
    pos1 = np.array(pos1)
    pos2 = np.array(pos2)

    # Find the unit vector parallel to the line i1-i2
    direction = pos2 - pos1
    dmod = np.sqrt(direction.dot(direction))
    unit_vec = direction / dmod

    # Sanity check: migration direction should not be near-parallel
    # to the line joining the two sites
    cross_product = np.cross(direction, cart_direction)
    mod_cross_product = np.sqrt(cross_product.dot(cross_product))
    mod_cd = np.sqrt(np.dot(cart_direction, cart_direction))

    if np.abs(mod_cross_product / (mod_cd * dmod)) < 1.0e-2:
        print("Migration direction near parallel to line of sight")
        return None

    # Find component of cart_direction perpendicular to the i1-i2 line,
    # and unit vector
    c_perp = cart_direction - unit_vec.dot(cart_direction) * unit_vec
    c_perp_mod = np.sqrt(c_perp.dot(c_perp))
    u_perp = c_perp / c_perp_mod

    # The mid-point of the path is now determined by the vector sum
    # of half of d and u_perp times the radius of the avoidance cylinder
    path_mid_point = pos1 + 0.5 * dmod * unit_vec + AVOIDANCE_RADIUS * u_perp

    return path_mid_point.tolist()
