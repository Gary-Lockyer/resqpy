import os
import numpy as np
import pandas as pd
from numpy.testing import assert_array_almost_equal
from lxml import etree

import resqpy.olio.xml_et as rqet
import resqpy.well
from resqpy.well.well_utils import load_hdf5_array, load_lattice_array, extract_xyz, find_entry_and_exit, _as_optional_array, _pl, well_names_in_cellio_file
from resqpy.grid import RegularGrid


def test_load_hdf5_array(example_model_with_well):

    # --------- Arrange ----------
    # Create a Deviation Survey object in memory

    # Load example model from a fixture
    model, well_interp, datum, traj = example_model_with_well

    # Create a survey
    data = dict(
        title = 'Majestic Umlaut ö',
        originator = 'Thor, god of sparkles',
        md_uom = 'ft',
        angle_uom = 'rad',
        is_final = True,
    )
    array_data = dict(
        measured_depths = np.array([1, 2, 3], dtype = float) + 1000.0,
        azimuths = np.array([4, 5, 6], dtype = float),
        inclinations = np.array([7, 8, 9], dtype = float),
        first_station = np.array([0, -1, 999], dtype = float),
    )

    survey = resqpy.well.DeviationSurvey(
        parent_model = model,
        represented_interp = well_interp,
        md_datum = datum,
        **data,
        **array_data,
    )

    # ----------- Act ---------
    survey.write_hdf5()
    survey.create_xml()
    mds_node = rqet.find_tag(survey.root, 'Mds', must_exist = True)
    # the only purpose of the call is to ensure that the array is cached in memory so should return None
    # a copy of the whole array is cached in memory as an attribute of the object
    expected_result = load_hdf5_array(survey, mds_node, 'measured_depths')

    # -------- Assert ---------
    np.testing.assert_equal(survey.__dict__['measured_depths'], array_data['measured_depths'])
    assert expected_result is None


def test_load_lattice_array(example_model_with_well):
    # Load example model from a fixture
    model, well_interp, datum, traj = example_model_with_well
    mds = traj.measured_depths[:3]

    lattice_array_step_start = mds[0]
    lattice_array_step_value = (mds[1] - lattice_array_step_start) / 2
    lattice_array_step_count = 3
    expected_mds = lattice_array_step_start + np.arange(lattice_array_step_count) * lattice_array_step_value

    # Construct a NodeMd element defined as DoubleLatticeArray
    node_md_xml_string = f"""
    <NodeMd type="DoubleLatticeArray">
        <StartValue>{lattice_array_step_start}</StartValue>
        <Offset>
            <Value>{lattice_array_step_value}</Value>
            <Count>{lattice_array_step_count}</Count>
        </Offset>
    </NodeMd>
    """
    mds_node = etree.fromstring(node_md_xml_string)
    target_object = well_interp

    expected_result = load_lattice_array(target_object, mds_node, "node_mds", traj)
    assert expected_result is None
    np.testing.assert_equal(target_object.__dict__["node_mds"], expected_mds)


def test_extract_xyz(example_model_with_well):

    # --------- Arrange ----------
    # Create a Deviation Survey object in memory

    # Load example model from a fixture
    model, well_interp, datum, traj = example_model_with_well

    # Create a survey
    data = dict(
        title = 'Majestic Umlaut ö',
        originator = 'Thor, god of sparkles',
        md_uom = 'ft',
        angle_uom = 'rad',
        is_final = True,
    )
    array_data = dict(
        measured_depths = np.array([1, 2, 3], dtype = float) + 1000.0,
        azimuths = np.array([4, 5, 6], dtype = float),
        inclinations = np.array([7, 8, 9], dtype = float),
        first_station = np.array([0, -1, 999], dtype = float),
    )

    survey = resqpy.well.DeviationSurvey(
        parent_model = model,
        represented_interp = well_interp,
        md_datum = datum,
        **data,
        **array_data,
    )

    # ----------- Act ---------
    survey.write_hdf5()
    survey.create_xml()
    first_station_node = rqet.find_tag(survey.root, 'FirstStationLocation', must_exist = True)
    first_station_xyz = extract_xyz(first_station_node)

    # ----------- Assert ---------
    np.testing.assert_equal(first_station_xyz, array_data['first_station'])


