import os

import pandas as pd

from typing import List

import efs_constants as consts
import demand_utilities.utils as du
import demand_utilities.vehicle_occupancy as vo


def decompile_od(od_import: str,
                 od_export: str,
                 year: int,
                 decompile_factors_path: str
                 ) -> None:
    """
    Takes User Class compiled OD matrices and decompiles them down to their
    individual purposes. Uses the stored decompiled factors to split.

    Parameters
    ----------
    od_import:
        Directory containing the user class compiled OD matrices.

    od_export:
        Directory to write the decompiled OD matrices.

    year:
        Which year to decompile the matrices for.

    decompile_factors_path:
        Full path to the pickle file containing the decompile factors to use.

    Returns
    -------
    None
    """
    # Load the factors
    decompile_factors = pd.read_pickle(decompile_factors_path)

    # Loop through the compiled matrices and decompile
    for comp_mat_name in decompile_factors.keys():
        # We need to ignore the year, so break into component parts
        comp_calib_params = du.fname_to_calib_params(comp_mat_name,
                                                     get_user_class=True,
                                                     get_matrix_format=True,
                                                     force_ca_exists=True)

        # Find the matching compiled matrix and load
        mat_name = du.get_compiled_matrix_name(
            matrix_format=comp_calib_params['matrix_format'],
            user_class=comp_calib_params['user_class'],
            year=str(year),
            mode=str(comp_calib_params['m']),
            ca=comp_calib_params['ca'],
            tp=str(comp_calib_params['tp']),
            csv=True
        )
        comp_mat = pd.read_csv(os.path.join(od_import, mat_name), index_col=0)
        print("Decompiling matrix: %s" % mat_name)

        # Loop through the factors and decompile the matrix
        for part_mat_name in decompile_factors[comp_mat_name].keys():
            # Decompile the matrix using the factors
            factors = decompile_factors[comp_mat_name][part_mat_name]
            part_mat = comp_mat * factors

            # Generate filename and save the decompiled matrix
            part_calib_params = du.fname_to_calib_params(part_mat_name,
                                                         get_trip_origin=True,
                                                         get_matrix_format=True)

            # If the year has not been found, add it in manually
            if part_calib_params.get('yr') is None:
                part_calib_params['yr'] = str(year)

            mat_name = du.calib_params_to_dist_name(
                trip_origin=part_calib_params['trip_origin'],
                matrix_format=part_calib_params['matrix_format'],
                calib_params=part_calib_params,
                csv=True
            )
            part_mat.to_csv(os.path.join(od_export, mat_name))


def _convert_to_efs_matrices_user_class(import_path: str,
                                        export_path: str,
                                        matrix_format: str,
                                        to_wide: bool = False,
                                        wide_col_name: str = 'zone_id'
                                        ) -> None:
    # Init
    import_files = du.list_files(import_path)

    # Figure out the new filename and copy to export location
    for fname in import_files:
        print("Converting '%s' to EFS matrix format..." % str(fname))

        calib_params = du.post_me_fname_to_calib_params(fname)
        new_fname = du.get_compiled_matrix_name(
            matrix_format=matrix_format,
            user_class=calib_params['user_class'],
            year=str(calib_params['yr']),
            mode=str(calib_params['m']),
            tp=str(calib_params['tp']),
            csv=True
        )

        # Just copy over if we don't need to convert
        if not to_wide:
            du.copy_and_rename(
                src=os.path.join(import_path, fname),
                dst=os.path.join(export_path, new_fname)
            )
            continue

        # Only get here if we need to convert to wide

        # Read in, convert to wide, and save in new location
        mat = pd.read_csv(os.path.join(import_path, fname),
                          names=[wide_col_name, 'col2', 'vals'])

        # Convert from long to wide format and output
        du.long_to_wide_out(
            mat,
            v_heading=wide_col_name,
            h_heading='col2',
            values='vals',
            out_path=os.path.join(export_path, new_fname)
        )

    return


def convert_to_efs_matrices(import_path: str,
                            export_path: str,
                            matrix_format: str,
                            user_class: bool = True,
                            to_wide: bool = True,
                            wide_col_name: str = 'zone_id',
                            from_pcu: bool = False,
                            vehicle_occupancy_import: str = None,
                            m_needed: List[int] = consts.MODES_NEEDED
                            ) -> None:
    """
    Converts matrices from TfN models into a format that EFS uses.
    This usually means a name conversion, and converting to wide format.

    Parameters
    ----------
    import_path:
        The directory to find the matrices to import and convert.

    export_path:
        The directory to output the converted matrices.

    matrix_format:
        What format the matrices are in. Usually 'pa' or 'od'.

    user_class:
        Whether the matrices are aggregated to used class or not.
        Default value is True.

    to_wide:
        Whether the matrices need converting from long to wide format.
        Default value is True.

    wide_col_name:
        If converting the wide format, this name is used as the title for the
        rows/columns of the resulting matrices.

    from_pcu:
        Whether the input matrices need converting from vehicle demand to
        people demand or not

    vehicle_occupancy_import:
        Only needs to be set if from_pcu is True. This is the location to find
        the vehicle occupancy file. The given location is usually the home of
        the imports directory. e.g. "Y:/NorMITs Demand/import"

    m_needed:
        The mode being used when converting from PCU to people.

    Returns
    -------
    None
    """
    # Input checks
    if len(m_needed) > 1:
        raise ValueError("Got more than one mode. convert_to_efs_matrices() "
                         "can only handle one mode at a time.")

    temp_export_path = export_path
    if from_pcu:
        if vehicle_occupancy_import is None:
            raise ValueError("vehicle_occupancy_import needs to be set when"
                             "converting from PCU matrices.")
        temp_export_path = os.path.join(export_path, 'from_pcu')
        du.create_folder(temp_export_path)

    if user_class:
        _convert_to_efs_matrices_user_class(
            import_path=import_path,
            export_path=temp_export_path,
            matrix_format=matrix_format,
            to_wide=to_wide,
            wide_col_name=wide_col_name
        )
    else:
        # TODO: Write this functionality
        raise NotImplementedError("Cannot convert naming unless in user class"
                                  "format.")

    if not from_pcu:
        return

    # Only get here if we need to convert from PCU format
    vo.people_vehicle_conversion(
        input_folder=temp_export_path,
        import_folder=vehicle_occupancy_import,
        export_folder=export_path,
        mode=str(m_needed[0]),
        method='to_people',
        out_format='wide'
    )