def test_find_entry_and_exit(example_model_and_crs):

    # --------- Arrange ----------
    model, crs = example_model_and_crs
    grid = RegularGrid(model,
                       extent_kji = (5, 3, 3),
                       dxyz = (50.0, -50.0, 50.0),
                       origin = (0.0, 0.0, 100.0),
                       crs_uuid = crs.uuid,
                       set_points_cached = True)
    grid.write_hdf5()
    grid.create_xml(write_geometry = True)
    well_name = 'DOGLEG'
    bw = resqpy.well.BlockedWell(model, well_name = well_name, use_face_centres = True, add_wellspec_properties = True)
    # populate empty blocked well object for a 'vertical' well in the given column
    bw.set_for_column(well_name = well_name, grid = grid, col_ji0 = (1, 1))
    cp = grid.corner_points(cell_kji0 = (1, 1, 1))
    cell_centre = np.mean(cp, axis = (0, 1, 2))
    assert_array_almost_equal(cell_centre, (75.0, -75.0, 175.0))
    e_entry_xyz = np.array([75, -75, 150], dtype = float)
    e_exit_xyz = np.array([75, -100, 175], dtype = float)
    entry_vector = 100.0 * (e_entry_xyz - cell_centre)
    exit_vector = 100.0 * (e_exit_xyz - cell_centre)

    # --------- Act ----------
    (entry_axis, entry_polarity, entry_xyz, exit_axis, exit_polarity, exit_xyz) =\
        find_entry_and_exit(cp = cp, entry_vector = entry_vector, exit_vector = exit_vector, well_name = well_name)

    # --------- Assert ----------
    assert (entry_axis, entry_polarity, exit_axis, exit_polarity) == (0, 0, 1, 1)
    assert_array_almost_equal(entry_xyz, e_entry_xyz)
    assert_array_almost_equal(exit_xyz, e_exit_xyz)


def test_as_optional_array():

    # --------- Arrange ----------
    to_test = [[1, 2, 3], None]

    # --------- Act ----------
    result1, result2 = _as_optional_array(to_test[0]), _as_optional_array(to_test[1])

    # --------- Assert ----------
    np.testing.assert_equal(result1, np.array([1, 2, 3]))
    assert result2 is None


def test_pl():

    # --------- Arrange ----------
    to_test = [1, 'Banoffee']

    # --------- Act ----------
    result1, result2, result3 = _pl(i = to_test[0]), _pl(i = to_test[1]), _pl(i = to_test[1], e = True)

    # --------- Assert ----------
    assert result1 == ''
    assert result2 == 's'
    assert result3 == 'es'


def test_well_names_in_cellio_file(tmp_path):

    # --------- Arrange ----------
    well_name = 'Banoffee'
    cellio_file = os.path.join(tmp_path, 'cellio.dat')
    source_df = pd.DataFrame(
        [[1, 1, 1, 25, 25, 0, 26, 26, 1, 120, 0.12], [2, 2, 1, 26, -26, 126, 27, -27, 127, 117, 0.20],
         [2, 3, 1, 27, -27, 127, 28, -28, 128, 135, 0.15]],
        columns = [
            'i_index unit1 scale1', 'j_index unit1 scale1', 'k_index unit1 scale1', 'x_in unit1 scale1',
            'y_in unit1 scale1', 'z_in unit1 scale1', 'x_out unit1 scale1', 'y_out unit1 scale1', 'z_out unit1 scale1',
            'Perm unit1 scale1', 'Poro unit1 scale1'
        ])

    with open(cellio_file, 'w') as fp:
        fp.write('1.0\n')
        fp.write('Undefined\n')
        fp.write(f'{well_name} terrible day\n')
        fp.write('11\n')
        for col in source_df.columns:
            fp.write(f' {col}\n')
        for row_index in range(len(source_df)):
            row = source_df.iloc[row_index]
            for col in source_df.columns:
                fp.write(f' {int(row[col])}')
            fp.write('\n')

    # --------- Arrange ----------
    well_list = well_names_in_cellio_file(cellio_file = cellio_file)

    # --------- Assert ----------
    assert len(well_list) == 1
    assert set(well_list) == {well_name}
